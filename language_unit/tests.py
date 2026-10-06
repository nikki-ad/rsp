from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from accounts.choices import Role
from accounts.models import StudentProfile, TeacherProfile
from academic.models import AcademicYear, Classroom, Enrollment, Grade
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

    def test_group_student_search_is_scoped_to_year_and_admin(self):
        self.student_user.first_name = "نگار"
        self.student_user.last_name = "احمدی"
        self.student_user.save()
        grade = Grade.objects.create(code="1", title="اول", order=1)
        classroom = Classroom.objects.create(
            academic_year=self.year, grade=grade, name="الف", capacity=30,
        )
        Enrollment.objects.create(student=self.student, academic_year=self.year,
                                  classroom=classroom, is_active=True)
        url = reverse("search_language_students")
        params = {"academic_year": str(self.year.id), "q": "احمد"}
        self.client.force_login(self.teacher_user)
        self.assertEqual(self.client.get(url, params).status_code, 403)
        admin = User.objects.create_superuser("admin", password="pass")
        self.client.force_login(admin)
        response = self.client.get(url, params)
        self.assertEqual(response.json()["students"], [
            {"id": str(self.student.id), "name": "نگار احمدی"}
        ])
        self.assertEqual(self.client.get(url, {**params, "academic_year": "invalid"}).json(),
                         {"students": []})

    def test_group_form_preserves_selected_students_and_rejects_other_year(self):
        grade = Grade.objects.create(code="1", title="اول", order=1)
        classroom = Classroom.objects.create(
            academic_year=self.year, grade=grade, name="الف", capacity=30,
        )
        Enrollment.objects.create(student=self.student, academic_year=self.year,
                                  classroom=classroom, is_active=True)
        admin = User.objects.create_superuser("admin", password="pass")
        self.client.force_login(admin)
        response = self.client.get(reverse("language_group_edit", args=[self.group.id]))
        self.assertContains(response, 'id="language-student-search"')
        self.assertContains(response, f'value="{self.student.id}" selected')
        response = self.client.post(reverse("language_group_edit", args=[self.group.id]), {
            "title": "A1", "academic_year": self.year.id, "teachers": [self.teacher.id],
            "students": [self.other_student.id], "is_active": "on",
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(self.group.students.all()), [self.student])

    def test_language_teacher_can_edit_own_material_and_assignment_only(self):
        other_teacher_user = User.objects.create_user("otherteacher", password="pass", role=Role.TEACHER)
        other_teacher = TeacherProfile.objects.create(user=other_teacher_user)
        material = self.group.materials.get()
        material_url = reverse("edit_language_material", args=[material.id])
        assignment_url = reverse("edit_language_assignment", args=[self.assignment.id])
        self.client.force_login(other_teacher_user)
        self.assertEqual(self.client.get(material_url).status_code, 404)
        self.assertEqual(self.client.get(assignment_url).status_code, 404)
        self.group.teachers.add(other_teacher)
        self.assertEqual(self.client.get(material_url).status_code, 404)
        self.client.force_login(self.teacher_user)
        self.assertContains(self.client.get(reverse("language_group_material_list", args=[self.group.id])),
                            material_url)
        self.assertEqual(self.client.post(material_url, {
            "title": "New material", "content_type": "text", "content": "Edited",
        }).status_code, 302)
        self.assertEqual(self.client.post(assignment_url, {
            "title": "New homework", "description": "Edited",
        }).status_code, 302)
        material.refresh_from_db()
        self.assignment.refresh_from_db()
        self.assertEqual(material.content, "Edited")
        self.assertEqual(self.assignment.description, "Edited")
