from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from accounts.choices import Role
from accounts.forms import StudentCreateForm
from accounts.models import StudentProfile, TeacherProfile
from academic.models import AcademicYear, Classroom, Enrollment, Grade, TeacherClassAssignment
from assignments.models import Assignment
from cafeteria.models import CafeteriaWeek
from materials.models import EducationalMaterial
from messaging.models import Conversation


User = get_user_model()


class ManagementFeatureTests(TestCase):
    def setUp(self):
        self.manager = User.objects.create_user(
            username="manager",
            password="ManagerPass!2026",
            first_name="مدیر",
            role=Role.SCHOOL_MANAGER,
            is_staff=True,
        )
        self.year = AcademicYear.objects.create(title="۱۴۰۵-۱۴۰۶", status=AcademicYear.Status.ACTIVE)
        self.grade = Grade.objects.create(code="1", title="اول", order=1)
        self.classroom = Classroom.objects.create(
            academic_year=self.year,
            grade=self.grade,
            name="یاس ۱",
            capacity=30,
        )

    def test_student_can_be_created_with_custom_credentials(self):
        form = StudentCreateForm(data={
            "username": "student.custom",
            "password1": "StudentSafePass!2026",
            "password2": "StudentSafePass!2026",
            "first_name": "سارا",
            "last_name": "دانش",
            "academic_year": str(self.year.id),
            "classroom": str(self.classroom.id),
        })
        self.assertTrue(form.is_valid(), form.errors)
        user = form.save(created_by=self.manager)
        self.assertEqual(user.username, "student.custom")
        self.assertTrue(user.check_password("StudentSafePass!2026"))

    def test_manager_can_create_operational_user(self):
        self.client.force_login(self.manager)
        response = self.client.post(reverse("general_user_create"), {
            "username": "finance.user",
            "first_name": "مالی",
            "last_name": "مدرسه",
            "email": "",
            "role": Role.FINANCE,
            "is_active": "on",
            "password1": "FinanceSafePass!2026",
            "password2": "FinanceSafePass!2026",
        })
        self.assertRedirects(response, reverse("user_list"))
        user = User.objects.get(username="finance.user")
        self.assertEqual(user.role, Role.FINANCE)
        self.assertTrue(user.is_staff)
        self.assertTrue(user.check_password("FinanceSafePass!2026"))

    def test_manager_can_create_weekly_menu(self):
        self.client.force_login(self.manager)
        response = self.client.post(reverse("cafeteria_week_create"), {
            "title": "هفته اول مهر",
            "start_date": "2026-09-26",
            "is_active": "on",
            "menus-TOTAL_FORMS": "5",
            "menus-INITIAL_FORMS": "0",
            "menus-MIN_NUM_FORMS": "0",
            "menus-MAX_NUM_FORMS": "5",
            "menus-0-day": "saturday",
            "menus-0-food_name": "عدس پلو",
            "menus-0-description": "",
            "menus-0-price": "150000",
            "menus-1-day": "sunday",
            "menus-1-food_name": "زرشک پلو",
            "menus-1-description": "",
            "menus-1-price": "150000",
            "menus-2-day": "monday",
            "menus-2-food_name": "لوبیا پلو",
            "menus-2-description": "",
            "menus-2-price": "150000",
            "menus-3-day": "tuesday",
            "menus-3-food_name": "ماکارونی",
            "menus-3-description": "",
            "menus-3-price": "150000",
            "menus-4-day": "wednesday",
            "menus-4-food_name": "چلو مرغ",
            "menus-4-description": "",
            "menus-4-price": "150000",
        })
        self.assertRedirects(response, reverse("cafeteria_week_list"))
        week = CafeteriaWeek.objects.get(title="هفته اول مهر")
        self.assertTrue(week.is_active)
        self.assertEqual(week.menus.count(), 5)
        self.assertEqual(week.menus.get(day="saturday").food_name, "عدس پلو")


