from datetime import date
from io import BytesIO
from xml.etree import ElementTree as ET
from zipfile import ZipFile

from django.contrib.auth import get_user_model
from django.test import TestCase, SimpleTestCase
from django.urls import reverse

from accounts.permissions import post_login_redirect_name
from dashboard.deficiency_xlsx import build_deficiency_report_xlsx
from .homework_models import HomeworkDeficiency
from . import test_homework_deficiencies as fixtures


NS = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}


def inspect_xlsx(content):
    with ZipFile(BytesIO(content)) as archive:
        for path in archive.namelist():
            if path.endswith((".xml", ".rels")):
                ET.fromstring(archive.read(path))
        workbook = ET.fromstring(archive.read("xl/workbook.xml"))
        names = [s.attrib["name"] for s in workbook.find("s:sheets", NS)]
        sheets = []
        for i in range(1, len(names)+1):
            sheet = ET.fromstring(archive.read(f"xl/worksheets/sheet{i}.xml"))
            rows = [["".join(cell.itertext()) for cell in row] for row in sheet.find("s:sheetData", NS)]
            sheets.append((sheet, rows))
        return names, sheets


class DeficiencyReportTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        fixtures.HomeworkDeficiencyTests.setUpTestData.__func__(cls)
        User = get_user_model()
        cls.manager = User.objects.create_user(username="report-manager", role="school_manager")
        cls.super_admin = User.objects.create_user(username="report-super", role="super_admin")
        cls.superuser = User.objects.create_user(username="report-root", role="student", is_superuser=True)
        cls.operator = User.objects.create_user(username="report-operator", role="operator")
        cls.finance = User.objects.create_user(username="report-finance", role="finance")
        for student, classroom, day in [(cls.students[0], cls.classroom, 1), (cls.students[0], cls.classroom, 2),
                                        (cls.students[0], cls.classroom, 3), (cls.students[2], cls.other_classroom, 2)]:
            HomeworkDeficiency.objects.create(teacher=cls.teacher, student=student, classroom=classroom,
                                             record_date=date(2026, 10, day), subject="ریاضی")

    def setUp(self):
        self.client.force_login(self.manager)
        self.url = reverse("deficiency_report_download")
        self.query = {"start_date": "۱۴۰۵/۰۷/۱۰", "end_date": "۱۴۰۵/۰۷/۱۱"}  # Oct 2–3 inclusive.

    def test_single_workbook_class_sheets_and_inclusive_dates(self):
        response = self.client.get(self.url, self.query)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        self.assertIn("attachment", response["Content-Disposition"])
        self.assertIn("no-store", response["Cache-Control"])
        names, sheets = inspect_xlsx(response.content)
        self.assertEqual(len(names), 2)
        self.assertTrue(any(self.classroom.name in name for name in names))
        self.assertTrue(any(self.other_classroom.name in name for name in names))
        rows = [row for _, data in sheets for row in data[1:]]
        self.assertEqual(len(rows), 3)
        self.assertEqual({row[2] for row in rows}, {"1405/07/10", "1405/07/11"})
        self.assertEqual({row[3] for row in rows}, {"مریم احمدی"})
        for xml, data in sheets:
            self.assertEqual(data[0], ["نام دانش‌آموز", "نام درس", "تاریخ ثبت نقص تکلیف", "نام معلم"])
            self.assertEqual(xml.find("s:sheetViews/s:sheetView", NS).get("rightToLeft"), "1")
            self.assertIsNotNone(xml.find("s:autoFilter", NS))

    def test_all_requested_roles_and_dashboard_button(self):
        for user in [self.manager, self.super_admin, self.superuser, self.operator]:
            with self.subTest(user=user):
                self.client.force_login(user)
                self.assertEqual(self.client.get(self.url, self.query).status_code, 200)
                self.assertContains(self.client.get(reverse("admin_dashboard")), "data-deficiency-report-open")
                self.assertEqual(self.client.get(reverse("deficiency_report_calendar"), {"year": 1403, "month": 12}).json()["days"], 30)

    def test_operator_access_does_not_grant_other_management_permissions(self):
        self.client.force_login(self.operator)
        self.assertEqual(post_login_redirect_name(self.operator), "admin_dashboard")
        response = self.client.get(reverse("admin_dashboard"))
        self.assertContains(response, reverse("deficiency_report_filter"))
        self.assertNotContains(response, reverse("general_user_create"))
        for route in ["user_list", "routine_report_excel", "student_list"]:
            self.assertEqual(self.client.get(reverse(route)).status_code, 403)

    def test_unprivileged_roles_cannot_filter_download_or_view_calendar(self):
        for user in [self.teacher_user, self.language_user, self.students[0].user, self.finance]:
            self.client.force_login(user)
            for route in ["deficiency_report_filter", "deficiency_report_download", "deficiency_report_calendar"]:
                self.assertEqual(self.client.get(reverse(route), self.query).status_code, 403)
        self.client.logout()
        self.assertEqual(self.client.get(self.url, self.query).status_code, 302)

    def test_invalid_ranges_return_errors_in_modal_and_normal_page(self):
        for query in [{}, {**self.query, "start_date": "invalid"},
                      {"start_date": "1405/07/12", "end_date": "1405/07/11"},
                      {"start_date": "1404/12/30", "end_date": "1405/01/01"}]:
            response = self.client.get(self.url, query, HTTP_ACCEPT="application/json")
            self.assertEqual(response.status_code, 400)
            self.assertTrue(response.json()["errors"])
        response = self.client.get(self.url, {})
        self.assertEqual(response.status_code, 400)
        self.assertContains(response, "deficiency-report-form", status_code=400)

    def test_empty_range_has_valid_informative_sheet(self):
        response = self.client.get(self.url, {"start_date": "1400/01/01", "end_date": "1400/01/02"})
        names, sheets = inspect_xlsx(response.content)
        self.assertEqual(names, ["بدون نقص تکلیف"])
        self.assertIn("ثبت نشده", sheets[0][1][1][0])

    def test_same_day_and_archived_classes_are_included(self):
        self.year.status = "archived"
        self.year.save()
        response = self.client.get(self.url, {"start_date": "1405/07/10", "end_date": "1405/07/10"})
        _, sheets = inspect_xlsx(response.content)
        self.assertEqual(sum(len(rows)-1 for _, rows in sheets), 2)

    def test_page_renders_both_jalali_inputs(self):
        response = self.client.get(reverse("deficiency_report_filter"))
        self.assertContains(response, 'name="start_date"')
        self.assertContains(response, 'name="end_date"')
        self.assertContains(response, 'data-jalali="date"', count=2)


class DeficiencyWorkbookTests(SimpleTestCase):
    def test_names_collisions_xml_characters_and_formula_safety(self):
        label = "'" + 'کلاس "الف" / [] : ? * ' * 5
        content = build_deficiency_report_xlsx([
            (label, [["=HYPERLINK(\"evil\")", "درس\x00 & <", "1405/01/01", "معلم"]]),
            (label, [["دانش‌آموز", "ریاضی", "1405/01/02", "معلم"]]),
        ])
        names, sheets = inspect_xlsx(content)
        self.assertEqual(len(set(names)), 2)
        for name in names:
            self.assertLessEqual(len(name), 31)
            self.assertNotRegex(name, r"[\\/*?:\[\]]")
        self.assertEqual(sheets[0][1][1][1], "درس & <")
        self.assertTrue(sheets[0][1][1][0].startswith("=HYPERLINK"))
        self.assertFalse(sheets[0][0].findall(".//s:f", NS))
