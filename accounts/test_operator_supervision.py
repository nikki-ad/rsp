from datetime import timedelta
from io import BytesIO
from tempfile import TemporaryDirectory
from unittest.mock import patch
from zipfile import ZipFile

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from academic.models import AcademicYear, Classroom, Enrollment, Grade
from accounts.models import StudentProfile, TeacherProfile
from assignments.models import Assignment
from core.jalali import jalali_format
from language_unit.models import LanguageAssignment, LanguageGroup
from notifications.models import Announcement
from online_classes.models import BBBConfiguration, OnlineClass
from online_exams.models import Exam, Participation
from reports.models import ReportCardPeriod, StudentReportCard


User = get_user_model()


class OperatorSupervisionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.operator = User.objects.create_user(username="operator-scope", role="operator")
        cls.manager = User.objects.create_user(username="manager-scope", role="school_manager")
        cls.year = AcademicYear.objects.create(title="Test year", status="active")
        grade = Grade.objects.create(code="2", title="Second", order=2)
        cls.room = Classroom.objects.create(academic_year=cls.year, grade=grade, name="Visible room", capacity=20)
        cls.other_room = Classroom.objects.create(academic_year=cls.year, grade=grade, name="Hidden room", capacity=20)
        cls.operator.supervised_classrooms.add(cls.room)
        cls.teacher = TeacherProfile.objects.create(user=User.objects.create_user(
            username="class-teacher", role="teacher",
        ))
        cls.student = StudentProfile.objects.create(user=User.objects.create_user(
            username="class-student", first_name="VisibleStudent",
        ))
        cls.other_student = StudentProfile.objects.create(user=User.objects.create_user(
            username="other-student", first_name="HiddenStudent",
        ))
        Enrollment.objects.create(student=cls.student, classroom=cls.room, academic_year=cls.year)
        Enrollment.objects.create(student=cls.other_student, classroom=cls.other_room, academic_year=cls.year)

    def setUp(self):
        self.client.force_login(self.operator)
        self.files = TemporaryDirectory()
        self.addCleanup(self.files.cleanup)
        settings = self.settings(MEDIA_ROOT=self.files.name, EXAM_PRIVATE_ROOT=self.files.name)
        settings.enable()
        self.addCleanup(settings.disable)

    def test_manager_can_assign_operator_classrooms(self):
        self.client.force_login(self.manager)
        response = self.client.post(reverse("general_user_create"), {
            "username": "new-class-operator", "role": "operator", "is_active": "on",
            "password1": "Switchboard-2658-Blue", "password2": "Switchboard-2658-Blue",
            "supervised_classrooms": [self.room.pk],
        })
        self.assertRedirects(response, reverse("user_list"))
        self.assertEqual(
            list(User.objects.get(username="new-class-operator").supervised_classrooms.all()),
            [self.room],
        )

    def test_class_and_file_permissions_are_enforced_on_direct_requests(self):
        response = self.client.get(reverse("classroom_list"))
        self.assertContains(response, self.room.name)
        self.assertNotContains(response, self.other_room.name)
        self.assertEqual(self.client.get(reverse("manager_class_assignments", args=[self.other_room.pk])).status_code, 404)
        for room, expected in [(self.room, 200), (self.other_room, 404)]:
            assignment = Assignment.objects.create(classroom=room, teacher=self.teacher, title="Lesson")
            assignment.file.save("worksheet.pdf", ContentFile(b"worksheet"))
            self.assertEqual(self.client.get(reverse("download_assignment_file", args=[assignment.pk])).status_code, expected)
            self.assertEqual(self.client.get(assignment.file.url).status_code, expected)
            self.assertEqual(self.client.post(reverse("delete_assignment", args=[assignment.pk])).status_code, 403)

    def test_announcement_rejects_forged_targets_and_forces_class_audience(self):
        url = reverse("announcement_create")
        data = {
            "title": "Operator announcement", "message": "A class message",
            "is_active": "on", "publish_at": jalali_format(timezone.now(), with_time=True),
            "audience": "all", "teachers": [self.teacher.pk],
        }
        self.assertEqual(self.client.post(url, {**data, "classrooms": [self.room.pk, self.other_room.pk]}).status_code, 200)
        self.assertFalse(Announcement.objects.exists())
        self.assertRedirects(self.client.post(url, {**data, "classrooms": [self.room.pk]}), reverse("admin_dashboard"))
        announcement = Announcement.objects.get()
        self.assertEqual(announcement.audience, Announcement.Audience.STUDENTS)
        self.assertTrue(announcement.targeted)
        self.assertEqual(list(announcement.classrooms.all()), [self.room])
        self.assertFalse(announcement.teachers.exists())

    def test_language_visibility_excludes_roster_and_mutations(self):
        group = LanguageGroup.objects.create(title="Language group", academic_year=self.year)
        group.students.add(self.other_student)
        assignment = LanguageAssignment.objects.create(group=group, teacher=self.teacher, title="Language worksheet")
        self.assertContains(self.client.get(reverse("manage_language_groups")), group.title)
        response = self.client.get(reverse("language_group_assignment_list", args=[group.pk]))
        self.assertContains(response, assignment.title)
        self.assertNotContains(response, self.other_student.user.first_name)
        for route in ("delete_language_assignment", "edit_language_assignment", "language_assignment_submissions"):
            self.assertEqual(self.client.post(reverse(route, args=[assignment.pk])).status_code, 403)

    def test_exam_reports_are_scoped_even_inside_a_shared_exam(self):
        now = timezone.now()
        exam = Exam.objects.create(title="Shared exam", subject="Math", mode="typed", published=True,
                                   opens_at=now - timedelta(hours=2), closes_at=now + timedelta(minutes=10))
        visible = Participation.objects.create(exam=exam, student=self.student, classroom=self.room, submitted_at=now)
        hidden = Participation.objects.create(exam=exam, student=self.other_student, classroom=self.other_room, submitted_at=now)
        for entry in (visible, hidden):
            entry.report.save("operator-test.png", ContentFile(b"report"))
        index = self.client.get(reverse("exam_list"))
        self.assertContains(index, exam.title)
        detail = reverse("exam_detail", args=[exam.pk])
        individual = reverse("exam_report", args=[exam.pk, visible.pk])
        bulk = reverse("exam_reports_zip", args=[exam.pk])
        for url in (detail, individual, bulk):
            self.assertEqual(self.client.get(url).status_code, 404)
        Exam.objects.filter(pk=exam.pk).update(closes_at=now)
        self.assertContains(self.client.get(detail), self.student.user.first_name)
        self.assertNotContains(self.client.get(detail), self.other_student.user.first_name)
        self.assertEqual(self.client.get(individual).status_code, 200)
        self.assertEqual(self.client.get(reverse("exam_report", args=[exam.pk, hidden.pk])).status_code, 404)
        with ZipFile(BytesIO(b"".join(self.client.get(bulk).streaming_content))) as archive:
            self.assertEqual(archive.namelist(), [f"report-{visible.pk}.png"])
        self.assertEqual(self.client.post(reverse("exam_edit", args=[exam.pk])).status_code, 403)

    def test_school_reports_and_contact_directory(self):
        period = ReportCardPeriod.objects.create(title="First period", academic_year=self.year)
        for student, expected in [(self.student, 200), (self.other_student, 404)]:
            card = StudentReportCard.objects.create(period=period, student=student)
            card.file.save("test-report.pdf", ContentFile(b"report"))
            self.assertEqual(self.client.get(reverse("download_report_card", args=[card.pk])).status_code, expected)
            self.assertEqual(self.client.get(card.file.url).status_code, expected)
        for route in ("student_list", "teacher_list", "user_list", "academic_year_list",
                      "weekly_reservation", "report_card_create", "conversation_list", "load_classrooms"):
            self.assertEqual(self.client.get(reverse(route)).status_code, 403)
        self.client.force_login(self.manager)
        self.assertNotContains(self.client.get(reverse("user_list_for_messaging")), self.operator.username)
        self.assertEqual(self.client.get(reverse("start_conversation", args=[self.operator.pk])).status_code, 404)

    def test_online_operator_entry_and_live_attendance(self):
        config = BBBConfiguration.objects.create(name="BBB", api_url="https://class.example/api/", secret="test")
        room = OnlineClass.objects.create(title="Online room", academic_year=self.year, bbb_configuration=config)
        room.students.add(self.student)
        listing = self.client.get(reverse("online_class_list"))
        self.assertContains(listing, reverse("live_attendance", args=[room.pk]))
        with patch("online_classes.views.register_attendance_hook"), patch(
            "online_classes.views.create_bbb_meeting"
        ), patch(
            "online_classes.views.build_bbb_join_url", return_value="https://class.example/join"
        ) as join:
            self.assertEqual(self.client.get(reverse("join_online_class", args=[room.pk])).status_code, 302)
            self.assertEqual(join.call_args.kwargs["role"], "moderator")
        snapshot = {"running": True, "session_id": "test-meeting", "attendees": [{"user_id": str(self.student.user_id)}]}
        with patch("online_classes.views.get_bbb_live_snapshot", return_value=snapshot) as live:
            response = self.client.get(reverse("live_attendance", args=[room.pk]))
            self.assertContains(response, self.student.user.first_name)
            self.assertNotContains(response, reverse("enable_attendance_tracking", args=[room.pk]))
            live.assert_called_once_with(room)

    def test_exam_selected_from_language_does_not_use_school_classroom(self):
        group = LanguageGroup.objects.create(title="Language group", academic_year=self.year)
        group.students.add(self.student)
        self.client.force_login(self.manager)
        now = timezone.now()
        data = {
            "title": "Language exam", "subject": "English", "mode": "typed",
            "duration_minutes": 20, "question_count": 1,
            "opens_at": jalali_format(now, with_time=True),
            "closes_at": jalali_format(now + timedelta(hours=1), with_time=True),
            "group_students": [f"{group.pk}:{self.student.pk}"],
        }
        response = self.client.post(reverse("exam_create"), data)
        self.assertEqual(response.status_code, 302)
        participant = Participation.objects.get()
        self.assertIsNone(participant.classroom_id)
        self.assertIn(group.title, participant.classroom_label)
        self.assertContains(self.client.get(reverse("exam_edit", args=[participant.exam_id])),
                            f'value="{group.pk}:{self.student.pk}"')
        self.client.force_login(self.operator)
        self.assertNotContains(self.client.get(reverse("exam_list")), participant.exam.title)

    def test_skyroom_operator_join_creates_a_short_lived_room_link(self):
        room_url = "https://www.skyroom.online/ch/school/classroom"
        room = OnlineClass.objects.create(title="Skyroom room", academic_year=self.year,
                                          provider="skyroom", skyroom_url=room_url)
        join_url = reverse("join_online_class", args=[room.pk])
        self.assertRedirects(self.client.get(join_url), room_url, fetch_redirect_response=False)
        with self.settings(RSP_SKYROOM_API_URL="https://www.skyroom.online/skyroom/api/example"), patch(
            "online_classes.skyroom.requests.post"
        ) as post:
            post.return_value.json.side_effect = [
                {"ok": True, "result": {"id": 42}},
                {"ok": True, "result": room_url + "/t/example"},
            ]
            self.assertRedirects(self.client.get(join_url), room_url + "/t/example", fetch_redirect_response=False)
            self.assertEqual(post.call_args_list[0].kwargs["json"]["params"], {"name": "classroom"})
            params = post.call_args_list[1].kwargs["json"]["params"]
            self.assertEqual((params["room_id"], params["access"], params["ttl"]), (42, 3, 120))
            self.assertEqual(params["user_id"], str(self.operator.pk))
            self.assertFalse(post.call_args.kwargs["allow_redirects"])
