from django.conf import settings
from django.db import models
from . import constants
from core.models import BaseModel


class Notification(BaseModel):

    TYPE_CHOICES = (
        (constants.MESSAGE, "پیام جدید"),
        (constants.ASSIGNMENT, "تکلیف جدید"),
        (constants.MATERIAL, "مطلب آموزشی جدید"),
        (constants.ANNOUNCEMENT, "اطلاعیه"),
        (constants.CAFETERIA, "رزرو غذا"),
        (constants.SYSTEM, "سیستمی"),
    )

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
        verbose_name="دریافت‌کننده",
    )

    notification_type = models.CharField(
        max_length=30,
        choices=TYPE_CHOICES,
        default="system",
        verbose_name="نوع اعلان",
    )

    title = models.CharField(
        max_length=200,
        verbose_name="عنوان",
    )

    message = models.TextField(
        blank=True,
        verbose_name="متن اعلان",
    )

    url = models.CharField(
        max_length=500,
        blank=True,
        verbose_name="لینک مقصد",
    )

    is_read = models.BooleanField(
        default=False,
        verbose_name="خوانده شده",
    )

    class Meta:
        verbose_name = "اعلان"
        verbose_name_plural = "اعلان‌ها"
        ordering = (
            "-created_at",
        )

    def __str__(self):
        return f"{self.recipient} - {self.title}"



class Announcement(BaseModel):

    class Audience(models.TextChoices):
        ALL = "all", "همه"
        STUDENTS = "students", "دانش‌آموزان"
        TEACHERS = "teachers", "معلمان"
        CLASSROOM = "classroom", "یک کلاس خاص"

    title = models.CharField(
        max_length=200,
        verbose_name="عنوان",
    )

    message = models.TextField(
        verbose_name="متن اطلاعیه",
    )

    audience = models.CharField(
        max_length=20,
        choices=Audience.choices,
        default=Audience.ALL,
        verbose_name="مخاطب",
    )

    publish_at = models.DateTimeField(
        verbose_name="زمان انتشار",
    )

    is_active = models.BooleanField(
        default=True,
        verbose_name="فعال",
    )

    classroom = models.ForeignKey(
        "academic.Classroom",
        on_delete=models.PROTECT,
        related_name="announcements",
        blank=True,
        null=True,
        verbose_name="کلاس مخاطب",
    )


    def clean(self):
        super().clean()

        if self.audience == self.Audience.CLASSROOM and not self.classroom:
            from django.core.exceptions import ValidationError

            raise ValidationError(
                {
                    "classroom": "برای اطلاعیه مخصوص کلاس، انتخاب کلاس الزامی است."
                }
            )

        if self.audience != self.Audience.CLASSROOM:
            self.classroom = None

    class Meta:
        verbose_name = "اطلاعیه عمومی"
        verbose_name_plural = "اطلاعیه‌های عمومی"
        ordering = ["-publish_at"]

    def __str__(self):
        return self.title