import tempfile
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from accounts.choices import Role
from accounts.forms import TeacherCreateForm, TeacherEditForm, TeacherSelfProfileForm
from accounts.models import StudentProfile, TeacherProfile
from academic.models import AcademicYear, Classroom, Grade, TeacherClassAssignment, Enrollment
from assignments.models import Assignment
from materials.models import EducationalMaterial
from materials.forms import assigned_active_classrooms
from notifications.models import Notification
from .models import LanguageGroup, LanguageMaterial, LanguageAssignment

User = get_user_model()

class LanguageTeacherIsolationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.year = AcademicYear.objects.create(title='1405', status='active')
        grade = Grade.objects.create(code='1', title='اول', order=1)
        cls.classroom = Classroom.objects.create(academic_year=cls.year, grade=grade, name='الف', capacity=30)
        cls.user = User.objects.create_user('language', role=Role.TEACHER)
        cls.teacher = TeacherProfile.objects.create(user=cls.user, is_language_teacher=True)
        cls.regular_user = User.objects.create_user('regular', role=Role.TEACHER)
        cls.regular = TeacherProfile.objects.create(user=cls.regular_user)
        cls.student_user = User.objects.create_user('student', role=Role.STUDENT)
        cls.student = StudentProfile.objects.create(user=cls.student_user)
        cls.outsider_user = User.objects.create_user('outsider', role=Role.STUDENT)
        cls.outsider = StudentProfile.objects.create(user=cls.outsider_user)
        Enrollment.objects.create(student=cls.student, classroom=cls.classroom, academic_year=cls.year)
        cls.manager = User.objects.create_user('manager', role=Role.SCHOOL_MANAGER)
        cls.group = LanguageGroup.objects.create(title='Language A', academic_year=cls.year)
        cls.group.teachers.add(cls.teacher)
        cls.group.students.add(cls.student)
        cls.other_group = LanguageGroup.objects.create(title='Language B', academic_year=cls.year)
        cls.other_group.teachers.add(cls.regular)
        cls.other_group.students.add(cls.outsider)
        cls.material = LanguageMaterial.objects.create(group=cls.group, teacher=cls.teacher, title='Language-only material', content='ABC')
        cls.assignment = LanguageAssignment.objects.create(group=cls.group, teacher=cls.teacher, title='Language-only homework', description='ABC')
        LanguageMaterial.objects.create(group=cls.other_group, teacher=cls.regular, title='Other group secret')
        # Simulate stale school assignment, which must not grant access.
        TeacherClassAssignment.objects.create(teacher=cls.teacher, classroom=cls.classroom)
        TeacherClassAssignment.objects.create(teacher=cls.regular, classroom=cls.classroom)
        cls.school_material = EducationalMaterial.objects.create(teacher=cls.teacher, title='School material')
        cls.school_material.classrooms.add(cls.classroom)
        cls.school_assignment = Assignment.objects.create(teacher=cls.teacher, classroom=cls.classroom, title='School homework')

    def test_legacy_navigation_redirects_to_language(self):
        self.client.force_login(self.user)
        for source, target in [('teacher_dashboard','teacher_language_dashboard'),('teacher_material_list','teacher_language_material_list'),('teacher_assignment_list','teacher_language_assignment_list'),('create_material','teacher_language_dashboard')]:
            with self.subTest(source=source):
                self.assertRedirects(self.client.get(reverse(source)), reverse(target))
        self.assertFalse(assigned_active_classrooms(self.teacher).exists())

    def test_school_urls_reject_get_and_post_even_with_stale_assignment(self):
        self.client.force_login(self.user)
        urls = [('teacher_class_detail',self.classroom.id),('teacher_class_material_list',self.classroom.id),('teacher_class_assignment_list',self.classroom.id),('create_class_material',self.classroom.id),('create_assignment',self.classroom.id),('edit_material',self.school_material.id),('delete_material',self.school_material.id),('edit_assignment',self.school_assignment.id),('delete_assignment',self.school_assignment.id),('assignment_submissions',self.school_assignment.id)]
        for name, pk in urls:
            for method in ['get','post']:
                with self.subTest(name=name, method=method):
                    self.assertEqual(getattr(self.client, method)(reverse(name,args=[pk])).status_code,403)
        self.assertEqual(self.client.post(reverse('create_material'), {'title':'Bypass'}).status_code,403)
        self.assertTrue(EducationalMaterial.objects.filter(pk=self.school_material.pk).exists())
        self.assertTrue(Assignment.objects.filter(pk=self.school_assignment.pk).exists())

    def test_language_teacher_creates_content_without_school_classes(self):
        TeacherClassAssignment.objects.filter(teacher=self.teacher).delete()
        self.client.force_login(self.user)
        for name,data in [('create_language_material',{'title':'New language material','content_type':'text','content':'hello'}),('create_language_assignment',{'title':'New language homework','description':'hello'})]:
            self.assertEqual(self.client.post(reverse(name,args=[self.group.pk]),data).status_code,302)
        self.assertEqual(self.group.materials.count(),2)
        self.assertEqual(self.group.assignments.count(),2)
        self.assertEqual(Notification.objects.filter(recipient=self.student_user).count(),2)
        self.assertFalse(Notification.objects.filter(recipient=self.outsider_user).exists())

    def test_other_group_and_inactive_group_cannot_be_used(self):
        self.client.force_login(self.user)
        for name in ['language_group_detail','create_language_material','create_language_assignment']:
            self.assertEqual(self.client.get(reverse(name,args=[self.other_group.pk])).status_code,404)
        self.group.is_active=False; self.group.save()
        for name in ['language_group_detail','create_language_material','create_language_assignment']:
            self.assertEqual(self.client.post(reverse(name,args=[self.group.pk]),{}).status_code,404)
        self.group.is_active=True; self.group.save()
        self.year.status='archived'; self.year.save()
        self.assertEqual(self.client.get(reverse('create_language_material',args=[self.group.pk])).status_code,404)

    def test_students_see_only_own_language_and_no_mixing(self):
        self.client.force_login(self.student_user)
        response=self.client.get(reverse('student_language_dashboard'))
        self.assertContains(response,'Language-only material')
        self.assertNotContains(response,'Other group secret')
        for name in ['student_dashboard','student_material_list','student_assignment_list']:
            response=self.client.get(reverse(name))
            self.assertNotContains(response,'Language-only material')
            self.assertNotContains(response,'Language-only homework')
        self.client.force_login(self.outsider_user)
        self.assertNotContains(self.client.get(reverse('student_language_dashboard')),'Language-only material')
        self.assertEqual(self.client.get(reverse('submit_language_assignment',args=[self.assignment.pk])).status_code,404)

    def test_manager_can_review_all_groups_and_teacher_cannot_use_manager_url(self):
        self.client.force_login(self.manager)
        response=self.client.get(reverse('manage_language_groups'))
        self.assertContains(response, reverse('manager_language_group_content',args=[self.group.pk]))
        for group in [self.group,self.other_group]:
            self.assertEqual(self.client.get(reverse('manager_language_group_content',args=[group.pk])).status_code,200)
        response=self.client.get(reverse('language_group_material_list',args=[self.group.pk]))
        self.assertContains(response,'Language-only material')
        self.assertNotContains(response,reverse('edit_language_material',args=[self.material.pk]))
        self.assertContains(self.client.get(reverse('language_group_assignment_list',args=[self.group.pk])), 'Language-only homework')
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse('manager_language_group_content',args=[self.group.pk])).status_code,403)

    def test_attachment_permissions(self):
        with tempfile.TemporaryDirectory() as media, override_settings(MEDIA_ROOT=media):
            self.material.file.save('example.txt',SimpleUploadedFile('example.txt',b'hello'))
            url=reverse('download_language_material',args=[self.material.pk])
            for user in [self.user,self.student_user,self.manager]:
                self.client.force_login(user)
                response=self.client.get(url)
                self.assertEqual(response.status_code,200)
                self.assertEqual(b''.join(response.streaming_content),b'hello'); response.close()
            self.client.force_login(self.outsider_user)
            self.assertEqual(self.client.get(url).status_code,404)
            self.client.force_login(self.regular_user)
            self.assertEqual(self.client.get(url).status_code,404)

    def test_regular_teacher_still_uses_school(self):
        self.client.force_login(self.regular_user)
        self.assertEqual(self.client.get(reverse('teacher_dashboard')).status_code,200)
        self.assertEqual(self.client.get(reverse('teacher_class_detail',args=[self.classroom.pk])).status_code,200)

    def test_flag_is_manager_controlled_and_persists(self):
        form=TeacherCreateForm(data={'first_name':'A','last_name':'B','is_language_teacher':'on','classrooms':[self.classroom.pk]})
        self.assertTrue(form.is_valid(),form.errors)
        user=form.save(); self.assertTrue(user.teacher_profile.is_language_teacher)
        self.assertFalse(user.teacher_profile.class_assignments.exists())
        self.assertNotIn('is_language_teacher',TeacherSelfProfileForm().fields)
        self.client.force_login(self.manager)
        response=self.client.get(reverse('edit_teacher',args=[self.teacher.pk]))
        self.assertTrue(response.context['form'].initial['is_language_teacher'])
        self.assertEqual(self.client.post(reverse('edit_teacher',args=[self.regular.pk]),{
            'username':'regular','first_name':'R','last_name':'T','is_active':'on',
            'is_language_teacher':'on','classrooms':[self.classroom.pk],
        }).status_code,302)
        self.regular.refresh_from_db(); self.assertTrue(self.regular.is_language_teacher)
        self.assertFalse(self.regular.class_assignments.filter(classroom=self.classroom).exists())

    def test_exclusive_language_sidebar_has_no_school_links(self):
        self.client.force_login(self.user)
        response=self.client.get(reverse('teacher_language_dashboard'))
        self.assertContains(response,reverse('teacher_language_material_list'))
        self.assertContains(response,reverse('teacher_language_assignment_list'))
        self.assertNotContains(response,'href="'+reverse('teacher_dashboard')+'"')
        self.assertNotContains(response,'href="'+reverse('teacher_material_list')+'"')

    def test_student_cannot_author_content_in_unassigned_group(self):
        self.other_group.teachers.clear()
        self.client.force_login(self.student_user)
        for name in ['language_group_detail','create_language_material','create_language_assignment']:
            self.assertEqual(self.client.get(reverse(name,args=[self.other_group.pk])).status_code,403)

    def test_school_online_and_classroom_lookup_are_blocked(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse('online_class_list')).status_code,403)
        self.assertEqual(self.client.get(reverse('load_classrooms'),{'academic_year':self.year.pk}).status_code,403)

    def test_group_dashboard_shows_buttons_instead_of_full_content(self):
        for user, name in [(self.user, 'language_group_detail'), (self.manager, 'manager_language_group_content')]:
            self.client.force_login(user)
            response=self.client.get(reverse(name,args=[self.group.pk]))
            self.assertContains(response, reverse('language_group_material_list',args=[self.group.pk]))
            self.assertContains(response, reverse('language_group_assignment_list',args=[self.group.pk]))
            self.assertNotContains(response, 'Language-only material')
            self.assertNotContains(response, 'Language-only homework')
            self.assertContains(response, 'پیام واحد زبان')

    def test_group_lists_are_newest_first_and_group_scoped(self):
        from datetime import timedelta
        from django.utils import timezone
        for model, name in [(LanguageMaterial,'language_group_material_list'), (LanguageAssignment,'language_group_assignment_list')]:
            older=model.objects.create(group=self.group,teacher=self.teacher,title='Older title')
            newer=model.objects.create(group=self.group,teacher=self.teacher,title='Newest title')
            model.objects.filter(pk=older.pk).update(created_at=timezone.now()-timedelta(days=2))
            self.client.force_login(self.user)
            response=self.client.get(reverse(name,args=[self.group.pk]))
            self.assertEqual(response.context['items'][0],newer)
            self.assertLess(response.content.index(b'Newest title'),response.content.index(b'Older title'))
            self.assertNotContains(response,'Other group secret')
            self.assertEqual(self.client.get(reverse(name,args=[self.other_group.pk])).status_code,404)
            self.client.force_login(self.student_user)
            self.assertEqual(self.client.get(reverse(name,args=[self.group.pk])).status_code,403)

    def test_manager_group_lists_include_other_authors(self):
        LanguageMaterial.objects.create(group=self.group,teacher=self.regular,title='Second author')
        self.client.force_login(self.user)
        self.assertNotContains(self.client.get(reverse('language_group_material_list',args=[self.group.pk])),'Second author')
        self.client.force_login(self.manager)
        response=self.client.get(reverse('language_group_material_list',args=[self.group.pk]))
        self.assertContains(response,'Second author')
        self.assertNotContains(response, 'مطلب جدید')
