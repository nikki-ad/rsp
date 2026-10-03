from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, Client
from django.urls import reverse

from assignments.models import Assignment
from core import test_uploads_and_dates as fixtures
from core.upload_progress import SUCCESS_MESSAGE
from language_unit.models import LanguageAssignment, LanguageMaterial
from materials.models import EducationalMaterial
from notifications.models import Announcement


class UploadProgressTests(TestCase):
    setUpTestData = classmethod(fixtures.UploadTests.setUpTestData.__func__)
    setUp = fixtures.UploadTests.setUp
    video = fixtures.UploadTests.video
    image = fixtures.UploadTests.image

    def cases(self):
        return [
            ('create_assignment', [self.classroom.pk], {'title': 'تکلیف', 'video': self.video()}, Assignment, 'edit_assignment'),
            ('create_class_material', [self.classroom.pk], {'title': 'مطلب کلاس', 'content_type': 'video', 'file': self.video()}, EducationalMaterial, 'edit_material'),
            ('create_material', [], {'title': 'مطلب', 'classrooms': [str(self.classroom.pk)], 'content_type': 'video', 'file': self.video()}, EducationalMaterial, 'edit_material'),
            ('create_language_assignment', [self.group.pk], {'title': 'زبان', 'video': self.video()}, LanguageAssignment, 'edit_language_assignment'),
            ('create_language_material', [self.group.pk], {'title': 'زبان', 'content_type': 'video', 'file': self.video()}, LanguageMaterial, 'edit_language_material'),
        ]

    def assert_success(self, response):
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['success'])
        self.assertEqual(response.json()['message'], SUCCESS_MESSAGE)
        self.assertTrue(response.json()['redirect_url'].startswith('/'))
        page = self.client.get(response.json()['redirect_url'])
        self.assertContains(page, SUCCESS_MESSAGE, count=1)

    def test_teacher_create_and_edit_confirm_saved_files(self):
        self.client.force_login(self.tuser)
        for route, args, data, model, edit_route in self.cases():
            with self.subTest(route=route):
                self.assertContains(self.client.get(reverse(route, args=args)), 'data-upload-progress')
                self.assert_success(self.client.post(reverse(route, args=args), data, HTTP_X_RSP_UPLOAD='1'))
                item = model.objects.get(title=data['title'])
                file_field = 'video' if 'video' in data else 'file'
                self.assertTrue(getattr(item, file_field).storage.exists(getattr(item, file_field).name))
                original = getattr(item, file_field).name
                edit_data = {key: value for key, value in data.items() if key not in ('video', 'file')}
                if model is EducationalMaterial:
                    edit_data['classrooms'] = [str(self.classroom.pk)]
                edit_data['title'] += ' اصلاح'
                self.assert_success(self.client.post(reverse(edit_route, args=[item.pk]), edit_data, HTTP_X_RSP_UPLOAD='1'))
                item.refresh_from_db()
                self.assertEqual(getattr(item, file_field).name, original)

    def test_validation_returns_errors_without_saving(self):
        self.client.force_login(self.tuser)
        for route, args, data, model, _ in self.cases():
            with self.subTest(route=route):
                data['title'] = ''
                response = self.client.post(reverse(route, args=args), data, HTTP_X_RSP_UPLOAD='1')
                self.assertEqual(response.status_code, 422)
                self.assertFalse(response.json()['success'])
                self.assertIn('title', response.json()['errors'])
                self.assertEqual(model.objects.count(), 0)
                self.assertEqual(list(get_messages(response.wsgi_request)), [])

    def test_announcement_create_edit_and_invalid_image(self):
        manager = get_user_model().objects.create_user(username='progress_manager', role='school_manager')
        self.client.force_login(manager)
        data = {'title': 'خبر', 'message': 'متن', 'audience': 'all', 'publish_at': '1405/07/11 08:00', 'is_active': 'on', 'image': self.image()}
        self.assertContains(self.client.get(reverse('announcement_create')), 'data-upload-progress')
        self.assert_success(self.client.post(reverse('announcement_create'), data, HTTP_X_RSP_UPLOAD='1'))
        item = Announcement.objects.get()
        self.assertTrue(item.image.storage.exists(item.image.name))
        original = item.image.name
        data.pop('image')
        self.assert_success(self.client.post(reverse('announcement_edit', args=[item.pk]), data, HTTP_X_RSP_UPLOAD='1'))
        data['image'] = SimpleUploadedFile('bad.png', b'not an image', content_type='image/png')
        response = self.client.post(reverse('announcement_edit', args=[item.pk]), data, HTTP_X_RSP_UPLOAD='1')
        self.assertEqual(response.status_code, 422)
        self.assertIn('image', response.json()['errors'])
        item.refresh_from_db()
        self.assertEqual(item.image.name, original)
        self.assertEqual(Announcement.objects.count(), 1)

    def test_regular_post_still_redirects_with_success_message(self):
        self.client.force_login(self.tuser)
        response = self.client.post(reverse('create_assignment', args=[self.classroom.pk]), {'title': 'بدون جاوااسکریپت', 'video': self.video()})
        self.assertEqual(response.status_code, 302)
        self.assertContains(self.client.get(response.url), SUCCESS_MESSAGE)

    def test_upload_header_does_not_bypass_authorization_or_csrf(self):
        url = reverse('create_assignment', args=[self.classroom.pk])
        response = self.client.post(url, {'title': 'ممنوع'}, HTTP_X_RSP_UPLOAD='1')
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response.url)
        self.client.force_login(self.suser)
        self.assertEqual(self.client.post(url, {'title': 'ممنوع'}, HTTP_X_RSP_UPLOAD='1').status_code, 403)
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.tuser)
        self.assertEqual(csrf_client.post(url, {'title': 'بدون توکن'}, HTTP_X_RSP_UPLOAD='1').status_code, 403)
        self.assertEqual(Assignment.objects.count(), 0)

    def test_unrelated_generic_form_is_not_enabled(self):
        manager = get_user_model().objects.create_user(username='progress_admin', role='school_manager')
        self.client.force_login(manager)
        self.assertNotContains(self.client.get(reverse('grade_create')), 'data-upload-progress')
