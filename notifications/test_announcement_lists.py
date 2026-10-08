from datetime import timedelta
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from accounts.models import StudentProfile, TeacherProfile
from academic.models import AcademicYear, Classroom, Grade, Enrollment
from .models import Announcement, Notification

User=get_user_model()

class RecipientAnnouncementListTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.student=User.objects.create_user('student',role='student')
        cls.profile=StudentProfile.objects.create(user=cls.student)
        cls.teacher=User.objects.create_user('teacher',role='teacher')
        cls.teacher_profile=TeacherProfile.objects.create(user=cls.teacher)
        cls.language_teacher=User.objects.create_user('language',role='teacher')
        TeacherProfile.objects.create(user=cls.language_teacher,is_language_teacher=True)
        cls.other_teacher=User.objects.create_user('other',role='teacher')
        cls.other_profile=TeacherProfile.objects.create(user=cls.other_teacher)
        cls.manager=User.objects.create_user('manager',role='school_manager')
        year=AcademicYear.objects.create(title='1405',status='active')
        grade=Grade.objects.create(code='1',title='اول',order=1)
        cls.classroom=Classroom.objects.create(name='الف',academic_year=year,grade=grade,capacity=30)
        cls.other_classroom=Classroom.objects.create(name='ب',academic_year=year,grade=grade,capacity=30)
        Enrollment.objects.create(student=cls.profile,academic_year=year,classroom=cls.classroom)
        cls.older=Announcement.objects.create(title='Older announcement',message='Old body',audience='all',publish_at=timezone.now()-timedelta(days=3))
        cls.latest=Announcement.objects.create(title='Latest announcement',message='New body',audience='all',publish_at=timezone.now()-timedelta(days=1),image='announcements/example.png')
        cls.future=Announcement.objects.create(title='Future announcement',message='Future',audience='all',publish_at=timezone.now()+timedelta(days=1))
        cls.inactive=Announcement.objects.create(title='Inactive announcement',message='Inactive',audience='all',is_active=False,publish_at=timezone.now())

    def test_dashboards_only_show_latest_and_keep_notifications_for_all(self):
        for user,route in [(self.student,'student_dashboard'),(self.teacher,'teacher_dashboard'),(self.language_teacher,'teacher_language_dashboard')]:
            with self.subTest(route=route):
                self.client.force_login(user)
                response=self.client.get(reverse(route))
                self.assertContains(response,'Latest announcement')
                self.assertNotContains(response,'Older announcement')
                self.assertNotContains(response,'Future announcement')
                self.assertNotContains(response,'Inactive announcement')
                self.assertContains(response,reverse('recipient_announcement_list'))
                self.assertContains(response,self.latest.image.url)
                self.assertEqual(len(response.context['announcements']),1)
                self.assertEqual(Notification.objects.filter(recipient=user,announcement__isnull=False).count(),2)

    def test_full_list_keeps_older_items_images_and_newest_first(self):
        for user,back in [(self.student,'student_dashboard'),(self.teacher,'teacher_dashboard'),(self.language_teacher,'teacher_language_dashboard')]:
            self.client.force_login(user)
            response=self.client.get(reverse('recipient_announcement_list'))
            self.assertEqual(list(response.context['announcements']),[self.latest,self.older])
            self.assertLess(response.content.index(b'Latest announcement'),response.content.index(b'Older announcement'))
            self.assertContains(response,self.latest.image.url)
            self.assertContains(response,reverse(back))
            self.assertNotContains(response,'Future announcement')
            self.assertNotContains(response,'Inactive announcement')

    def test_targeted_notices_are_filtered_before_selecting_latest(self):
        teacher_notice=Announcement.objects.create(title='Private teacher announcement',message='T',audience='teachers',targeted=True,publish_at=timezone.now()-timedelta(hours=3))
        teacher_notice.teachers.add(self.teacher_profile)
        student_notice=Announcement.objects.create(title='Private class announcement',message='S',audience='students',targeted=True,publish_at=timezone.now()-timedelta(hours=2))
        student_notice.classrooms.add(self.classroom)
        hidden_notice=Announcement.objects.create(title='Other class secret',message='Hidden',audience='students',targeted=True,publish_at=timezone.now()-timedelta(hours=1))
        hidden_notice.classrooms.add(self.other_classroom)
        for user,route,latest,hidden in [(self.student,'student_dashboard',student_notice,teacher_notice),(self.teacher,'teacher_dashboard',teacher_notice,student_notice),(self.language_teacher,'teacher_language_dashboard',self.latest,teacher_notice)]:
            self.client.force_login(user)
            response=self.client.get(reverse(route))
            self.assertEqual(list(response.context['announcements']),[latest])
            response=self.client.get(reverse('recipient_announcement_list'))
            self.assertContains(response,latest.title)
            self.assertNotContains(response,hidden.title)
            self.assertNotContains(response,hidden_notice.title)

    def test_empty_dashboard_still_links_to_empty_list(self):
        Announcement.objects.all().delete()
        self.client.force_login(self.student)
        self.assertContains(self.client.get(reverse('student_dashboard')),reverse('recipient_announcement_list'))
        response=self.client.get(reverse('recipient_announcement_list'))
        self.assertContains(response,'اطلاعیه‌ای برای شما وجود ندارد.')

    def test_list_requires_login_and_recipient_role(self):
        self.assertEqual(self.client.get(reverse('recipient_announcement_list')).status_code,302)
        self.client.force_login(self.manager)
        self.assertEqual(self.client.get(reverse('recipient_announcement_list')).status_code,403)

    def test_deleting_notifications_does_not_delete_announcement_history(self):
        self.client.force_login(self.student)
        self.client.get(reverse('student_dashboard'))
        self.client.post(reverse('delete_all_notifications'))
        self.assertFalse(Notification.objects.filter(recipient=self.student).exists())
        response=self.client.get(reverse('recipient_announcement_list'))
        self.assertContains(response,'Latest announcement')
        self.assertContains(response,'Older announcement')
