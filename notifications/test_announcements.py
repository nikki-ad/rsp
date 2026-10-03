from io import BytesIO
from tempfile import TemporaryDirectory
from datetime import timedelta

from PIL import Image
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from academic.models import AcademicYear, Classroom, Enrollment, Grade
from accounts.models import StudentProfile, TeacherProfile
from .models import Announcement, Notification


class AnnouncementTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.manager = User.objects.create_user(username='manager', role='school_manager')
        cls.teacher = User.objects.create_user(username='teacher', role='teacher')
        TeacherProfile.objects.create(user=cls.teacher)
        year = AcademicYear.objects.create(title='1405', status='active')
        grade = Grade.objects.create(code='1', title='اول', order=1)
        cls.students = []
        cls.classrooms = []
        for index in range(3):
            user = User.objects.create_user(username=f'student{index}', role='student')
            profile = StudentProfile.objects.create(user=user)
            cls.students.append(user)
            # Include an active student without an enrollment.
            if index < 2:
                classroom = Classroom.objects.create(name=f'کلاس {index}', grade=grade, academic_year=year, capacity=30)
                cls.classrooms.append(classroom)
                Enrollment.objects.create(student=profile, classroom=classroom, academic_year=year)
        inactive = User.objects.create_user(username='inactive', role='student', is_active=False)
        StudentProfile.objects.create(user=inactive)

    def setUp(self):
        self.media = TemporaryDirectory()
        self.addCleanup(self.media.cleanup)
        self.settings_override = override_settings(MEDIA_ROOT=self.media.name)
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)
        self.client.force_login(self.manager)

    def data(self, **kwargs):
        data = dict(title='اطلاعیه تست', message='متن اطلاعیه', audience='students',
                    classrooms=[str(c.pk) for c in self.classrooms], publish_at=timezone.localtime(timezone.now() - timedelta(minutes=2)).strftime('%Y-%m-%dT%H:%M'),
                    is_active='on')
        data.update(kwargs)
        return data

    def image(self, name='poster.png'):
        output = BytesIO()
        Image.new('RGB', (40, 60), 'pink').save(output, format='PNG')
        return SimpleUploadedFile(name, output.getvalue(), content_type='image/png')

    def create(self, **kwargs):
        response = self.client.post(reverse('announcement_create'), self.data(**kwargs))
        self.assertEqual(response.status_code, 302)
        return Announcement.objects.latest('created_at')

    def test_all_users_without_enrollment_receive_and_see_image(self):
        announcement = self.create(audience="all", image=self.image())
        self.assertIsNone(announcement.classroom_id)
        self.assertEqual(set(Notification.objects.values_list('recipient_id', flat=True)),
                         {student.pk for student in self.students} | {self.teacher.pk})
        self.assertEqual(Notification.objects.filter(announcement=announcement).count(), 4)
        for student in self.students:
            self.client.force_login(student)
            for route in ['student_dashboard', 'notification_list']:
                self.assertContains(self.client.get(reverse(route)), announcement.image.url)
        self.client.force_login(self.teacher)
        self.assertContains(self.client.get(reverse('teacher_dashboard')), announcement.title)

    def test_class_specific_does_not_leak_to_other_classes(self):
        announcement = self.create(classrooms=[str(self.classrooms[0].pk)], image=self.image())
        self.assertEqual(list(Notification.objects.values_list('recipient_id', flat=True)), [self.students[0].pk])
        self.client.force_login(self.students[1])
        self.assertNotContains(self.client.get(reverse('student_dashboard')), announcement.image.url)
        self.assertNotContains(self.client.get(reverse('notification_list')), announcement.image.url)

    def test_class_specific_requires_class_and_image_is_optional(self):
        response = self.client.post(reverse('announcement_create'), self.data(classrooms=[]))
        self.assertEqual(response.status_code, 200)
        self.assertIn('classrooms', response.context['form'].errors)
        self.assertEqual(Announcement.objects.count(), 0)
        self.assertFalse(self.create().image)

    def test_image_retain_replace_clear_updates_notification(self):
        announcement = self.create(image=self.image())
        url = reverse('announcement_edit', args=[announcement.pk])
        original = announcement.image.name
        self.assertEqual(self.client.post(url, self.data()).status_code, 302)
        announcement.refresh_from_db()
        self.assertEqual(announcement.image.name, original)
        self.assertEqual(self.client.post(url, self.data(image=self.image('replacement.png'))).status_code, 302)
        announcement.refresh_from_db()
        self.assertNotEqual(announcement.image.name, original)
        self.client.force_login(self.students[0])
        self.assertContains(self.client.get(reverse('notification_list')), announcement.image.url)
        self.client.force_login(self.manager)
        self.assertEqual(self.client.post(url, self.data(**{'image-clear': 'on'})).status_code, 302)
        announcement.refresh_from_db()
        self.assertFalse(announcement.image)
        self.assertEqual(Notification.objects.count(), 2)

    def test_non_image_upload_rejected(self):
        response = self.client.post(reverse('announcement_create'), self.data(
            image=SimpleUploadedFile('fake.png', b'not an image', content_type='image/png')))
        self.assertEqual(response.status_code, 200)
        self.assertIn('image', response.context['form'].errors)
        self.assertEqual(Notification.objects.count(), 0)
        self.assertEqual(Announcement.objects.count(), 0)

    def test_teacher_and_manager_see_image_and_form_help(self):
        response = self.client.get(reverse('announcement_create'))
        self.assertContains(response, 'multipart/form-data')
        self.assertContains(response, 'کلاس‌های تیک‌خورده')
        announcement = self.create(audience='teachers', teachers=[str(self.teacher.teacher_profile.pk)], image=self.image())
        self.assertContains(self.client.get(reverse('announcement_list')), announcement.image.url)
        self.client.force_login(self.teacher)
        self.assertContains(self.client.get(reverse('teacher_dashboard')), announcement.image.url)
        self.assertContains(self.client.get(reverse('notification_list')), announcement.image.url)

    def test_future_and_inactive_announcements_not_sent_or_shown(self):
        future = timezone.localtime(timezone.now() + timedelta(days=1)).strftime('%Y-%m-%dT%H:%M')
        self.create(publish_at=future, image=self.image())
        self.create(is_active='', image=self.image())
        self.assertEqual(Notification.objects.count(), 0)
        self.client.force_login(self.students[0])
        self.assertNotContains(self.client.get(reverse('student_dashboard')), 'اطلاعیه تست')

    def test_student_cannot_manage_announcements(self):
        self.client.force_login(self.students[0])
        self.assertEqual(self.client.post(reverse('announcement_create'), self.data(image=self.image())).status_code, 403)
        self.assertEqual(Announcement.objects.count(), 0)

    def test_students_audience_ignores_stale_class_selection(self):
        announcement = self.create(classroom=str(self.classrooms[0].pk))
        self.assertIsNone(announcement.classroom_id)
        self.assertEqual(Notification.objects.count(), 2)

    def test_teacher_selection_does_not_leak(self):
        user = get_user_model().objects.create_user(username="other_teacher", role="teacher")
        TeacherProfile.objects.create(user=user)
        item = self.create(audience="teachers", teachers=[str(self.teacher.teacher_profile.pk)])
        self.assertEqual(list(Notification.objects.values_list("recipient_id", flat=True)), [self.teacher.pk])
        self.client.force_login(user)
        self.assertNotContains(self.client.get(reverse("teacher_dashboard")), item.title)
        self.assertNotContains(self.client.get(reverse("notification_list")), item.title)

    def test_missing_teacher_selection_rejected(self):
        response = self.client.post(reverse("announcement_create"), self.data(audience="teachers", teachers=[]))
        self.assertIn("teachers", response.context["form"].errors)
        self.assertFalse(Announcement.objects.exists())

    def test_edit_moves_delivery_and_visibility_to_new_class(self):
        item = self.create(classrooms=[str(self.classrooms[0].pk)])
        response = self.client.post(reverse("announcement_edit", args=[item.pk]),
                                   self.data(classrooms=[str(self.classrooms[1].pk)]))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(list(Notification.objects.values_list("recipient_id", flat=True)), [self.students[1].pk])
        self.client.force_login(self.students[0])
        self.assertNotContains(self.client.get(reverse("student_dashboard")), item.title)
        self.assertNotContains(self.client.get(reverse("notification_list")), item.title)
        self.client.force_login(self.students[1])
        self.assertContains(self.client.get(reverse("student_dashboard")), item.title)
        self.assertContains(self.client.get(reverse("notification_list")), item.title)

    def test_old_and_scheduled_announcements_repair_delivery_without_duplicates(self):
        item = Announcement.objects.create(title="old notice", message="legacy", audience="students", publish_at=timezone.now())
        self.client.force_login(self.students[2])
        self.assertContains(self.client.get(reverse("student_dashboard")), item.title)
        self.assertContains(self.client.get(reverse("notification_list")), item.title)
        self.assertEqual(Notification.objects.filter(announcement=item, recipient=self.students[2]).count(), 1)
        self.client.post(reverse("delete_all_notifications"))
        self.client.get(reverse("notification_list"))
        self.assertFalse(Notification.objects.filter(announcement=item, recipient=self.students[2]).exists())

    def test_legacy_classroom_notice_still_works(self):
        item = Announcement.objects.create(title="legacy classroom", message="old", audience="classroom",
                                           classroom=self.classrooms[0], publish_at=timezone.now())
        self.client.force_login(self.students[0])
        self.assertContains(self.client.get(reverse("student_dashboard")), item.title)
        self.client.force_login(self.students[1])
        self.assertNotContains(self.client.get(reverse("student_dashboard")), item.title)

    def test_scheduled_notice_delivered_after_publish_time(self):
        item = self.create(publish_at=timezone.localtime(timezone.now()+timedelta(days=1)).strftime("%Y-%m-%dT%H:%M"))
        self.assertFalse(Notification.objects.exists())
        item.publish_at = timezone.now()-timedelta(minutes=1)
        item.save()
        self.client.force_login(self.students[0])
        self.assertContains(self.client.get(reverse("notification_list")), item.title)
        self.assertEqual(Notification.objects.filter(announcement=item).count(), 1)
