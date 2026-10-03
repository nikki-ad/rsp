from datetime import date, datetime, timezone as dt_timezone
from io import BytesIO
from tempfile import TemporaryDirectory

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, SimpleTestCase, override_settings
from django.urls import reverse
from PIL import Image

from academic.models import AcademicYear, Grade, Classroom, Enrollment, TeacherClassAssignment
from accounts.models import StudentProfile, TeacherProfile
from assignments.models import Assignment
from assignments.forms import AssignmentCreateForm
from materials.forms import EducationalMaterialCreateForm
from materials.models import EducationalMaterial
from language_unit.forms import LanguageAssignmentForm, LanguageMaterialForm
from language_unit.models import LanguageGroup, LanguageAssignment, LanguageMaterial
from core.jalali import JalaliDateField, JalaliDateTimeField, JalaliDateInput, jalali_format
from core.uploads import MAX_VIDEO_SIZE


class JalaliTests(SimpleTestCase):
    def test_conversion_and_persian_digits(self):
        self.assertEqual(jalali_format(date(2026, 10, 3)), '1405/07/11')
        self.assertEqual(JalaliDateField().clean('۱۴۰۵/۰۷/۱۱'), date(2026, 10, 3))
        self.assertEqual(JalaliDateField().clean('١٤٠٥/٠٧/١١'), date(2026, 10, 3))
        self.assertEqual(JalaliDateInput().format_value(date(2026, 10, 3)), '1405/07/11')
        self.assertEqual(JalaliDateField().clean('2026-10-03'), date(2026, 10, 3))

    def test_leap_day_and_invalid_date(self):
        self.assertEqual(JalaliDateField().clean('1403/12/30'), date(2025, 3, 20))
        for value in ['1404/12/30', '1405/07/31', '1405/13/01']:
            with self.assertRaises(Exception):
                JalaliDateField().clean(value)

    def test_local_datetime(self):
        parsed = JalaliDateTimeField().clean('۱۴۰۵/۰۷/۱۱ ۱۸:۳۰')
        self.assertEqual(parsed.astimezone(dt_timezone.utc), datetime(2026, 10, 3, 15, tzinfo=dt_timezone.utc))
        self.assertEqual(jalali_format(parsed, True), '1405/07/11 18:30')


class UploadTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.tuser = User.objects.create_user(username='media_teacher', role='teacher')
        cls.teacher = TeacherProfile.objects.create(user=cls.tuser)
        cls.suser = User.objects.create_user(username='media_student', role='student')
        cls.student = StudentProfile.objects.create(user=cls.suser)
        cls.outsider = User.objects.create_user(username='outsider', role='student')
        StudentProfile.objects.create(user=cls.outsider)
        cls.year = AcademicYear.objects.create(title='1405', status='active')
        cls.grade = Grade.objects.create(code='1', title='اول', order=1)
        cls.classroom = Classroom.objects.create(academic_year=cls.year, grade=cls.grade, name='یاس', capacity=30)
        Enrollment.objects.create(academic_year=cls.year, classroom=cls.classroom, student=cls.student)
        TeacherClassAssignment.objects.create(classroom=cls.classroom, teacher=cls.teacher)
        cls.group = LanguageGroup.objects.create(title='زبان', academic_year=cls.year)
        cls.group.students.add(cls.student)
        cls.group.teachers.add(cls.teacher)

    def setUp(self):
        media = TemporaryDirectory()
        self.addCleanup(media.cleanup)
        override = override_settings(MEDIA_ROOT=media.name)
        override.enable()
        self.addCleanup(override.disable)

    def video(self, size=16):
        return SimpleUploadedFile('lesson.mp4', b'x' * size, content_type='video/mp4')

    def image(self):
        output = BytesIO()
        Image.new('RGB', (4,4), 'pink').save(output, 'PNG')
        return SimpleUploadedFile('lesson.png', output.getvalue(), content_type='image/png')

    def test_all_assignment_attachments_visible_and_downloadable(self):
        self.client.force_login(self.tuser)
        response = self.client.post(reverse('create_assignment', args=[self.classroom.pk]),
            {'title':'تکلیف فایل‌دار', 'file':SimpleUploadedFile('lesson.pdf', b'pdf data'), 'image':self.image(), 'video':self.video()})
        self.assertEqual(response.status_code,302)
        assignment = Assignment.objects.get()
        self.client.force_login(self.suser)
        for route in ['student_dashboard','student_assignment_list','submit_assignment']:
            url = reverse(route,args=[assignment.pk]) if route=='submit_assignment' else reverse(route)
            page = self.client.get(url)
            for kind in ['file','image','video']:
                self.assertContains(page,reverse('download_assignment_attachment',args=[assignment.pk,kind]) if kind!='file' else reverse('download_assignment_file',args=[assignment.pk]))
        for kind in ['file','image','video']:
            url=reverse('download_assignment_attachment',args=[assignment.pk,kind])
            result=self.client.get(url)
            self.assertEqual(result.status_code,200)
            self.assertIn('attachment', result['Content-Disposition'])
            self.assertTrue(b''.join(result.streaming_content))
            self.client.force_login(self.outsider)
            self.assertEqual(self.client.get(url).status_code,404)
            self.client.force_login(self.suser)

    def test_video_limit_boundary_and_generic_file_bypass(self):
        for form_class in [AssignmentCreateForm, LanguageAssignmentForm]:
            form=form_class({'title':'فیلم'}, {'video':self.video(MAX_VIDEO_SIZE)})
            self.assertTrue(form.is_valid(),form.errors)
            form=form_class({'title':'فیلم'}, {'video':self.video(MAX_VIDEO_SIZE+1)})
            self.assertFalse(form.is_valid())
            self.assertIn('video',form.errors)
            form=form_class({'title':'فیلم'}, {'file':self.video(MAX_VIDEO_SIZE+1)})
            self.assertFalse(form.is_valid())
            self.assertIn('file',form.errors)

    def test_material_video_limit_and_download(self):
        self.client.force_login(self.tuser)
        response=self.client.post(reverse('create_material'),{'title':'فیلم', 'content_type':'video', 'classrooms':[str(self.classroom.pk)],'file':self.video()})
        self.assertEqual(response.status_code,302)
        material=EducationalMaterial.objects.get()
        self.client.force_login(self.suser)
        self.assertContains(self.client.get(reverse('student_material_list')), reverse('download_material',args=[material.pk]))
        result=self.client.get(reverse('download_material',args=[material.pk]))
        self.assertEqual(b''.join(result.streaming_content),b'x'*16)
        for form_class, kwargs in [(EducationalMaterialCreateForm,{'teacher':self.teacher}), (LanguageMaterialForm,{})]:
            data={'title':'فیلم','content_type':'video','classrooms':[str(self.classroom.pk)]}
            form=form_class(data,{'file':self.video(MAX_VIDEO_SIZE+1)},**kwargs)
            self.assertFalse(form.is_valid())
            self.assertIn('file',form.errors)

    def test_media_type_rejects_wrong_file_kind(self):
        for form_class, kwargs in [(EducationalMaterialCreateForm, {"teacher":self.teacher}), (LanguageMaterialForm,{})]:
            for kind in ["video","image"]:
                form=form_class({"title":"wrong kind", "content_type":kind,"classrooms":[str(self.classroom.pk)]},
                                {"file":SimpleUploadedFile("wrong.pdf",b"pdf bytes")},**kwargs)
                self.assertFalse(form.is_valid())
                self.assertIn("file",form.errors)

    def test_missing_file_returns_404_and_edit_preserves_attachments(self):
        item=Assignment.objects.create(teacher=self.teacher,classroom=self.classroom,title='missing',file='assignments/missing.pdf',video=self.video())
        self.client.force_login(self.suser)
        self.assertEqual(self.client.get(reverse('download_assignment_file',args=[item.pk])).status_code,404)
        self.client.force_login(self.tuser)
        original=item.video.name
        self.assertEqual(self.client.post(reverse('edit_assignment',args=[item.pk]),{'title':'ویرایش'}).status_code,302)
        item.refresh_from_db()
        self.assertEqual(item.video.name,original)

    def test_language_attachments_and_access(self):
        self.client.force_login(self.tuser)
        self.assertEqual(self.client.post(reverse('create_language_assignment',args=[self.group.pk]),{'title':'زبان', 'video':self.video(),'image':self.image()}).status_code,302)
        item=LanguageAssignment.objects.get()
        self.client.force_login(self.suser)
        url=reverse('download_language_assignment',args=[item.pk,'video'])
        self.assertContains(self.client.get(reverse('student_language_dashboard')),url)
        result=self.client.get(url)
        self.assertEqual(b''.join(result.streaming_content),b'x'*16)
        self.client.force_login(self.outsider)
        self.assertEqual(self.client.get(url).status_code,404)

    def test_admin_dates_and_date_forms(self):
        user=get_user_model().objects.create_superuser(username='date_admin',password='test',role='super_admin')
        self.client.force_login(user)
        for url in [reverse('admin:academic_academicyear_change',args=[self.year.pk]),reverse('admin:accounts_studentprofile_change',args=[self.student.pk]),reverse('admin:academic_academicyear_changelist')]:
            self.assertEqual(self.client.get(url).status_code,200)
        self.assertContains(self.client.get(reverse('admin:accounts_studentprofile_change',args=[self.student.pk])),'data-jalali="date"')
        self.assertContains(self.client.get(reverse('announcement_create')),'data-jalali="datetime"')
