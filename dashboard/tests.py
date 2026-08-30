from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from accounts.choices import Role
from academic.models import AcademicYear, Classroom, Grade


User = get_user_model()


class ManagerRoutineReportTests(TestCase):
    def setUp(self):
        self.manager = User.objects.create_user(
            username="manager.report",
            password="pass",
            role=Role.SCHOOL_MANAGER,
        )
        year = AcademicYear.objects.create(
            title="۱۴۰۵-۱۴۰۶",
            status=AcademicYear.Status.ACTIVE,
        )
        grade = Grade.objects.create(code="1", title="اول", order=1)
        Classroom.objects.create(
            academic_year=year,
            grade=grade,
            name="یاس ۱",
            capacity=30,
        )
        self.client.force_login(self.manager)

    def test_dashboard_links_to_separate_report_page_without_full_table(self):
        response = self.client.get(reverse("admin_dashboard"))
        self.assertContains(response, reverse("routine_report_list"))
        self.assertNotContains(response, "routine-print-table")

    def test_report_page_contains_print_and_excel_actions(self):
        response = self.client.get(reverse("routine_report_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "window.print()")
        self.assertContains(response, reverse("routine_report_excel"))

    def test_excel_report_is_valid_xlsx_download(self):
        response = self.client.get(reverse("routine_report_excel"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response["Content-Type"],
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        self.assertTrue(response.content.startswith(b"PK"))
        self.assertIn("daily-routine-report.xlsx", response["Content-Disposition"])
