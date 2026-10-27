import tempfile
from django.test import TestCase, override_settings, Client
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from academic.models import AcademicYear, Grade, Classroom, Enrollment, TeacherClassAssignment
from accounts.models import TeacherProfile, StudentProfile
from assignments.models import Assignment
from materials.models import EducationalMaterial


class TeacherContentActionsTests(TestCase):
    def setUp(self):
        media = tempfile.TemporaryDirectory()
        self.addCleanup(media.cleanup)
        settings = override_settings(MEDIA_ROOT=media.name)
        settings.enable()
        self.addCleanup(settings.disable)
        User = get_user_model()
        self.owner = User.objects.create_user('owner', role='teacher')
        self.other = User.objects.create_user('other', role='teacher')
        self.teacher = TeacherProfile.objects.create(user=self.owner)
        other = TeacherProfile.objects.create(user=self.other)
        self.student_user = User.objects.create_user('student', role='student')
        student = StudentProfile.objects.create(user=self.student_user)
        self.year = AcademicYear.objects.create(title='1405', status='active')
        grade = Grade.objects.create(code='1', title='اول', order=1)
        self.room = Classroom.objects.create(name='یاس', grade=grade, academic_year=self.year, capacity=30)
        for teacher in (self.teacher, other):
            TeacherClassAssignment.objects.create(teacher=teacher, classroom=self.room)
        Enrollment.objects.create(student=student, classroom=self.room, academic_year=self.year)
        self.assignment = Assignment.objects.create(title='Homework', teacher=self.teacher, classroom=self.room,
            file=SimpleUploadedFile('test.pdf', b'pdf'), image=SimpleUploadedFile('test.png', b'image'),
            video=SimpleUploadedFile('test.mp4', b'video'))
        self.material = EducationalMaterial.objects.create(title='Material', teacher=self.teacher,
            content_type='image', file=SimpleUploadedFile('material.png', b'material'))
        self.material.classrooms.add(self.room)

    def attachment_urls(self):
        return [reverse('download_material', args=[self.material.pk])] + [
            reverse('download_assignment_attachment', args=[self.assignment.pk, kind])
            for kind in ('file', 'image', 'video')]

    def test_all_lists_have_edit_delete_and_all_attachments(self):
        self.client.force_login(self.owner)
        for route, args, objects in [
            ('teacher_assignment_list', [], [self.assignment]),
            ('teacher_material_list', [], [self.material]),
            ('teacher_class_detail', [self.room.pk], [self.assignment, self.material]),
            ('teacher_class_assignment_list', [self.room.pk], [self.assignment]),
            ('teacher_class_material_list', [self.room.pk], [self.material]),
        ]:
            page = self.client.get(reverse(route, args=args))
            for obj in objects:
                kind = 'assignment' if isinstance(obj, Assignment) else 'material'
                for action in ('edit', 'delete'):
                    self.assertContains(page, reverse(f'{action}_{kind}', args=[obj.pk]))
            if self.assignment in objects:
                for kind in ('image', 'video'):
                    self.assertContains(page, reverse('download_assignment_attachment', args=[self.assignment.pk, kind]))
            if self.material in objects:
                self.assertContains(page, reverse('download_material', args=[self.material.pk]))

    def test_owner_and_enrolled_student_can_download(self):
        for user in (self.owner, self.student_user):
            self.client.force_login(user)
            for url in self.attachment_urls():
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)
                self.assertTrue(b''.join(response.streaming_content))
                response.close()

    def test_other_teacher_and_unrelated_student_cannot_download(self):
        User = get_user_model()
        outsider = User.objects.create_user('outsider', role='student')
        StudentProfile.objects.create(user=outsider)
        for user in (self.other, outsider):
            self.client.force_login(user)
            for url in self.attachment_urls():
                self.assertEqual(self.client.get(url).status_code, 404)

    def test_delete_requires_owner_confirmation_and_csrf(self):
        for kind, obj in [('assignment', self.assignment), ('material', self.material)]:
            url = reverse(f'delete_{kind}', args=[obj.pk])
            self.client.force_login(self.other)
            self.assertEqual(self.client.post(url).status_code, 404)
            self.client.force_login(self.owner)
            self.assertContains(self.client.get(url), 'csrfmiddlewaretoken')
            self.assertTrue(type(obj).objects.filter(pk=obj.pk).exists())
            secure = Client(enforce_csrf_checks=True)
            secure.force_login(self.owner)
            self.assertEqual(secure.post(url).status_code, 403)
            self.assertEqual(self.client.post(url).status_code, 302)
            self.assertFalse(type(obj).objects.filter(pk=obj.pk).exists())

    def test_invalid_or_missing_attachment_and_archived_year(self):
        self.client.force_login(self.owner)
        url = reverse('download_assignment_attachment', args=[self.assignment.pk, 'teacher'])
        self.assertEqual(self.client.get(url).status_code, 404)
        self.assignment.image = ''
        self.assignment.save()
        self.assertEqual(self.client.get(self.attachment_urls()[2]).status_code, 404)
        self.year.status = 'archived'
        self.year.save()
        for url in self.attachment_urls():
            self.assertEqual(self.client.get(url).status_code, 404)
