import hashlib
from io import StringIO
from unittest.mock import patch, Mock
from urllib.parse import parse_qs, urlsplit

from django.core.management import call_command, CommandError
from django.test import TestCase
from django.urls import reverse
import requests

from accounts.choices import Role
from accounts.models import CustomUser, StudentProfile, TeacherProfile
from academic.models import AcademicYear, Classroom, Grade, Enrollment
from dashboard.forms import OnlineClassForm
from .models import BBBConfiguration, OnlineClass
from .services import build_bbb_join_url, build_bbb_meeting_id, create_bbb_meeting, test_bbb_connection


class OnlineClassTests(TestCase):
    def setUp(self):
        self.year = AcademicYear.objects.create(title='1405', status='active')
        self.other_year = AcademicYear.objects.create(title='1404')
        grade = Grade.objects.create(code='1', title='اول', order=1)
        self.room = Classroom.objects.create(academic_year=self.year, grade=grade, name='الف', capacity=30)
        self.student_user = CustomUser.objects.create_user(username='student', role=Role.STUDENT)
        self.student = StudentProfile.objects.create(user=self.student_user)
        self.second_student = StudentProfile.objects.create(user=CustomUser.objects.create_user(username='second'))
        for student in (self.student, self.second_student):
            Enrollment.objects.create(student=student, academic_year=self.year, classroom=self.room)
        self.teacher_user = CustomUser.objects.create_user(username='teacher', role=Role.TEACHER)
        self.teacher = TeacherProfile.objects.create(user=self.teacher_user)
        self.config = BBBConfiguration.objects.create(name='BBB', api_url='https://bbb.example/bigbluebutton/api/', secret='test-secret')
        self.online = OnlineClass.objects.create(title='کلاس', academic_year=self.year, bbb_configuration=self.config)
        self.online.students.add(self.student)
        self.online.teachers.add(self.teacher)
        self.manager = CustomUser.objects.create_user(username='manager', role=Role.SCHOOL_MANAGER)
        # Admin must retain global access even with unrelated teacher/student profiles.
        TeacherProfile.objects.create(user=self.manager)
        StudentProfile.objects.create(user=self.manager)

    def test_admin_profiles_do_not_limit_list_or_moderator_join(self):
        for role in (Role.SCHOOL_MANAGER, Role.SUPER_ADMIN):
            self.manager.role = role
            self.manager.save()
            self.client.force_login(self.manager)
            response = self.client.get(reverse('online_class_list'))
            self.assertContains(response, self.online.title)
            with patch('online_classes.views.create_bbb_meeting'):
                response = self.client.get(reverse('join_online_class', args=[self.online.pk]))
            params = parse_qs(urlsplit(response.url).query)
            self.assertEqual(params['role'], ['MODERATOR'])
        self.manager.role = Role.STUDENT
        self.manager.is_superuser = True
        self.manager.save()
        with patch('online_classes.views.create_bbb_meeting'):
            response = self.client.get(reverse('join_online_class', args=[self.online.pk]))
        self.assertEqual(parse_qs(urlsplit(response.url).query)['role'], ['MODERATOR'])

    def test_teacher_moderator_student_viewer_and_signed_roles(self):
        for user, role in ((self.teacher_user, 'MODERATOR'), (self.student_user, 'VIEWER')):
            self.client.force_login(user)
            with patch('online_classes.views.create_bbb_meeting'):
                response = self.client.get(reverse('join_online_class', args=[self.online.pk]) + '?role=moderator')
            query = urlsplit(response.url).query
            params = parse_qs(query)
            self.assertEqual(params['role'], [role])
            unsigned, checksum = query.rsplit('&checksum=', 1)
            self.assertEqual(checksum, hashlib.sha1(('join' + unsigned + self.config.secret).encode()).hexdigest())

    def test_selected_language_teacher_can_join(self):
        self.teacher.is_language_teacher = True
        self.teacher.save()
        self.client.force_login(self.teacher_user)
        self.assertContains(self.client.get(reverse('online_class_list')), reverse('online_class_list'))
        with patch('online_classes.views.create_bbb_meeting'):
            response = self.client.get(reverse('join_online_class', args=[self.online.pk]))
        self.assertEqual(parse_qs(urlsplit(response.url).query)['role'], ['MODERATOR'])

    def test_unassigned_users_cannot_join_or_create_meeting(self):
        for user in (self.second_student.user, CustomUser.objects.create_user(username='outsider', role=Role.TEACHER)):
            self.client.force_login(user)
            with patch('online_classes.views.create_bbb_meeting') as create:
                response = self.client.get(reverse('join_online_class', args=[self.online.pk]))
            create.assert_not_called()
            self.assertRedirects(response, reverse('online_class_list'))

    def test_room_id_remains_automatic_and_stable(self):
        self.online.bbb_room_id = 'legacy-unused-value'
        self.assertEqual(build_bbb_meeting_id(self.online), f'online-class-{self.online.pk}')
        self.assertNotIn('bbb_room_id', OnlineClassForm(instance=self.online).fields)

    def test_form_defaults_to_active_year_and_groups_students(self):
        form = OnlineClassForm()
        self.assertEqual(form.initial['academic_year'], self.year.pk)
        groups = form.student_classroom_data
        self.assertEqual(groups[0]['id'], str(self.room.pk))
        self.assertEqual({s['id'] for s in groups[0]['students']}, {str(self.student.pk), str(self.second_student.pk)})

    def test_save_excluded_student_and_edit_preserves_selection(self):
        form = OnlineClassForm(data={
            'title': 'جدید', 'academic_year': self.year.pk, 'provider': 'bbb',
            'bbb_configuration': self.config.pk, 'students': [self.second_student.pk],
            'teachers': [self.teacher.pk], 'is_active': 'on',
        })
        self.assertTrue(form.is_valid(), form.errors)
        online = form.save()
        self.assertEqual(list(online.students.all()), [self.second_student])
        self.assertEqual(OnlineClassForm(instance=online).initial['students'], [self.second_student])

    def test_year_membership_is_validated_and_invalid_uuid_does_not_crash(self):
        for year in (self.other_year.pk, 'bad-uuid'):
            form = OnlineClassForm(data={'title': 'x', 'academic_year': year, 'provider': 'bbb',
                'bbb_configuration': self.config.pk, 'students': [self.student.pk]})
            self.assertFalse(form.is_valid())
            self.assertIn('students', form.errors)

    def test_people_endpoint_permissions_and_year_filter(self):
        self.client.force_login(self.student_user)
        self.assertEqual(self.client.get(reverse('load_year_people')).status_code, 403)
        self.client.force_login(self.manager)
        response = self.client.get(reverse('load_year_people'), {'academic_year': str(self.year.pk)})
        self.assertEqual(len(response.json()['classrooms'][0]['students']), 2)
        self.assertEqual(self.client.get(reverse('load_year_people'), {'academic_year': str(self.other_year.pk)}).json()['classrooms'], [])
        self.assertEqual(self.client.get(reverse('load_year_people'), {'academic_year': 'bad'}).status_code, 400)

    def test_bbb_http_200_failure_or_html_is_not_success(self):
        for body in ('<response><returncode>FAILED</returncode><messageKey>checksumError</messageKey></response>', '<html>bad</html>', 'not xml'):
            with patch('online_classes.services.requests.get', return_value=Mock(text=body)):
                with self.assertRaises(ValueError):
                    test_bbb_connection(self.config)
                with self.assertRaises(ValueError):
                    create_bbb_meeting(self.online)

    def test_bbb_success_uses_signed_getmeetings_without_creating(self):
        with patch('online_classes.services.requests.get', return_value=Mock(text='<response><returncode>SUCCESS</returncode></response>')) as get:
            test_bbb_connection(self.config)
        url = get.call_args.args[0]
        self.assertIn('/getMeetings?', url)
        self.assertNotIn('/create', url)
        self.assertIn(hashlib.sha1(('getMeetings' + self.config.secret).encode()).hexdigest(), url)

    def test_inactive_service_is_rejected(self):
        self.config.is_active = False
        self.config.save()
        self.assertNotIn(self.config, OnlineClassForm().fields['bbb_configuration'].queryset)
        with self.assertRaises(ValueError):
            build_bbb_join_url(self.online, self.student_user, 'attendee')

    def test_failed_create_does_not_redirect_to_bbb(self):
        self.client.force_login(self.student_user)
        with patch('online_classes.views.create_bbb_meeting', side_effect=ValueError('API failed')):
            response = self.client.get(reverse('join_online_class', args=[self.online.pk]))
        self.assertRedirects(response, reverse('online_class_list'))

    def test_connection_button_and_command_are_safe(self):
        self.client.force_login(self.manager)
        url = reverse('bbb_config_test', args=[self.config.pk])
        self.assertEqual(self.client.get(url).status_code, 405)
        with patch('online_classes.services.requests.get', return_value=Mock(text='<response><returncode>SUCCESS</returncode></response>')):
            response = self.client.post(url, follow=True)
            self.assertContains(response, 'اتصال به BBB موفق است')
            output = StringIO()
            call_command('check_bbb', stdout=output)
            self.assertIn('OK:', output.getvalue())
            self.assertNotIn(self.config.secret, output.getvalue())
        with patch('online_classes.services.requests.get', side_effect=requests.ConnectionError('private signed url')):
            with self.assertRaises(CommandError):
                call_command('check_bbb', stdout=StringIO(), stderr=StringIO())
        self.client.force_login(self.student_user)
        self.assertEqual(self.client.post(url).status_code, 403)

    def test_online_form_renders_script_with_initial_group_data(self):
        self.client.force_login(self.manager)
        response = self.client.get(reverse('online_class_edit', args=[self.online.pk]))
        self.assertContains(response, 'online-class-students.js')
        self.assertContains(response, 'online-class-groups')
        self.assertContains(response, str(self.room.pk))

    def test_manager_has_operator_entry_in_management_list(self):
        self.client.force_login(self.manager)
        response = self.client.get(reverse('online_class_manage_list'))
        self.assertContains(response, 'ورود اپراتور')
        self.assertContains(response, reverse('join_online_class', args=[self.online.pk]))
