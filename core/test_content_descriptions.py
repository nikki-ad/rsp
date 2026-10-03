from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from core import test_uploads_and_dates as uploads
from materials.forms import EducationalMaterialCreateForm
from materials.models import EducationalMaterial
from language_unit.forms import LanguageMaterialForm, LanguageAssignmentForm
from language_unit.models import LanguageMaterial, LanguageAssignment
from assignments.forms import AssignmentCreateForm
from assignments.models import Assignment


class ContentDescriptionTests(TestCase):
    setUpTestData = classmethod(uploads.UploadTests.setUpTestData.__func__)
    setUp = uploads.UploadTests.setUp
    image = uploads.UploadTests.image
    video = uploads.UploadTests.video

    def attachment(self, kind):
        return self.image() if kind == 'image' else self.video() if kind == 'video' else SimpleUploadedFile('lesson.pdf', b'pdf')

    def test_material_types_accept_optional_description_and_require_primary_content(self):
        for form_class, kwargs in [(EducationalMaterialCreateForm, {'teacher': self.teacher}), (LanguageMaterialForm, {})]:
            for kind in ['text', 'file', 'image', 'video', 'link']:
                for text in ['Study pages 3 to 5', '']:
                    with self.subTest(form=form_class.__name__, kind=kind, text=text):
                        data = {'title': 'Lesson', 'content_type': kind, 'content': text, 'classrooms': [str(self.classroom.pk)]}
                        files = {}
                        if kind == 'link':
                            data['link'] = 'https://example.com/lesson'
                        elif kind != 'text':
                            files['file'] = self.attachment(kind)
                        form = form_class(data, files, **kwargs)
                        self.assertEqual(form.is_valid(), kind != 'text' or bool(text), form.errors)
                data = {'title': 'Empty', 'content_type': kind, 'classrooms': [str(self.classroom.pk)]}
                self.assertFalse(form_class(data, **kwargs).is_valid())

    def test_material_upload_and_edit_preserve_file_and_show_description_to_all_roles(self):
        self.client.force_login(self.tuser)
        self.assertEqual(self.client.post(reverse('create_material'), {
            'title': 'File lesson', 'content_type': 'file', 'content': 'Original instructions',
            'classrooms': [str(self.classroom.pk)], 'file': self.attachment('file'),
        }).status_code, 302)
        material = EducationalMaterial.objects.get()
        original_file = material.file.name
        self.assertEqual(self.client.post(reverse('edit_material', args=[material.pk]), {
            'title': 'File lesson', 'content_type': 'file', 'content': 'Read pages 3\nThen solve <script>evil()</script>',
            'classrooms': [str(self.classroom.pk)],
        }).status_code, 302)
        material.refresh_from_db()
        self.assertEqual(material.file.name, original_file)
        routes = [
            (self.suser, 'student_material_list', []), (self.suser, 'student_dashboard', []),
            (self.tuser, 'teacher_class_detail', [self.classroom.pk]),
            (self.tuser, 'teacher_class_material_list', [self.classroom.pk]),
            (self.tuser, 'teacher_material_list', []),
            (get_user_model().objects.create_user('description_admin', role='super_admin'), 'manager_class_materials', [self.classroom.pk]),
        ]
        for user, route, args in routes:
            self.client.force_login(user)
            page = self.client.get(reverse(route, args=args))
            self.assertContains(page, 'Read pages 3<br>Then solve &lt;script&gt;evil()&lt;/script&gt;')
            self.assertNotContains(page, '<script>evil()</script>')

    def test_language_material_description_is_saved_edited_and_visible(self):
        self.client.force_login(self.tuser)
        self.assertEqual(self.client.post(reverse('create_language_material', args=[self.group.pk]), {
            'title': 'Language file', 'content_type': 'file', 'content': 'Read the file', 'file': self.attachment('file'),
        }).status_code, 302)
        material = LanguageMaterial.objects.get()
        original_file = material.file.name
        self.assertEqual(self.client.post(reverse('edit_language_material', args=[material.pk]), {
            'title': 'Language file', 'content_type': 'file', 'content': 'Updated instructions',
        }).status_code, 302)
        material.refresh_from_db()
        self.assertEqual(material.file.name, original_file)
        self.assertContains(self.client.get(reverse('language_group_detail', args=[self.group.pk])), 'Updated instructions')
        self.client.force_login(self.suser)
        page = self.client.get(reverse('student_language_dashboard'))
        self.assertContains(page, 'Updated instructions')
        self.assertContains(page, reverse('download_language_material', args=[material.pk]))

    def test_assignments_allow_text_attachments_or_both_and_reject_empty(self):
        for form_class in [AssignmentCreateForm, LanguageAssignmentForm]:
            for text in ['', 'Instructions']:
                for kind in [None, 'file', 'image', 'video']:
                    with self.subTest(form=form_class.__name__, text=text, kind=kind):
                        files = {kind: self.attachment(kind)} if kind else {}
                        form = form_class({'title': 'Homework', 'description': text}, files)
                        self.assertEqual(form.is_valid(), bool(text or kind), form.errors)
            self.assertFalse(form_class({'title': 'Blank', 'description': ' \n '}).is_valid())

    def test_assignment_edit_keeps_attachments_and_allows_optional_text(self):
        for model, form_class, relations in [
            (Assignment, AssignmentCreateForm, {'classroom': self.classroom}),
            (LanguageAssignment, LanguageAssignmentForm, {'group': self.group}),
        ]:
            item = model.objects.create(title='Homework', teacher=self.teacher, file=self.attachment('file'), **relations)
            original = item.file.name
            form = form_class({'title': 'Homework', 'description': 'Updated\nInstructions'}, instance=item)
            self.assertTrue(form.is_valid(), form.errors)
            form.save()
            item.refresh_from_db()
            self.assertEqual(item.file.name, original)
            self.assertEqual(item.description, 'Updated\nInstructions')
            clear_form = form_class({'title': 'Homework', 'description': '', 'file-clear': 'on'}, instance=item)
            self.assertFalse(clear_form.is_valid())

    def test_assignment_description_and_attachment_are_visible_together(self):
        assignment = Assignment.objects.create(title='Homework', teacher=self.teacher, classroom=self.classroom,
            description='Read page 3\nSolve exercise 2', file=self.attachment('file'))
        language_assignment = LanguageAssignment.objects.create(title='Homework', teacher=self.teacher, group=self.group,
            description='Read page 3\nSolve exercise 2', file=self.attachment('file'))
        self.client.force_login(self.suser)
        for route, args in [('student_assignment_list', []), ('student_dashboard', []), ('submit_assignment', [assignment.pk]), ('student_language_dashboard', [])]:
            page = self.client.get(reverse(route, args=args))
            self.assertContains(page, 'Read page 3<br>Solve exercise 2')
            download = reverse('download_language_assignment', args=[language_assignment.pk, 'file']) if route == 'student_language_dashboard' else reverse('download_assignment_file', args=[assignment.pk])
            self.assertContains(page, download)
