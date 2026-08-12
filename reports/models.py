from django.db import models

from core.models import BaseModel
from django.core.validators import FileExtensionValidator

class StudentReportCard(BaseModel):

    student = models.ForeignKey(
        "accounts.StudentProfile",
        on_delete=models.CASCADE,
        related_name="report_cards",
        verbose_name="دانش‌آموز",
    )

    title = models.CharField(
        max_length=200,
        verbose_name="عنوان کارنامه",
    )

    file = models.FileField(
        upload_to="report_cards/",
        validators=[
            FileExtensionValidator(
                allowed_extensions=["pdf"],
            ),
        ],
        verbose_name="فایل PDF کارنامه",
    )

    is_active = models.BooleanField(
        default=True,
        verbose_name="فعال",
    )

    class Meta:
        verbose_name = "کارنامه دانش‌آموز"
        verbose_name_plural = "کارنامه‌های دانش‌آموز"

        ordering = (
            "-created_at",
        )

    def __str__(self):
        return f"{self.student} - {self.title}"