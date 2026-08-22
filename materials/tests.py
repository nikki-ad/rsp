from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from academic.models import AcademicYear, Classroom, Grade, TeacherClassAssignment
from accounts.choices import Role
from accounts.models import TeacherProfile
from materials.models import EducationalMaterial


User = get_user_model()


class TeacherMaterialClassroomTests(TestCase):
    def setUp(self):
        self.year = AcademicYear.objects.create(
            title="1405-1406",
            status=AcademicYear.Status.ACTIVE,
        )
        self.grade = Grade.objects.create(
            code="1",
            title="اول",
            order=1,
        )
        self.assigned_class = Classroom.objects.create(
            academic_year=self.year,
            grade=self.grade,
            name="یاس ۱",
            capacity=20,
        )
        self.other_class = Classroom.objects.create(
            academic_year=self.year,
            grade=self.grade,
            name="یاس ۲",
            capacity=20,
        )

        self.teacher_user = User.objects.create_user(
            username="teacher.one",
            password="testpass123",
            first_name="سارا",
            last_name="معلم",
            role=Role.TEACHER,
        )
        self.teacher = TeacherProfile.objects.create(user=self.teacher_user)
        TeacherClassAssignment.objects.create(
            teacher=self.teacher,
            classroom=self.assigned_class,
        )
        self.client.force_login(self.teacher_user)

    def test_create_form_only_lists_assigned_classrooms(self):
        response = self.client.get(reverse("create_material"))
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn(str(self.assigned_class.id), html)
        self.assertNotIn(str(self.other_class.id), html)
        self.assertContains(response, "یاس ۱")
        self.assertNotContains(response, "یاس ۲")

    def test_cannot_publish_to_unassigned_classroom(self):
        response = self.client.post(
            reverse("create_material"),
            {
                "title": "آزمون",
                "content_type": "text",
                "content": "متن مطلب",
                "classrooms": [self.other_class.id],
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(EducationalMaterial.objects.count(), 0)
        self.assertTrue(response.context["form"].errors.get("classrooms"))

    def test_can_publish_to_assigned_classroom(self):
        response = self.client.post(
            reverse("create_material"),
            {
                "title": "آزمون",
                "content_type": "text",
                "content": "متن مطلب",
                "classrooms": [self.assigned_class.id],
            },
        )
        self.assertEqual(response.status_code, 302)
        material = EducationalMaterial.objects.get()
        self.assertEqual(list(material.classrooms.all()), [self.assigned_class])

    def test_class_detail_create_hides_classroom_picker(self):
        response = self.client.get(
            reverse("create_class_material", args=[self.assigned_class.id])
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'name="classrooms"')

    def test_cannot_open_create_for_unassigned_class(self):
        response = self.client.get(
            reverse("create_class_material", args=[self.other_class.id])
        )
        self.assertEqual(response.status_code, 404)
