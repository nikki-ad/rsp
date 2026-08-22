from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from accounts.choices import Role
from accounts.models import StudentProfile, TeacherProfile
from academic.models import AcademicYear
from notifications.models import Notification
from .models import LanguageAssignment, LanguageGroup, LanguageMaterial


User = get_user_model()


class LanguageUnitTests(TestCase):
    def setUp(self):
        self.year = AcademicYear.objects.create(title="1405-1406", status="active")
        self.student_user = User.objects.create_user("student", password="pass", role=Role.STUDENT)
        self.student = StudentProfile.objects.create(user=self.student_user)
        self.other_user = User.objects.create_user("other", password="pass", role=Role.STUDENT)
        self.other_student = StudentProfile.objects.create(user=self.other_user)
        self.teacher_user = User.objects.create_user("teacher", password="pass", role=Role.TEACHER)
        self.teacher = TeacherProfile.objects.create(user=self.teacher_user)
        self.group = LanguageGroup.objects.create(title="A1", academic_year=self.year)
        self.group.students.add(self.student)
        self.group.teachers.add(self.teacher)
        LanguageMaterial.objects.create(
            group=self.group, teacher=self.teacher, title="Alphabet", content="ABC"
        )
        self.assignment = LanguageAssignment.objects.create(
            group=self.group, teacher=self.teacher, title="Homework"
        )

    def test_student_only_sees_own_language_group_content(self):
        self.client.force_login(self.student_user)
        response = self.client.get(reverse("student_language_dashboard"))
        self.assertContains(response, "Alphabet")
        self.client.force_login(self.other_user)
        response = self.client.get(reverse("student_language_dashboard"))
        self.assertNotContains(response, "Alphabet")

    def test_language_teacher_can_open_assigned_group(self):
        self.client.force_login(self.teacher_user)
        response = self.client.get(reverse("language_group_detail", args=[self.group.id]))
        self.assertEqual(response.status_code, 200)

    def test_delete_all_notifications_only_deletes_current_users_items(self):
        Notification.objects.create(recipient=self.student_user, title="one")
        Notification.objects.create(recipient=self.other_user, title="two")
        self.client.force_login(self.student_user)
        self.client.post(reverse("delete_all_notifications"))
        self.assertFalse(Notification.objects.filter(recipient=self.student_user).exists())
        self.assertTrue(Notification.objects.filter(recipient=self.other_user).exists())
