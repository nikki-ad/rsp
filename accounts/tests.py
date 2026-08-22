from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from accounts.choices import Role
from accounts.models import StudentProfile


User = get_user_model()

TINY_PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
    "0000000a49444154789c63000100000500010d0a2db40000000049454e44ae426082"
)


class ProfileAvatarTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="student.one",
            password="testpass123",
            first_name="علی",
            last_name="محمدی",
            role=Role.STUDENT,
        )
        StudentProfile.objects.create(user=self.user)
        self.client.force_login(self.user)

    def test_profile_page_renders(self):
        response = self.client.get(reverse("profile"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'enctype="multipart/form-data"')
        self.assertContains(response, "عکس پروفایل")

    def test_avatar_upload(self):
        image = SimpleUploadedFile(
            "avatar.png",
            TINY_PNG,
            content_type="image/png",
        )
        response = self.client.post(
            reverse("profile"),
            {
                "first_name": "علی",
                "last_name": "محمدی",
                "email": "ali@example.com",
                "avatar": image,
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertTrue(self.user.avatar)
        self.assertIn("avatars/", self.user.avatar.name)
