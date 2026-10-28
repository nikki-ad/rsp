import io
import tempfile
from PIL import Image
from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from accounts.models import TeacherProfile, StudentProfile
from academic.models import AcademicYear, Grade, Classroom, Enrollment
from assignments.models import Assignment, AssignmentSubmission
from assignments.forms import AssignmentEvaluationForm
from language_unit.forms import LanguageFeedbackForm
from language_unit.models import LanguageGroup, LanguageAssignment, LanguageAssignmentSubmission
from notifications.models import Notification


class TeacherFeedbackTests(TestCase):
    def setUp(self):
        media = tempfile.TemporaryDirectory()
        self.addCleanup(media.cleanup)
        setting = override_settings(MEDIA_ROOT=media.name)
        setting.enable()
        self.addCleanup(setting.disable)
        User = get_user_model()
        self.owner = User.objects.create_user('teacher', role='teacher')
        self.language_owner = User.objects.create_user('language', role='teacher')
        self.other = User.objects.create_user('other', role='teacher')
        self.student_user = User.objects.create_user('student', role='student')
        self.other_student_user = User.objects.create_user('otherstudent', role='student')
        self.manager = User.objects.create_user('manager', role='school_manager')
        teacher = TeacherProfile.objects.create(user=self.owner)
        lt = TeacherProfile.objects.create(user=self.language_owner, is_language_teacher=True)
        ot = TeacherProfile.objects.create(user=self.other)
        self.student = StudentProfile.objects.create(user=self.student_user)
        other_student = StudentProfile.objects.create(user=self.other_student_user)
        self.year = AcademicYear.objects.create(title='1405', status='active')
        grade = Grade.objects.create(code='1', title='First', order=1)
        classroom = Classroom.objects.create(name='A', grade=grade, academic_year=self.year, capacity=30)
        for student in (self.student, other_student):
            Enrollment.objects.create(student=student, academic_year=self.year, classroom=classroom)
        group = LanguageGroup.objects.create(title='English', academic_year=self.year)
        group.teachers.add(lt, ot)
        group.students.add(self.student, other_student)
        school = Assignment.objects.create(title='School', teacher=teacher, classroom=classroom)
        language = LanguageAssignment.objects.create(title='Language', teacher=lt, group=group)
        self.school = AssignmentSubmission.objects.create(assignment=school, student=self.student, answer_text='answer')
        self.language = LanguageAssignmentSubmission.objects.create(assignment=language, student=self.student, answer_text='answer')
        self.cases = [(self.school, self.owner, AssignmentEvaluationForm, 'evaluate_submission', 'download_teacher_feedback', 'student_assignment_list'),
                      (self.language, self.language_owner, LanguageFeedbackForm, 'language_submission_feedback', 'download_language_feedback', 'student_language_dashboard')]

    def test_all_four_modes_save_caption_and_notify_student(self):
        for sub, owner, form_class, route, download, listing in self.cases:
            self.client.force_login(owner)
            url = reverse(route, args=[sub.pk])
            self.assertContains(self.client.get(url), 'multipart/form-data')
            for kind in ('text', 'file', 'image', 'video'):
                data = {'feedback_type': kind, 'teacher_feedback': 'Teacher caption\nsecond line'}
                if kind == 'image':
                    stream = io.BytesIO()
                    Image.new('RGB', (2, 2)).save(stream, format='PNG')
                    data['feedback_file'] = SimpleUploadedFile('reply.png', stream.getvalue(), content_type='image/png')
                elif kind != 'text':
                    data['feedback_file'] = SimpleUploadedFile('reply.mp4' if kind == 'video' else 'reply.pdf', b'reply bytes')
                self.assertEqual(self.client.post(url, data).status_code, 302)
                sub.refresh_from_db()
                self.assertEqual(sub.feedback_type, kind)
                self.assertEqual(sub.teacher_feedback, data['teacher_feedback'])
                self.client.force_login(self.student_user)
                page = self.client.get(reverse(listing))
                self.assertContains(page, 'Teacher caption<br>second line', html=False)
                self.assertContains(page, '<details', html=False)
                if kind != 'text':
                    response = self.client.get(reverse(download, args=[sub.pk]))
                    self.assertEqual(response.status_code, 200)
                    self.assertTrue(b''.join(response.streaming_content))
                self.client.force_login(owner)
        self.assertEqual(Notification.objects.filter(recipient=self.student_user).count(), 8)

    def test_text_mode_removes_old_attachment_and_ignores_posted_file(self):
        for sub, owner, form_class, route, download, listing in self.cases:
            sub.feedback_type = 'file'
            sub.feedback_file = SimpleUploadedFile('old.pdf', b'old')
            sub.save()
            form = form_class({'feedback_type': 'text', 'teacher_feedback': 'Only text'},
                {'feedback_file': SimpleUploadedFile('new.pdf', b'new')}, instance=sub)
            self.assertTrue(form.is_valid(), form.errors)
            form.save()
            sub.refresh_from_db()
            self.assertFalse(sub.feedback_file)
            self.client.force_login(self.student_user)
            self.assertEqual(self.client.get(reverse(download, args=[sub.pk])).status_code, 404)

    def test_validation_rejects_empty_wrong_media_and_oversized_videos(self):
        for sub, owner, form_class, route, download, listing in self.cases:
            self.assertFalse(form_class({'feedback_type': 'text', 'teacher_feedback': '  '}, instance=sub).is_valid())
            self.assertFalse(form_class({'feedback_type': 'file'}, instance=sub).is_valid())
            bad = form_class({'feedback_type': 'image'}, {'feedback_file': SimpleUploadedFile('bad.png', b'not image')}, instance=sub)
            self.assertFalse(bad.is_valid())
            for kind in ('video', 'file'):
                bad = form_class({'feedback_type': kind}, {'feedback_file': SimpleUploadedFile('large.mp4', b'x' * (20*1024*1024+1))}, instance=sub)
                self.assertFalse(bad.is_valid())

    def test_edit_retains_attachment_but_type_change_requires_new_upload(self):
        for sub, owner, form_class, route, download, listing in self.cases:
            sub.feedback_type = 'file'
            sub.feedback_file = SimpleUploadedFile('reply.pdf', b'reply')
            sub.save()
            form = form_class({'feedback_type': 'file', 'teacher_feedback': 'Edited'}, instance=sub)
            self.assertTrue(form.is_valid(), form.errors)
            form.save()
            self.assertFalse(form_class({'feedback_type': 'video', 'teacher_feedback': 'Edited'}, instance=sub).is_valid())

    def test_only_owner_can_write_and_only_own_student_can_download(self):
        for sub, owner, form_class, route, download, listing in self.cases:
            sub.feedback_type = 'file'
            sub.feedback_file = SimpleUploadedFile('private.pdf', b'private')
            sub.save()
            for user in (self.other, self.student_user, self.other_student_user, self.manager):
                self.client.force_login(user)
                self.assertIn(self.client.post(reverse(route, args=[sub.pk]), {'feedback_type': 'text', 'teacher_feedback': 'overwrite'}).status_code, (403, 404))
            for user in (self.other, self.other_student_user):
                self.client.force_login(user)
                self.assertIn(self.client.get(reverse(download, args=[sub.pk])).status_code, (403, 404))
            for user in (owner, self.student_user, self.manager):
                self.client.force_login(user)
                response = self.client.get(reverse(download, args=[sub.pk]))
                self.assertEqual(response.status_code, 200)
                self.assertEqual(b''.join(response.streaming_content), b'private')

    def test_invalid_async_post_returns_errors_without_saving(self):
        for sub, owner, form_class, route, download, listing in self.cases:
            self.client.force_login(owner)
            response = self.client.post(reverse(route, args=[sub.pk]), {'feedback_type': 'file'}, HTTP_X_RSP_UPLOAD='1')
            self.assertEqual(response.status_code, 422)
            self.assertIn('feedback_file', response.json()['errors'])
            sub.refresh_from_db()
            self.assertFalse(sub.has_feedback)

    def test_school_evaluation_without_feedback_remains_supported(self):
        form = AssignmentEvaluationForm({'evaluation': 'good', 'feedback_type': 'text'}, instance=self.school)
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        self.school.refresh_from_db()
        self.assertEqual(self.school.evaluation, 'good')

    def test_successful_async_save_and_archived_access(self):
        for sub, owner, form_class, route, download, listing in self.cases:
            self.client.force_login(owner)
            response = self.client.post(reverse(route, args=[sub.pk]),
                {'feedback_type': 'file', 'teacher_feedback': 'Caption',
                 'feedback_file': SimpleUploadedFile('reply.pdf', b'reply')}, HTTP_X_RSP_UPLOAD='1')
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.json()['success'])
            self.assertIn('redirect_url', response.json())
        self.year.status = 'archived'
        self.year.save()
        for sub, owner, form_class, route, download, listing in self.cases:
            for user in (owner, self.student_user):
                self.client.force_login(user)
                self.assertEqual(self.client.get(reverse(download, args=[sub.pk])).status_code, 404)
            self.client.force_login(owner)
            self.assertEqual(self.client.get(reverse(route, args=[sub.pk])).status_code, 404)
