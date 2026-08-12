import uuid

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models
from core.models import BaseModel
from .choices import Role




class CustomUser(AbstractUser):
    """
    Base user model for the entire system.
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        verbose_name="شناسه",
    )

    role = models.CharField(
        max_length=30,
        choices=Role.choices,
        default=Role.STUDENT,
        verbose_name="نقش",
    )

    class Meta:
        verbose_name = "کاربر"
        verbose_name_plural = "کاربران"

    def __str__(self) -> str:
        full_name = self.get_full_name()
        if full_name:
            return full_name
        return self.username


class StudentProfile(BaseModel):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="student_profile",
        verbose_name="کاربر",
    )

    national_code = models.CharField(
        max_length=10,
        unique=True,
        null=True,
        blank=True,
        verbose_name="کد ملی"
    )


    birth_date = models.DateField(
        null=True,
        blank=True,
        verbose_name="تاریخ تولد",
    )

    guardian_name = models.CharField(
        max_length=100,
        verbose_name="نام ولی",
    )

    guardian_phone = models.CharField(
        max_length=20,
        verbose_name="شماره تماس ولی",
    )

    address = models.TextField(
        blank=True,
        verbose_name="آدرس",
    )

    class Meta:
        verbose_name = "پروفایل دانش‌آموز"
        verbose_name_plural = "پروفایل‌های دانش‌آموز"

    def __str__(self) -> str:
        return self.user.get_full_name() or self.user.username



class TeacherProfile(BaseModel):

    user = models.OneToOneField(
        "accounts.CustomUser",
        on_delete=models.CASCADE,
        related_name="teacher_profile",
        verbose_name="کاربر",
    )

    personnel_code = models.CharField(
        max_length=20,
        null=True,
        blank=True,
        unique=True,
        verbose_name="کد پرسنلی",
    )

    expertise = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        verbose_name="تخصص",
    )

    description = models.TextField(
        null=True,
        blank=True,
        verbose_name="توضیحات",
    )

    class Meta:
        verbose_name = "پروفایل معلم"
        verbose_name_plural = "پروفایل‌های معلم"

    def __str__(self):
        return self.user.get_full_name()



