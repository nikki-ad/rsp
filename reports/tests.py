import tempfile
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase, TransactionTestCase, override_settings
from django.urls import reverse

from academic.models import AcademicYear, Classroom, Enrollment, Grade
from accounts.choices import Role
from accounts.models import StudentProfile
from dashboard.forms import ReportCardForm
from .models import ReportCardPeriod, StudentReportCard

User = get_user_model()


class ReportCardWorkflowTests(TestCase):
    def setUp(self):
        self.media = tempfile.TemporaryDirectory()
        self.addCleanup(self.media.cleanup)
        self.settings_override = override_settings(MEDIA_ROOT=self.media.name)
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)
        self.manager = User.objects.create_user(username="manager", role=Role.SCHOOL_MANAGER)
        self.student = StudentProfile.objects.create(user=User.objects.create_user(username="student", first_name="علی", last_name="کریمی", role=Role.STUDENT))
        self.other = StudentProfile.objects.create(user=User.objects.create_user(username="other", role=Role.STUDENT))
        self.year = AcademicYear.objects.create(title="1405-1406", status="active")
        grade = Grade.objects.create(code="1", title="اول", order=1)
        self.classroom = Classroom.objects.create(academic_year=self.year, grade=grade, name="یاس", capacity=30)
        Enrollment.objects.create(student=self.student, academic_year=self.year, classroom=self.classroom)
        self.period = ReportCardPeriod.objects.create(title="کارنامه ماهیانه مهر", academic_year=self.year)
        self.client.force_login(self.manager)

    def upload(self, name="report.pdf", student=None):
        return self.client.post(reverse("report_card_create"), {
            "period": self.period.pk, "student": (student or self.student).pk,
            "file": SimpleUploadedFile(name, b"%PDF-1.4\nreport content"), "is_active": "on",
        })

    def test_upload_pdf_and_images_and_keep_period_for_next_student(self):
        for ext in ("pdf", "jpg", "jpeg", "png", "webp"):
            with self.subTest(ext=ext):
                response = self.upload("report." + ext)
                self.assertRedirects(response, reverse("report_card_create") + "?period=" + str(self.period.pk))
                card = StudentReportCard.objects.get()
                self.assertEqual(card.title, self.period.title)
                self.assertEqual(card.created_by, self.manager)
                card.delete()

    def test_reject_unsupported_extension_and_unselected_student(self):
        self.assertEqual(self.upload("report.html").status_code, 200)
        self.assertFalse(StudentReportCard.objects.exists())
        form = ReportCardForm(data={"period": self.period.pk}, files={"file": SimpleUploadedFile("r.pdf", b"%PDF-1.4")})
        self.assertFalse(form.is_valid())
        self.assertIn("student", form.errors)

    def test_duplicate_upload_requires_editing_existing_file(self):
        self.upload()
        self.assertContains(self.upload(), "فایل قبلی را ویرایش کنید")
        self.assertEqual(StudentReportCard.objects.count(), 1)

    def test_edit_keeps_student_period_and_can_replace_file(self):
        self.upload()
        card = StudentReportCard.objects.get()
        response = self.client.get(reverse("report_card_edit", args=[card.pk]))
        self.assertEqual(response.context["form"]["period"].value(), card.period_id)
        self.assertEqual(response.context["form"]["student"].value(), card.student_id)
        response = self.client.post(reverse("report_card_edit", args=[card.pk]), {
            "period": self.period.pk, "student": self.student.pk,
            "file": SimpleUploadedFile("replacement.png", b"image"), "is_active": "on",
        })
        self.assertEqual(response.status_code, 302)
        card.refresh_from_db()
        self.assertTrue(card.file.name.endswith(".png"))

    def test_period_class_student_navigation_and_missing_upload(self):
        self.assertContains(self.client.get(reverse("report_card_list")), self.period.title)
        self.assertContains(self.client.get(reverse("report_card_period_detail", args=[self.period.pk])), str(self.classroom))
        url = reverse("report_card_class_detail", args=[self.period.pk, self.classroom.pk])
        self.assertContains(self.client.get(url), "هنوز بارگذاری نشده")
        self.upload()
        self.assertContains(self.client.get(url), "دانلود فایل کارنامه")
        self.assertNotContains(self.client.get(url), "هنوز بارگذاری نشده")

    def test_unassigned_upload_and_other_year_class_is_rejected(self):
        self.upload(student=self.other)
        url = reverse("report_card_period_detail", args=[self.period.pk]) + "?unassigned=1"
        self.assertContains(self.client.get(url), "other")
        other_year = AcademicYear.objects.create(title="1404-1405")
        self.period.academic_year = other_year
        self.period.save()
        self.assertEqual(self.client.get(reverse("report_card_class_detail", args=[self.period.pk, self.classroom.pk])).status_code, 404)

    def test_download_ownership_inactive_and_manager_access(self):
        self.upload()
        card = StudentReportCard.objects.get()
        url = reverse("download_report_card", args=[card.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertIn("attachment", response["Content-Disposition"])
        response.close()
        self.client.force_login(self.other.user)
        self.assertEqual(self.client.get(url).status_code, 404)
        self.client.force_login(self.student.user)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        response.close()
        card.is_active = False
        card.save()
        self.assertEqual(self.client.get(url).status_code, 404)
        self.client.force_login(self.manager)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        response.close()

    def test_student_page_groups_by_period_and_no_other_student_files(self):
        self.upload()
        self.upload(student=self.other)
        own = StudentReportCard.objects.get(student=self.student)
        other = StudentReportCard.objects.get(student=self.other)
        self.client.force_login(self.student.user)
        response = self.client.get(reverse("student_report_cards"))
        self.assertContains(response, self.period.title, count=1)
        self.assertContains(response, reverse("download_report_card", args=[own.pk]))
        self.assertNotContains(response, reverse("download_report_card", args=[other.pk]))

    def test_dashboard_has_sidebar_link_without_report_content(self):
        self.upload()
        self.client.force_login(self.student.user)
        response = self.client.get(reverse("student_dashboard"))
        self.assertContains(response, reverse("student_report_cards"))
        self.assertNotContains(response, self.period.title)
        self.assertNotContains(response, 'id="report-cards"')

    def test_report_page_access_and_empty_state(self):
        url = reverse("student_report_cards")
        self.assertEqual(self.client.get(url).status_code, 403)
        self.client.logout()
        self.assertEqual(self.client.get(url).status_code, 302)
        self.client.force_login(self.student.user)
        self.assertContains(self.client.get(url), "هنوز کارنامه‌ای ثبت نشده است.")

    def test_report_page_hides_inactive_cards(self):
        self.upload()
        StudentReportCard.objects.update(is_active=False)
        self.client.force_login(self.student.user)
        response = self.client.get(reverse("student_report_cards"))
        self.assertNotContains(response, self.period.title)
        self.assertContains(response, "هنوز کارنامه‌ای ثبت نشده است.")

    def test_student_cannot_manage_periods_or_upload(self):
        self.client.force_login(self.student.user)
        for name in ("report_card_list", "report_card_create", "report_card_period_create"):
            self.assertEqual(self.client.get(reverse(name)).status_code, 403)

    def test_search_is_text_input_and_contains_class_disambiguation(self):
        response = self.client.get(reverse("report_card_create"))
        self.assertContains(response, 'id="id_student_search"')
        self.assertContains(response, 'type="hidden" name="student"')
        self.assertNotContains(response, '<select name="student"')
        choices = response.context["form"].student_choices
        self.assertTrue(any("کریمی" in s["label"] and "یاس" in s["label"] for s in choices))

    def test_create_period_requires_year_and_allows_same_month_in_another_year(self):
        url = reverse("report_card_period_create")
        response = self.client.post(url, {"title": "آبان"})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(ReportCardPeriod.objects.filter(title="آبان").exists())
        response = self.client.post(url, {"title": "آبان", "academic_year": self.year.pk})
        self.assertRedirects(response, reverse("report_card_list"))
        self.assertEqual(ReportCardPeriod.objects.get(title="آبان").created_by, self.manager)


class ReportCardMigrationTests(TransactionTestCase):
    def test_existing_files_and_duplicate_titles_survive_backfill(self):
        executor = MigrationExecutor(connection)
        executor.migrate([("reports", "0001_initial")])
        try:
            apps = executor.loader.project_state([("reports", "0001_initial")]).apps
            OldUser = apps.get_model("accounts", "CustomUser")
            Student = apps.get_model("accounts", "StudentProfile")
            Card = apps.get_model("reports", "StudentReportCard")
            student = Student.objects.create(user=OldUser.objects.create(username="legacy"))
            ids = [Card.objects.create(student=student, title="مهر", file=f"report_cards/old{i}.pdf").pk for i in range(2)]
            executor = MigrationExecutor(connection)
            executor.migrate([("reports", "0002_alter_studentreportcard_file_and_more")])
            cards = StudentReportCard.objects.filter(pk__in=ids)
            self.assertEqual(cards.count(), 2)
            self.assertEqual(len(set(cards.values_list("period_id", flat=True))), 1)
            self.assertEqual(ReportCardPeriod.objects.filter(title="مهر").count(), 1)
            self.assertEqual(set(cards.values_list("file", flat=True)), {"report_cards/old0.pdf", "report_cards/old1.pdf"})
            self.assertIsNone(cards.first().period.academic_year_id)
        finally:
            executor = MigrationExecutor(connection)
            executor.migrate(executor.loader.graph.leaf_nodes())
