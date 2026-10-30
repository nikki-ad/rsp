from unittest.mock import patch
from django.test import TestCase
from django.urls import reverse
from accounts.models import CustomUser, StudentProfile, TeacherProfile
from accounts.choices import Role
from academic.models import AcademicYear
from language_unit.models import LanguageGroup
from dashboard.forms import LanguageOnlineClassForm
from online_classes.models import OnlineClass, BBBConfiguration


class LanguageOnlineTests(TestCase):
    def setUp(self):
        self.year = AcademicYear.objects.create(title='1405', status='active')
        self.manager = CustomUser.objects.create_user(username='manager', role=Role.SCHOOL_MANAGER)
        self.student = StudentProfile.objects.create(user=CustomUser.objects.create_user(username='student', role=Role.STUDENT))
        self.outsider = StudentProfile.objects.create(user=CustomUser.objects.create_user(username='outsider', role=Role.STUDENT))
        self.teacher = TeacherProfile.objects.create(user=CustomUser.objects.create_user(username='teacher', role=Role.TEACHER), is_language_teacher=True)
        self.group = LanguageGroup.objects.create(title='English A', academic_year=self.year)
        self.group.students.add(self.student)
        self.group.teachers.add(self.teacher)
        self.config = BBBConfiguration.objects.create(name='BBB', api_url='https://bbb.example/api/', secret='test')
        self.data = dict(title='English online', academic_year=str(self.year.pk), provider='bbb', bbb_configuration=str(self.config.pk), students=[str(self.student.pk)], teachers=[str(self.teacher.pk)], is_active='on')

    def test_group_students_without_school_enrollment_and_teacher_selection(self):
        form = LanguageOnlineClassForm(self.data)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.student_classroom_data[0]['name'], str(self.group))
        form = LanguageOnlineClassForm({**self.data, 'students': [str(self.outsider.pk)]})
        self.assertFalse(form.is_valid())
        self.assertIn('students', form.errors)
        self.group.is_active = False
        self.group.save()
        self.assertFalse(LanguageOnlineClassForm(self.data).is_valid())

    def test_create_edit_list_delete_and_navigation(self):
        self.client.force_login(self.manager)
        response = self.client.post(reverse('language_online_create'), self.data)
        self.assertRedirects(response, reverse('language_online_manage'))
        online = OnlineClass.objects.get(title='English online')
        self.assertTrue(online.is_language)
        self.assertContains(self.client.get(reverse('language_online_manage')), online.title)
        self.assertNotContains(self.client.get(reverse('online_class_manage_list')), online.title)
        self.assertContains(self.client.get(reverse('online_class_manage_list')), reverse('language_online_manage'))
        self.assertContains(self.client.get(reverse('manage_language_groups')), reverse('language_online_manage'))
        self.assertContains(self.client.get(reverse('language_online_edit', args=[online.pk])), str(self.student.pk))
        self.assertEqual(self.client.get(reverse('online_class_edit', args=[online.pk])).status_code, 404)
        self.assertEqual(self.client.get(reverse('online_class_delete', args=[online.pk])).status_code, 404)
        self.assertRedirects(self.client.post(reverse('language_online_delete', args=[online.pk])), reverse('language_online_manage'))
        self.assertFalse(OnlineClass.objects.filter(pk=online.pk).exists())

    def test_access_join_and_people_endpoint(self):
        self.client.force_login(self.manager)
        self.client.post(reverse('language_online_create'), self.data)
        online = OnlineClass.objects.get(title='English online')
        response = self.client.get(reverse('language_online_people'), {'academic_year': self.year.pk})
        self.assertEqual(response.json()['classrooms'][0]['students'][0]['id'], str(self.student.pk))
        self.assertEqual(self.client.get(reverse('language_online_people'), {'academic_year': 'bad'}).json(), {'classrooms': []})
        for profile in (self.student, self.teacher):
            self.client.force_login(profile.user)
            self.assertContains(self.client.get(reverse('language_online_list')), online.title)
            self.assertEqual(self.client.get(reverse('language_online_create')).status_code, 403)
            self.assertEqual(self.client.get(reverse('language_online_people')).status_code, 403)
            with patch('online_classes.views.create_bbb_meeting') as create:
                self.assertEqual(self.client.get(reverse('join_online_class', args=[online.pk])).status_code, 302)
                create.assert_called_once()
        self.client.force_login(self.outsider.user)
        self.assertNotContains(self.client.get(reverse('language_online_list')), online.title)
        with patch('online_classes.views.create_bbb_meeting') as create:
            self.client.get(reverse('join_online_class', args=[online.pk]))
            create.assert_not_called()
