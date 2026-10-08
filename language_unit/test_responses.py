import tempfile
from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from accounts.models import TeacherProfile, StudentProfile
from academic.models import AcademicYear, Grade, Classroom
from assignments.models import Assignment, AssignmentSubmission
from .models import LanguageGroup, LanguageMaterial, LanguageAssignment, LanguageAssignmentSubmission


class ResponseAccessTests(TestCase):
    def setUp(self):
        self.media = tempfile.TemporaryDirectory()
        self.addCleanup(self.media.cleanup)
        self.settings_override = override_settings(MEDIA_ROOT=self.media.name)
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)
        User = get_user_model()
        self.manager = User.objects.create_user('manager', role='school_manager')
        self.owner = User.objects.create_user('owner', role='teacher')
        self.other = User.objects.create_user('other', role='teacher')
        self.student_user = User.objects.create_user('student', role='student')
        self.teacher = TeacherProfile.objects.create(user=self.owner, is_language_teacher=True)
        self.other_teacher = TeacherProfile.objects.create(user=self.other, is_language_teacher=True)
        self.student = StudentProfile.objects.create(user=self.student_user)
        self.year = AcademicYear.objects.create(title='1405', status='active')
        self.group = LanguageGroup.objects.create(title='English', academic_year=self.year)
        self.group.teachers.add(self.teacher, self.other_teacher)
        self.group.students.add(self.student)
        self.assignment = LanguageAssignment.objects.create(group=self.group, teacher=self.teacher, title='Homework', description='Instructions')
        self.material = LanguageMaterial.objects.create(group=self.group, teacher=self.teacher, title='Lesson', content='Text')
        self.submission = LanguageAssignmentSubmission.objects.create(assignment=self.assignment, student=self.student,
            answer_text='Student answer', file=SimpleUploadedFile('answer.txt', b'answer bytes'))

    def test_owner_and_manager_can_read_text_and_download_exact_file(self):
        for user in [self.owner, self.manager]:
            self.client.force_login(user)
            page = self.client.get(reverse('language_assignment_submissions', args=[self.assignment.pk]))
            self.assertContains(page, 'Student answer')
            self.assertContains(page, reverse('download_language_submission', args=[self.submission.pk]))
            response = self.client.get(reverse('download_language_submission', args=[self.submission.pk]))
            self.assertEqual(response.status_code, 200)
            self.assertEqual(b''.join(response.streaming_content), b'answer bytes')
            self.assertIn('attachment;', response['Content-Disposition'])

    def test_other_group_teacher_and_student_cannot_read_responses(self):
        for user in [self.other, self.student_user]:
            self.client.force_login(user)
            for route, pk in [('language_assignment_submissions', self.assignment.pk), ('download_language_submission', self.submission.pk)]:
                self.assertIn(self.client.get(reverse(route, args=[pk])).status_code, [403, 404])

    def test_inactive_group_blocks_teacher_but_preserves_manager_access(self):
        self.group.is_active = False
        self.group.save()
        self.client.force_login(self.owner)
        self.assertEqual(self.client.get(reverse('download_language_submission', args=[self.submission.pk])).status_code, 404)
        self.client.force_login(self.manager)
        self.assertEqual(self.client.get(reverse('language_assignment_submissions', args=[self.assignment.pk])).status_code, 200)

    def test_missing_response_file_returns_404(self):
        self.submission.file.storage.delete(self.submission.file.name)
        self.client.force_login(self.owner)
        self.assertEqual(self.client.get(reverse('download_language_submission', args=[self.submission.pk])).status_code, 404)

    def test_edit_and_delete_controls_and_owner_only_post_deletion(self):
        for kind, item in [('material', self.material), ('assignment', self.assignment)]:
            self.client.force_login(self.owner)
            page = self.client.get(reverse('teacher_language_' + kind + '_list'))
            self.assertContains(page, reverse('edit_language_' + kind, args=[item.pk]))
            url = reverse('delete_language_' + kind, args=[item.pk])
            self.assertContains(page, url)
            self.assertEqual(self.client.get(url).status_code, 200)
            self.assertTrue(type(item).objects.filter(pk=item.pk).exists())
            self.client.force_login(self.other)
            self.assertEqual(self.client.post(url).status_code, 404)
            self.assertEqual(self.client.get(reverse('edit_language_' + kind, args=[item.pk])).status_code, 404)
            self.client.force_login(self.owner)
            self.assertEqual(self.client.post(url).status_code, 302)
            self.assertFalse(type(item).objects.filter(pk=item.pk).exists())

    def test_manager_can_read_school_responses_without_teacher_profile(self):
        grade = Grade.objects.create(code='1', title='First', order=1)
        classroom = Classroom.objects.create(name='A', grade=grade, academic_year=self.year, capacity=30)
        assignment = Assignment.objects.create(title='School homework', classroom=classroom, teacher=self.teacher)
        submission = AssignmentSubmission.objects.create(assignment=assignment, student=self.student,
            answer_text='School answer', file=SimpleUploadedFile('school.txt', b'school bytes'))
        self.client.force_login(self.manager)
        page = self.client.get(reverse('manager_class_assignments', args=[classroom.pk]))
        self.assertContains(page, reverse('assignment_submissions', args=[assignment.pk]))
        page = self.client.get(reverse('assignment_submissions', args=[assignment.pk]))
        self.assertContains(page, 'School answer')
        self.assertNotContains(page, reverse('evaluate_submission', args=[submission.pk]))
        response = self.client.get(reverse('download_submission_file', args=[submission.pk]))
        self.assertEqual(b''.join(response.streaming_content), b'school bytes')
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(reverse('download_submission_file', args=[submission.pk])).status_code, 403)
