from django.db import models

from core.models import BaseModel
from django.core.validators import FileExtensionValidator

class ReportCardPeriod(BaseModel):
    title = models.CharField(max_length=200, verbose_name="عنوان کارنامه")
    academic_year = models.ForeignKey(
        "academic.AcademicYear", on_delete=models.PROTECT, null=True,
        verbose_name="سال تحصیلی",
    )

    class Meta:
        ordering = ("-created_at",)
        verbose_name = "عنوان کارنامه"
        verbose_name_plural = "عنوان‌های کارنامه"

    def __str__(self):
        return f"{self.title} — {self.academic_year}" if self.academic_year_id else self.title


class StudentReportCard(BaseModel):
    period = models.ForeignKey(
        ReportCardPeriod, on_delete=models.PROTECT, related_name="report_cards",
        verbose_name="عنوان کارنامه",
    )

    student = models.ForeignKey(
        "accounts.StudentProfile",
        on_delete=models.CASCADE,
        related_name="report_cards",
        verbose_name="دانش‌آموز",
    )

    title = models.CharField(
        max_length=200,
        verbose_name="عنوان قدیمی کارنامه", blank=True,
    )

    file = models.FileField(
        upload_to="report_cards/",
        validators=[
            FileExtensionValidator(
                allowed_extensions=["pdf", "jpg", "jpeg", "png", "webp"],
            ),
        ],
        verbose_name="فایل کارنامه (PDF یا عکس)",
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
        return f"{self.student} - {self.period.title}"