class StudentExperienceTests(TestCase):
    def setUp(self):
        self.manager = User.objects.create_user(
            username="manager.contact",
            password="pass",
            first_name="مدیر",
            last_name="مدرسه",
            role=Role.SCHOOL_MANAGER,
        )
        self.superuser = User.objects.create_superuser(
            username="system.admin",
            password="pass",
            first_name="مدیر",
            last_name="تست",
        )
        self.student_user = User.objects.create_user(
            username="student",
            password="pass",
            role=Role.STUDENT,
        )
        self.student = StudentProfile.objects.create(user=self.student_user)
        self.teacher_user = User.objects.create_user(
            username="teacher",
            password="pass",
            first_name="معلم",
            last_name="کلاس",
            role=Role.TEACHER,
        )
        self.teacher = TeacherProfile.objects.create(user=self.teacher_user)
        self.other_teacher_user = User.objects.create_user(
            username="other.teacher",
            password="pass",
            role=Role.TEACHER,
        )
        TeacherProfile.objects.create(user=self.other_teacher_user)
        self.year = AcademicYear.objects.create(title="۱۴۰۵-۱۴۰۶", status=AcademicYear.Status.ACTIVE)
        self.grade = Grade.objects.create(code="1", title="اول", order=1)
        self.classroom = Classroom.objects.create(
            academic_year=self.year,
            grade=self.grade,
            name="یاس ۱",
            capacity=30,
        )
        Enrollment.objects.create(
            student=self.student,
            academic_year=self.year,
            classroom=self.classroom,
            is_active=True,
        )
        TeacherClassAssignment.objects.create(teacher=self.teacher, classroom=self.classroom)
        old_material = EducationalMaterial.objects.create(
            teacher=self.teacher,
            title="مطلب قدیمی",
            content_type="text",
            content="قدیمی",
        )
        old_material.classrooms.add(self.classroom)
        new_material = EducationalMaterial.objects.create(
            teacher=self.teacher,
            title="مطلب جدید",
            content_type="text",
            content="جدید",
        )
        new_material.classrooms.add(self.classroom)
        Assignment.objects.create(teacher=self.teacher, classroom=self.classroom, title="تکلیف قدیمی")
        Assignment.objects.create(teacher=self.teacher, classroom=self.classroom, title="تکلیف جدید")
        self.client.force_login(self.student_user)

    def test_dashboard_only_shows_latest_material_and_assignment(self):
        response = self.client.get(reverse("student_dashboard"))
        self.assertContains(response, "مطلب جدید")
        self.assertNotContains(response, "مطلب قدیمی")
        self.assertContains(response, "تکلیف جدید")
        self.assertNotContains(response, "تکلیف قدیمی")

    def test_archive_pages_show_all_items(self):
        material_response = self.client.get(reverse("student_material_list"))
        assignment_response = self.client.get(reverse("student_assignment_list"))
        self.assertContains(material_response, "مطلب جدید")
        self.assertContains(material_response, "مطلب قدیمی")
        self.assertContains(assignment_response, "تکلیف جدید")
        self.assertContains(assignment_response, "تکلیف قدیمی")

    def test_student_sees_teacher_and_manager_as_contacts(self):
        response = self.client.get(reverse("conversation_list"))
        self.assertContains(response, "معلم کلاس")
        self.assertContains(response, "مدیر مدرسه")
        self.assertContains(response, "مدیر تست")
        self.assertContains(response, "مدیر سیستم")

    def test_student_can_start_manager_conversation_but_not_unrelated_teacher(self):
        response = self.client.get(reverse("start_conversation", args=[self.manager.id]))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            Conversation.objects.filter(participant_1=self.student_user, participant_2=self.manager).exists()
            or Conversation.objects.filter(participant_1=self.manager, participant_2=self.student_user).exists()
        )
        forbidden = self.client.get(reverse("start_conversation", args=[self.other_teacher_user.id]))
        self.assertEqual(forbidden.status_code, 403)


class LightThemeTests(SimpleTestCase):
    def test_dark_theme_code_is_removed(self):
        static_root = Path(settings.BASE_DIR) / "static"
        combined = "\n".join(
            path.read_text(encoding="utf-8")
            for path in [
                static_root / "js" / "rsp-prism.js",
                static_root / "css" / "rsp-prism.css",
                static_root / "css" / "rsp-prism-interactions.css",
                static_root / "css" / "weekly_schedule.css",
            ]
        )
        self.assertNotIn("rsp-dark", combined)
        self.assertNotIn("prefers-color-scheme: dark", combined)
        self.assertNotIn("themeButton", combined)
