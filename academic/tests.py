from datetime import time

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.choices import Role
from accounts.models import StudentProfile, TeacherProfile
from dashboard.forms import ClassroomForm

from .models import AcademicYear, Classroom, Enrollment, Grade, StudentDailyRoutine, TeacherClassAssignment


User = get_user_model()


class DailyRoutineFeatureTests(TestCase):
    def setUp(self):
        self.year = AcademicYear.objects.create(title="۱۴۰۵-۱۴۰۶", status=AcademicYear.Status.ACTIVE)
        self.grade = Grade.objects.create(code="1", title="اول", order=1)

        teacher_user = User.objects.create_user(username="main.teacher", password="pass", role=Role.TEACHER)
        other_user = User.objects.create_user(username="art.teacher", password="pass", role=Role.TEACHER)
        self.teacher = TeacherProfile.objects.create(user=teacher_user)
        self.other_teacher = TeacherProfile.objects.create(user=other_user)
        self.classroom = Classroom.objects.create(
            academic_year=self.year,
            grade=self.grade,
            name="یاس ۱",
            capacity=30,
            daily_report_responsible=self.teacher,
        )
        TeacherClassAssignment.objects.create(teacher=self.teacher, classroom=self.classroom)
        TeacherClassAssignment.objects.create(teacher=self.other_teacher, classroom=self.classroom)

        student_user = User.objects.create_user(username="student.one", password="pass", role=Role.STUDENT)
        self.student = StudentProfile.objects.create(user=student_user)
        Enrollment.objects.create(student=self.student, academic_year=self.year, classroom=self.classroom)

    def routine_payload(self, **overrides):
        payload = {
            "study_start": "16:00",
            "study_end": "17:00",
            "homework_start": "18:00",
            "homework_end": "19:00",
            "sleep_time": "22:30",
        }
        payload.update(overrides)
        return payload

    def test_student_creates_and_updates_only_todays_record(self):
        self.client.force_login(self.student.user)
        self.client.post(reverse("student_dashboard"), self.routine_payload())
        self.assertEqual(StudentDailyRoutine.objects.count(), 1)
        self.client.post(reverse("student_dashboard"), self.routine_payload(study_end="17:30"))
        self.assertEqual(StudentDailyRoutine.objects.count(), 1)
        self.assertEqual(StudentDailyRoutine.objects.get().study_end, time(17, 30))

    def test_invalid_time_interval_is_not_saved(self):
        self.client.force_login(self.student.user)
        response = self.client.post(
            reverse("student_dashboard"),
            self.routine_payload(study_start="18:00", study_end="17:00"),
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(StudentDailyRoutine.objects.count(), 0)
        self.assertContains(response, "زمان پایان بازه مطالعه باید بعد از زمان شروع باشد")

    def test_only_responsible_teacher_can_open_report(self):
        self.client.force_login(self.teacher.user)
        allowed = self.client.get(reverse("teacher_routine_report", args=[self.classroom.id]))
        self.assertEqual(allowed.status_code, 200)
        self.client.force_login(self.other_teacher.user)
        denied = self.client.get(reverse("teacher_routine_report", args=[self.classroom.id]))
        self.assertEqual(denied.status_code, 404)

    def test_non_responsible_teacher_dashboard_has_no_tracking_section(self):
        self.client.force_login(self.other_teacher.user)
        response = self.client.get(reverse("teacher_dashboard"))
        self.assertNotContains(response, "پایش برنامه روزانه")

    def test_classroom_form_rejects_responsible_outside_selected_teachers(self):
        form = ClassroomForm(data={
            "academic_year": self.year.id,
            "grade": self.grade.id,
            "name": "یاس ۲",
            "capacity": 30,
            "description": "",
            "teachers": [self.other_teacher.id],
            "daily_report_responsible": self.teacher.id,
        })
        self.assertFalse(form.is_valid())
        self.assertIn("daily_report_responsible", form.errors)


class UserRoleFilterTests(TestCase):
    def test_manager_can_filter_users_by_role(self):
        manager = User.objects.create_user(username="manager", password="pass", role=Role.SCHOOL_MANAGER)
        User.objects.create_user(username="teacher", password="pass", role=Role.TEACHER)
        User.objects.create_user(username="student", password="pass", role=Role.STUDENT)
        self.client.force_login(manager)
        response = self.client.get(reverse("user_list"), {"role": Role.TEACHER})
        self.assertContains(response, "teacher")
        self.assertNotContains(response, ">student<")
