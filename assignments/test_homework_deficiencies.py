from datetime import date
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from academic.models import AcademicYear, Classroom, Enrollment, Grade, TeacherClassAssignment
from accounts.models import StudentProfile, TeacherProfile
from notifications.models import Notification
from .homework_models import HomeworkDeficiency


class HomeworkDeficiencyTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.teacher_user = User.objects.create_user(username="teacher", role="teacher", first_name="مریم", last_name="احمدی")
        cls.teacher = TeacherProfile.objects.create(user=cls.teacher_user)
        cls.language_user = User.objects.create_user(username="language", role="teacher")
        cls.language = TeacherProfile.objects.create(user=cls.language_user, is_language_teacher=True)
        cls.other_teacher_user = User.objects.create_user(username="other_teacher", role="teacher")
        TeacherProfile.objects.create(user=cls.other_teacher_user)
        cls.year = AcademicYear.objects.create(title="1405", status="active")
        cls.grade = Grade.objects.create(code="1", title="اول", order=1)
        cls.classroom = Classroom.objects.create(name="یاس", academic_year=cls.year, grade=cls.grade, capacity=30)
        cls.other_classroom = Classroom.objects.create(name="رز", academic_year=cls.year, grade=cls.grade, capacity=30)
        TeacherClassAssignment.objects.create(teacher=cls.teacher, classroom=cls.classroom)
        TeacherClassAssignment.objects.create(teacher=cls.language, classroom=cls.classroom)
        cls.students = []
        for i in range(4):
            user = User.objects.create_user(username=f"student{i}", role="student", first_name=f"دانش‌آموز {i}")
            student = StudentProfile.objects.create(user=user)
            Enrollment.objects.create(student=student, academic_year=cls.year,
                                      classroom=cls.other_classroom if i == 2 else cls.classroom,
                                      is_active=i != 3)
            cls.students.append(student)

    def setUp(self):
        self.client.force_login(self.teacher_user)
        self.url = reverse("teacher_deficiency_create", args=[self.classroom.pk])
        self.data = {"record_date": "۱۴۰۵/۰۷/۲۶", "subject": "ریاضی", "students": [str(s.pk) for s in self.students[:2]]}

    def test_batch_registration_and_duplicate_submission(self):
        for _ in range(2):
            self.assertRedirects(self.client.post(self.url, self.data), self.url)
        self.assertEqual(HomeworkDeficiency.objects.count(), 2)
        self.assertEqual(Notification.objects.count(), 2)
        self.assertEqual(set(Notification.objects.values_list("recipient_id", flat=True)), {s.user_id for s in self.students[:2]})
        record = HomeworkDeficiency.objects.first()
        self.assertEqual(record.record_date, date(2026, 10, 18))
        self.assertEqual(record.created_by, self.teacher_user)
        notification = Notification.objects.first()
        self.assertIn("1405/07/26", notification.message)
        self.assertIn("ریاضی", notification.message)
        self.assertIn("مریم احمدی", notification.message)
        self.assertEqual(notification.summary_message, "")
        self.assertEqual(notification.url, reverse("student_deficiency_list"))

    def test_invalid_student_selection_is_atomic(self):
        for student in self.students[2:]:
            with self.subTest(student=student):
                self.data["students"] = [str(self.students[0].pk), str(student.pk)]
                response = self.client.post(self.url, self.data)
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.context["form"].errors)
        self.assertEqual(HomeworkDeficiency.objects.count(), 0)
        self.assertEqual(Notification.objects.count(), 0)

    def test_invalid_fields_and_empty_selection(self):
        for changes in ({"students": []}, {"record_date": "1404/12/30"}, {"subject": "   "}, {"subject": "a" * 151}):
            with self.subTest(changes=changes):
                response = self.client.post(self.url, {**self.data, **changes})
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.context["form"].errors)
        self.assertFalse(HomeworkDeficiency.objects.exists())

    def test_authorization_for_classes_roles_and_language_unit(self):
        self.assertEqual(self.client.get(reverse("teacher_deficiency_create", args=[self.other_classroom.pk])).status_code, 404)
        for user, status in [(self.language_user, 403), (self.other_teacher_user, 404), (self.students[0].user, 403)]:
            self.client.force_login(user)
            self.assertEqual(self.client.get(self.url).status_code, status)
            self.assertEqual(self.client.post(self.url, self.data).status_code, status)
        self.client.logout()
        self.assertEqual(self.client.get(self.url).status_code, 302)
        self.assertFalse(HomeworkDeficiency.objects.exists())

    def test_archived_class_blocked(self):
        self.year.status = "archived"
        self.year.save()
        self.assertEqual(self.client.post(self.url, self.data).status_code, 404)
        self.assertNotContains(self.client.get(reverse("teacher_deficiency_classrooms")), self.classroom.name)

    def test_own_history_sorted_by_record_date(self):
        for student, day in [(self.students[0], 18), (self.students[0], 16), (self.students[1], 19)]:
            HomeworkDeficiency.objects.create(teacher=self.teacher, classroom=self.classroom, student=student,
                                             record_date=date(2026, 10, day), subject="ریاضی")
        self.client.force_login(self.students[0].user)
        response = self.client.get(reverse("student_deficiency_list"))
        self.assertEqual([r.record_date.day for r in response.context["page_obj"]], [18, 16])
        self.assertContains(response, "مریم احمدی")
        self.assertContains(response, "مشاهده نقص تکلیف")
        self.client.force_login(self.teacher_user)
        self.assertEqual(self.client.get(reverse("student_deficiency_list")).status_code, 403)

    def test_notification_failure_rolls_back_records(self):
        with patch("assignments.homework_views.create_notification", side_effect=RuntimeError("failure")):
            with self.assertRaises(RuntimeError):
                self.client.post(self.url, self.data)
        self.assertFalse(HomeworkDeficiency.objects.exists())

    def test_sidebar_and_roster(self):
        response = self.client.get(self.url)
        self.assertContains(response, "ثبت نقص تکلیف")
        self.assertContains(response, "تقویم شمسی")
        self.assertEqual(set(response.context["form"].fields["students"].queryset), set(self.students[:2]))
        self.client.force_login(self.language_user)
        response = self.client.get(reverse("teacher_language_dashboard"))
        self.assertNotContains(response, reverse("teacher_deficiency_classrooms"))

    def test_calendar_leap_year_and_weekday(self):
        url = reverse("deficiency_calendar")
        for year, days in [(1403, 30), (1404, 29)]:
            data = self.client.get(url, {"year": year, "month": 12}).json()
            self.assertEqual(data["days"], days)
        data = self.client.get(url, {"year": 1405, "month": 1}).json()
        self.assertEqual(data["offset"], 0)  # 1405/01/01 is Saturday.
        for params in ({"year": "bad"}, {"month": 13}, {"year": 9999}):
            self.assertEqual(self.client.get(url, params).status_code, 400)
        self.client.force_login(self.language_user)
        self.assertEqual(self.client.get(url).status_code, 403)
