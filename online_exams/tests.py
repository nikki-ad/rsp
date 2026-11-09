import json
import tempfile
from datetime import timedelta
from decimal import Decimal
from io import BytesIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from PIL import Image
from pypdf import PdfWriter
from academic.models import AcademicYear, Classroom, Enrollment, Grade, TeacherClassAssignment
from accounts.models import StudentProfile, TeacherProfile
from language_unit.models import LanguageGroup
from .access import eligible_students
from .formatting import render_text
from .forms import ExamForm
from .models import Exam, Participation, Question
from .services import ensure_report, finalize_due, publish, purge, record, score, start


class ExamTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.admin = User.objects.create_user(username="manager", role="school_manager")
        cls.teacher = User.objects.create_user(username="teacher", role="teacher")
        cls.other_teacher = User.objects.create_user(username="other-teacher", role="teacher")
        cls.teacher_profile = TeacherProfile.objects.create(user=cls.teacher)
        cls.other_profile = TeacherProfile.objects.create(user=cls.other_teacher)
        cls.user = User.objects.create_user(username="student", first_name="نیلوفر", last_name="آزمایشی", role="student")
        cls.student = StudentProfile.objects.create(user=cls.user)
        cls.other_user = User.objects.create_user(username="other", role="student")
        cls.other_student = StudentProfile.objects.create(user=cls.other_user)
        cls.year = AcademicYear.objects.create(title="۱۴۰۵", status="active")
        cls.grade = Grade.objects.create(code="4", title="چهارم", order=4)
        cls.classroom = Classroom.objects.create(name="لاله", grade=cls.grade, academic_year=cls.year, capacity=20)
        cls.other_class = Classroom.objects.create(name="یاس", grade=cls.grade, academic_year=cls.year, capacity=20)
        Enrollment.objects.create(student=cls.student, classroom=cls.classroom, academic_year=cls.year)
        Enrollment.objects.create(student=cls.other_student, classroom=cls.other_class, academic_year=cls.year)
        TeacherClassAssignment.objects.create(teacher=cls.teacher_profile, classroom=cls.classroom)
        TeacherClassAssignment.objects.create(teacher=cls.other_profile, classroom=cls.other_class)

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.settings = override_settings(EXAM_PRIVATE_ROOT=self.directory.name)
        self.settings.enable()
        self.addCleanup(self.directory.cleanup)
        self.addCleanup(self.settings.disable)
        now = timezone.now()
        self.exam = Exam.objects.create(title="آزمون ریاضی", subject="ریاضی", mode="typed", question_count=3,
            duration_minutes=20, opens_at=now - timedelta(hours=1), closes_at=now + timedelta(hours=1),
            created_by=self.teacher)
        for number in range(1, 4):
            Question.objects.create(exam=self.exam, number=number, text=r"حاصل \(\frac{1}{2}\)؟",
                options=["یک", "دو", "سه", "چهار"], correct_option=number)
        self.p = Participation.objects.create(exam=self.exam, student=self.student, classroom_label="چهارم لاله")

    def published(self):
        publish(self.exam.pk, self.teacher)
        self.exam.refresh_from_db()

    def login(self, user=None):
        self.client.force_login(user or self.user)

    def test_scoring_both_modes_blank_and_negative(self):
        key = {1: 1, 2: 2, 3: 3, 4: 4}
        self.assertEqual(score({"1": 1, "2": 1}, key, False), (1, 1, 2, Decimal("25.00")))
        self.assertEqual(score({"1": 1, "2": 1}, key, True), (1, 1, 2, Decimal("16.67")))
        self.assertEqual(score({"1": 2, "2": 1, "3": 1}, {1: 1, 2: 2, 3: 3}, True)[3], Decimal("-33.33"))
        self.assertEqual(score({}, key, True)[3], Decimal("0.00"))

    def test_late_start_hard_deadline_and_refresh(self):
        now = timezone.now()
        self.exam.closes_at = now + timedelta(minutes=5)
        self.exam.save()
        self.published()
        p = start(self.exam.pk, self.student)
        self.assertEqual(p.deadline_at, self.exam.closes_at)
        self.assertEqual(start(self.exam.pk, self.student).started_at, p.started_at)
        self.assertLess(p.deadline_at - p.started_at, timedelta(minutes=6))

    def test_closed_or_future_exam_cannot_start(self):
        self.published()
        with patch("online_exams.services.timezone.now", return_value=self.exam.closes_at):
            with self.assertRaises(ValidationError): start(self.exam.pk, self.student)
        with patch("online_exams.services.timezone.now", return_value=self.exam.opens_at - timedelta(seconds=1)):
            with self.assertRaises(ValidationError): start(self.exam.pk, self.student)

    def test_publish_rejects_missing_options_or_key(self):
        q = self.exam.questions.first(); q.options = ["one"]; q.save()
        with self.assertRaises(ValidationError): publish(self.exam.pk, self.teacher)
        q.options = ["a", "b", "c", "d"]; q.correct_option = None; q.save()
        with self.assertRaises(ValidationError): publish(self.exam.pk, self.teacher)

    def test_autosave_and_submit_are_persistent_and_single_attempt(self):
        self.published(); start(self.exam.pk, self.student)
        record(self.p.pk, number=1, choice=1)
        record(self.p.pk, number=2, choice=4)
        p, accepted = record(self.p.pk, submit=True)
        self.assertTrue(accepted)
        self.assertEqual((p.correct, p.wrong, p.blank), (1, 1, 1))
        original = p.submitted_at
        p, accepted = record(self.p.pk, number=1, choice=2)
        self.assertFalse(accepted); self.assertEqual(p.answers["1"], 1)
        self.assertEqual(start(self.exam.pk, self.student).submitted_at, original)

    def test_expiry_finalizes_without_accepting_late_answer(self):
        self.published(); p = start(self.exam.pk, self.student)
        record(p.pk, number=1, choice=1)
        with patch("online_exams.services.timezone.now", return_value=p.deadline_at):
            p, accepted = record(p.pk, number=2, choice=2)
        self.assertFalse(accepted)
        self.assertEqual(p.answers, {"1": 1}); self.assertEqual(p.percentage, Decimal("33.33"))

    def test_background_finalization_closed_browser_and_report(self):
        self.published(); p = start(self.exam.pk, self.student)
        with self.captureOnCommitCallbacks(execute=True):
            with patch("online_exams.services.timezone.now", return_value=p.deadline_at):
                self.assertEqual(finalize_due(), 1)
        p.refresh_from_db(); self.assertIsNotNone(p.submitted_at)
        self.assertTrue(p.report.storage.exists(p.report.name))
        self.assertTrue(p.report.path.startswith(self.directory.name))
        with p.report.open("rb") as file:
            image = Image.open(file); self.assertEqual(image.format, "PNG")
        self.assertNotIn("/media/", str(p.report.path))

    def test_invalid_answers_do_not_mutate(self):
        self.published(); start(self.exam.pk, self.student)
        for number, choice in [(0, 1), (4, 1), (True, 1), (1, True), (1, 5), (1, "2")]:
            with self.assertRaises(ValidationError): record(self.p.pk, number=number, choice=choice)
        record(self.p.pk, number=1, choice=1); record(self.p.pk, number=1, choice=None)
        self.p.refresh_from_db(); self.assertEqual(self.p.answers, {})

    def completed(self):
        self.published(); start(self.exam.pk, self.student)
        with self.captureOnCommitCallbacks(execute=True):
            record(self.p.pk, number=1, choice=1, submit=True)
        self.p.refresh_from_db()
        self.exam.closes_at = timezone.now() - timedelta(seconds=1)
        self.exam.opens_at = self.exam.closes_at - timedelta(hours=2)
        self.exam.save()

    def test_file_purge_preserves_results_and_never_regenerates(self):
        self.completed(); path = self.p.report.name; storage = self.p.report.storage
        purge(self.exam.pk, self.admin)
        self.p.refresh_from_db(); self.assertFalse(self.p.report)
        self.assertFalse(storage.exists(path)); self.assertEqual(self.p.percentage, Decimal("33.33"))
        ensure_report(self.p.pk); self.p.refresh_from_db(); self.assertFalse(self.p.report)
        self.login(); self.assertContains(self.client.get(reverse("exam_result", args=[self.exam.pk])), "33.33")

    def test_full_purge_erases_answers_scores_and_blocks_retake(self):
        self.completed(); purge(self.exam.pk, self.admin, full=True)
        self.p.refresh_from_db(); self.assertEqual(self.p.answers, {})
        self.assertIsNone(self.p.percentage); self.assertTrue(self.p.result_deleted)
        self.assertFalse(self.p.report)
        with self.assertRaises(ValidationError): start(self.exam.pk, self.student)
        self.login(); self.assertContains(self.client.get(reverse("exam_result", args=[self.exam.pk])), "حذف شده")

    def test_teacher_cannot_purge_or_manage_other_teacher_exam(self):
        from django.core.exceptions import PermissionDenied
        with self.assertRaises(PermissionDenied): purge(self.exam.pk, self.teacher, full=True)
        self.login(self.other_teacher)
        for name in ["exam_detail", "exam_questions", "exam_key"]:
            self.assertEqual(self.client.get(reverse(name, args=[self.exam.pk])).status_code, 404)
        self.assertEqual(self.client.get(reverse("exam_delete_results", args=[self.exam.pk])).status_code, 403)

    def test_student_cannot_manage_or_download_reports_or_read_others(self):
        self.published(); self.login()
        self.assertEqual(self.client.get(reverse("exam_create")).status_code, 403)
        self.assertEqual(self.client.get(reverse("exam_detail", args=[self.exam.pk])).status_code, 404)
        self.assertEqual(self.client.get(reverse("exam_reports_zip", args=[self.exam.pk])).status_code, 404)
        self.login(self.other_user)
        self.assertEqual(self.client.get(reverse("exam_take", args=[self.exam.pk])).status_code, 404)

    def test_teacher_class_and_language_group_scoping(self):
        self.assertEqual(set(eligible_students(self.teacher)), {self.student})
        self.assertEqual(set(eligible_students(self.admin)), {self.student, self.other_student})
        self.teacher_profile.is_language_teacher = True; self.teacher_profile.save()
        group = LanguageGroup.objects.create(title="A", academic_year=self.year)
        group.teachers.add(self.teacher_profile); group.students.add(self.other_student)
        # Reload user: related-object cache may reflect the old teacher flag.
        user = get_user_model().objects.get(pk=self.teacher.pk)
        self.assertEqual(set(eligible_students(user)), {self.other_student})

    def test_exam_html_does_not_contain_key(self):
        self.published(); start(self.exam.pk, self.student); self.login()
        response = self.client.get(reverse("exam_take", args=[self.exam.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "correct_option")
        self.assertNotContains(response, '"correct"')
        self.assertIn("no-store", response.headers["Cache-Control"])
        self.assertNotIn("correct_option", response.context["questions"][0])

    def test_key_hidden_until_window_end_if_requested(self):
        self.exam.show_key_immediately = False; self.exam.save()
        self.published(); start(self.exam.pk, self.student); record(self.p.pk, submit=True); self.login()
        response = self.client.get(reverse("exam_result", args=[self.exam.pk]))
        self.assertFalse(response.context["show_key"])
        self.assertNotContains(response, "<th>پاسخ صحیح</th>", html=True)

    def test_math_and_html_sanitization(self):
        html = str(render_text(r'**سلام** \(\frac{1}{2}+x^2+\sqrt{3}\) <script>alert(1)</script>'))
        self.assertIn("<mfrac>", html); self.assertIn("<msup>", html); self.assertIn("<msqrt>", html)
        self.assertNotIn("<script>", html); self.assertIn("&lt;script&gt;", html)
        self.assertNotIn("href=", str(render_text(r'\(\href{javascript:alert(1)}{x}\)')))
        self.assertIsInstance(render_text(r'\(\frac{\)'), str)

    def exam_data(self):
        return {"subject": "ریاضی", "title": "آزمون", "mode": "typed", "question_count": 2,
            "duration_minutes": 20, "opens_at": "۱۴۰۵/۰۹/۰۱ ۰۸:۰۰", "closes_at": "۱۴۰۵/۰۹/۰۲ ۱۵:۰۰",
            "students": [str(self.student.pk)]}

    def test_jalali_form_dates_and_unauthorized_student(self):
        data = self.exam_data(); form = ExamForm(data, user=self.teacher)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["opens_at"].hour, 8)
        data["students"] = [str(self.other_student.pk)]
        self.assertFalse(ExamForm(data, user=self.teacher).is_valid())

    def test_pdf_validation_and_authenticated_download(self):
        writer = PdfWriter(); writer.add_blank_page(width=200, height=200)
        buffer = BytesIO(); writer.write(buffer)
        data = self.exam_data(); data["mode"] = "pdf"
        form = ExamForm(data, {"question_pdf": SimpleUploadedFile("questions.pdf", buffer.getvalue(), "application/pdf")}, user=self.teacher)
        self.assertTrue(form.is_valid(), form.errors)
        bad = ExamForm(data, {"question_pdf": SimpleUploadedFile("fake.pdf", b"not pdf")}, user=self.teacher)
        self.assertFalse(bad.is_valid())
        self.exam.mode = "pdf"; self.exam.question_pdf.save("q.pdf", SimpleUploadedFile("q.pdf", buffer.getvalue())); self.exam.save()
        self.published(); self.login()
        url = reverse("exam_pdf", args=[self.exam.pk])
        self.assertEqual(self.client.get(url).status_code, 403)
        start(self.exam.pk, self.student)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200); response.close()
        with patch("online_exams.views.timezone.now", return_value=self.exam.closes_at):
            self.assertEqual(self.client.get(url).status_code, 403)

    def test_full_creation_and_typed_editor_routes(self):
        self.login(self.teacher)
        response = self.client.post(reverse("exam_create"), self.exam_data())
        self.assertEqual(response.status_code, 302)
        exam = Exam.objects.exclude(pk=self.exam.pk).get()
        self.assertEqual(exam.participations.count(), 1)
        for number in (1, 2):
            response = self.client.post(reverse("exam_questions", args=[exam.pk]) + f"?number={number}",
                {"text": "سؤال", "option1": "۱", "option2": "۲", "option3": "۳", "option4": "۴", "action": "next"})
            self.assertEqual(response.status_code, 302)
        self.assertEqual(self.client.post(reverse("exam_key", args=[exam.pk]), {"key_1": 1, "key_2": 2}).status_code, 302)
        for name in ("exam_detail", "exam_key", "exam_questions"):
            self.assertEqual(self.client.get(reverse(name, args=[exam.pk])).status_code, 200)
        self.client.post(reverse("exam_publish", args=[exam.pk]))
        exam.refresh_from_db(); self.assertTrue(exam.published)

    def test_answer_endpoint_validation_and_csrf(self):
        self.published(); start(self.exam.pk, self.student); self.login()
        url = reverse("exam_answer", args=[self.exam.pk])
        self.assertEqual(self.client.get(url).status_code, 405)
        self.assertEqual(self.client.post(url, json.dumps({"number": 1, "choice": 1}), content_type="application/json").status_code, 200)
        self.assertEqual(self.client.post(url, "[]", content_type="application/json").status_code, 400)
        from django.test import Client
        secure = Client(enforce_csrf_checks=True); secure.force_login(self.user)
        self.assertEqual(secure.post(url, json.dumps({"number": 1, "choice": 1}), content_type="application/json").status_code, 403)

    def test_admin_and_superuser_delete_views_and_other_roles_create(self):
        User = get_user_model()
        for role in ("operator", "finance", "super_admin", "school_manager"):
            user = User.objects.create_user(username="role-" + role, role=role)
            self.login(user); self.assertEqual(self.client.get(reverse("exam_create")).status_code, 200)
        superuser = User.objects.create_user(username="root", is_superuser=True, role="student")
        for user in (self.admin, superuser):
            self.login(user)
            self.assertEqual(self.client.get(reverse("exam_delete_results", args=[self.exam.pk]) + "?kind=full").status_code, 200)

    def test_absent_only_after_window_and_purge_confirmation(self):
        self.published(); self.login(self.admin)
        response = self.client.get(reverse("exam_detail", args=[self.exam.pk]))
        self.assertContains(response, "شرکت نکرده")
        with patch("online_exams.views.timezone.now", return_value=self.exam.closes_at):
            response = self.client.get(reverse("exam_detail", args=[self.exam.pk]))
        self.assertContains(response, "غایب")
        url = reverse("exam_delete_results", args=[self.exam.pk])
        self.assertEqual(self.client.post(url, {"confirm": "bad"}).status_code, 400)

    def test_draft_metadata_edit_preserves_questions_and_publication_freezes_it(self):
        self.login(self.teacher)
        data = self.exam_data(); data["question_count"] = 2
        response = self.client.post(reverse("exam_edit", args=[self.exam.pk]), data)
        self.assertEqual(response.status_code, 302)
        self.exam.refresh_from_db()
        self.assertEqual(self.exam.questions.count(), 2)
        self.assertTrue(self.exam.questions.first().text)
        self.assertEqual(self.exam.participations.count(), 1)
        self.published()
        self.assertEqual(self.client.post(reverse("exam_edit", args=[self.exam.pk]), data).status_code, 403)

    def test_management_report_download_zip_and_student_denial(self):
        from zipfile import ZipFile
        self.completed(); self.login(self.teacher)
        url = reverse("exam_report", args=[self.exam.pk, self.p.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "image/png")
        self.assertIn("no-store", response["Cache-Control"])
        response.close()
        response = self.client.get(reverse("exam_reports_zip", args=[self.exam.pk]))
        data = b"".join(response.streaming_content); response.close()
        with ZipFile(BytesIO(data)) as archive:
            self.assertEqual(len(archive.namelist()), 1)
        self.login(); self.assertEqual(self.client.get(url).status_code, 404)
        purge(self.exam.pk, self.admin)
        self.login(self.teacher)
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_timer_retries_reports_but_does_not_recreate_purged_files(self):
        from django.core.management import call_command
        self.completed()
        self.p.report.delete(); self.p.refresh_from_db()
        call_command("finalize_exams")
        self.p.refresh_from_db(); self.assertTrue(self.p.report)
        purge(self.exam.pk, self.admin)
        call_command("finalize_exams")
        self.p.refresh_from_db(); self.assertFalse(self.p.report)

    def test_action_links_and_reopen_edit_publish(self):
        self.login(self.teacher)
        self.assertContains(self.client.get(reverse("exam_list")), "حذف آزمون")
        self.published()
        self.assertContains(self.client.get(reverse("exam_list")), "بازگشت به پیش‌نویس")
        url = reverse("exam_reopen", args=[self.exam.pk])
        self.assertEqual(self.client.get(url).status_code, 405)
        self.assertRedirects(self.client.post(url), reverse("exam_edit", args=[self.exam.pk]))
        self.exam.refresh_from_db(); self.assertFalse(self.exam.published)
        self.login()
        self.assertEqual(self.client.get(reverse("exam_take", args=[self.exam.pk])).status_code, 404)
        self.login(self.teacher)
        data = self.exam_data(); data["question_count"] = 3
        self.client.post(reverse("exam_edit", args=[self.exam.pk]), data)
        self.assertEqual(self.exam.questions.count(), 3)
        self.client.post(reverse("exam_publish", args=[self.exam.pk]))
        self.exam.refresh_from_db(); self.assertTrue(self.exam.published)

    def test_started_exam_cannot_reopen_or_be_deleted_while_open(self):
        self.published(); start(self.exam.pk, self.student)
        record(self.p.pk, number=1, choice=2)
        self.login(self.admin)
        self.client.post(reverse("exam_reopen", args=[self.exam.pk]))
        self.exam.refresh_from_db(); self.p.refresh_from_db()
        self.assertTrue(self.exam.published); self.assertEqual(self.p.answers, {"1": 2})
        url = reverse("exam_delete", args=[self.exam.pk])
        self.assertContains(self.client.get(url), "فقط پس از پایان")
        self.client.post(url, {"confirm": str(self.exam.pk)})
        self.assertTrue(Exam.objects.filter(pk=self.exam.pk).exists())
        self.login(self.teacher)
        response = self.client.get(reverse("exam_detail", args=[self.exam.pk]))
        self.assertNotContains(response, 'href="' + url + '"')
        self.assertNotContains(response, "بازگشت به پیش‌نویس و ویرایش")

    def test_delete_confirmation_cascade_files_and_late_requests(self):
        self.exam.question_pdf.save("test.pdf", SimpleUploadedFile("test.pdf", b"%PDF-test"))
        name = self.exam.question_pdf.name; storage = self.exam.question_pdf.storage
        self.published(); self.login(self.teacher)
        url = reverse("exam_delete", args=[self.exam.pk])
        self.assertContains(self.client.get(url), "تأیید حذف کامل آزمون")
        self.assertTrue(Exam.objects.filter(pk=self.exam.pk).exists())
        self.assertEqual(self.client.post(url, {"confirm": "bad"}).status_code, 400)
        with self.captureOnCommitCallbacks(execute=True):
            self.assertRedirects(self.client.post(url, {"confirm": str(self.exam.pk)}), reverse("exam_list"))
        self.assertFalse(Exam.objects.filter(pk=self.exam.pk).exists())
        self.assertFalse(Question.objects.filter(exam_id=self.exam.pk).exists())
        self.assertFalse(Participation.objects.filter(pk=self.p.pk).exists())
        self.assertFalse(storage.exists(name))
        ensure_report(self.p.pk)
        with self.assertRaises(ValidationError): start(self.exam.pk, self.student)
        with self.assertRaises(ValidationError): record(self.p.pk, number=1, choice=1)

    def test_completed_exam_delete_admin_only_and_report_cleanup(self):
        self.completed()
        url = reverse("exam_delete", args=[self.exam.pk])
        self.login(self.teacher)
        self.assertEqual(self.client.post(url, {"confirm": str(self.exam.pk)}).status_code, 403)
        name = self.p.report.name; storage = self.p.report.storage
        self.login(self.admin)
        with self.captureOnCommitCallbacks(execute=True):
            self.assertRedirects(self.client.post(url, {"confirm": str(self.exam.pk)}), reverse("exam_list"))
        self.assertFalse(Exam.objects.filter(pk=self.exam.pk).exists())
        self.assertFalse(storage.exists(name))

    def test_action_permissions_and_csrf(self):
        from django.test import Client
        for user in (self.other_teacher, self.user):
            self.login(user)
            for name in ("exam_delete", "exam_reopen", "exam_edit"):
                self.assertEqual(self.client.post(reverse(name, args=[self.exam.pk]),
                    {"confirm": str(self.exam.pk)}).status_code,
                    403 if user == self.user and name == "exam_edit" else 404)
        secure = Client(enforce_csrf_checks=True); secure.force_login(self.teacher)
        for name in ("exam_delete", "exam_reopen"):
            self.assertEqual(secure.post(reverse(name, args=[self.exam.pk]),
                {"confirm": str(self.exam.pk)}).status_code, 403)
        self.assertTrue(Exam.objects.filter(pk=self.exam.pk).exists())
