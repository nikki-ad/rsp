from django.db import models

from core.models import BaseModel


class LanguageGroup(BaseModel):
    title = models.CharField(max_length=120, verbose_name="عنوان گروه زبان")
    academic_year = models.ForeignKey(
        "academic.AcademicYear", on_delete=models.CASCADE,
        related_name="language_groups", verbose_name="سال تحصیلی",
    )
    teachers = models.ManyToManyField(
        "accounts.TeacherProfile", related_name="language_groups",
        verbose_name="معلمان زبان",
    )
    students = models.ManyToManyField(
        "accounts.StudentProfile", related_name="language_groups",
        verbose_name="دانش‌آموزان",
    )
    is_active = models.BooleanField(default=True, verbose_name="فعال")

    class Meta:
        ordering = ("-academic_year__title", "title")
        constraints = [models.UniqueConstraint(
            fields=("academic_year", "title"), name="unique_language_group_per_year"
        )]
        verbose_name = "گروه زبان"
        verbose_name_plural = "گروه‌های زبان"

    def __str__(self):
        return f"{self.title} - {self.academic_year}"


class LanguageMaterial(BaseModel):
    TYPE_CHOICES = (("text", "متن"), ("file", "فایل"), ("link", "لینک"))
    group = models.ForeignKey(LanguageGroup, on_delete=models.CASCADE,
                              related_name="materials", verbose_name="گروه زبان")
    teacher = models.ForeignKey("accounts.TeacherProfile", on_delete=models.CASCADE,
                                related_name="language_materials", verbose_name="معلم زبان")
    title = models.CharField(max_length=200, verbose_name="عنوان")
    content_type = models.CharField(max_length=20, choices=TYPE_CHOICES,
                                    default="text", verbose_name="نوع محتوا")
    content = models.TextField(blank=True, verbose_name="متن مطلب")
    file = models.FileField(upload_to="language_materials/", blank=True, null=True,
                            verbose_name="فایل")
    link = models.URLField(blank=True, verbose_name="لینک")

    class Meta:
        ordering = ("-created_at",)
        verbose_name = "مطلب واحد زبان"
        verbose_name_plural = "مطالب واحد زبان"

    def __str__(self):
        return self.title


class LanguageAssignment(BaseModel):
    group = models.ForeignKey(LanguageGroup, on_delete=models.CASCADE,
                              related_name="assignments", verbose_name="گروه زبان")
    teacher = models.ForeignKey("accounts.TeacherProfile", on_delete=models.CASCADE,
                                related_name="language_assignments", verbose_name="معلم زبان")
    title = models.CharField(max_length=200, verbose_name="عنوان تکلیف")
    description = models.TextField(blank=True, verbose_name="توضیحات")
    file = models.FileField(upload_to="language_assignments/", blank=True, null=True,
                            verbose_name="فایل تکلیف")

    class Meta:
        ordering = ("-created_at",)
        verbose_name = "تکلیف واحد زبان"
        verbose_name_plural = "تکالیف واحد زبان"

    def __str__(self):
        return self.title


class LanguageAssignmentSubmission(BaseModel):
    assignment = models.ForeignKey(LanguageAssignment, on_delete=models.CASCADE,
                                   related_name="submissions", verbose_name="تکلیف")
    student = models.ForeignKey("accounts.StudentProfile", on_delete=models.CASCADE,
                                related_name="language_submissions", verbose_name="دانش‌آموز")
    answer_text = models.TextField(blank=True, verbose_name="متن پاسخ")
    file = models.FileField(upload_to="language_submissions/", blank=True, null=True,
                            verbose_name="فایل پاسخ")

    class Meta:
        constraints = [models.UniqueConstraint(
            fields=("assignment", "student"), name="unique_language_assignment_submission"
        )]
        verbose_name = "پاسخ تکلیف زبان"
        verbose_name_plural = "پاسخ‌های تکلیف زبان"

    def __str__(self):
        return f"{self.student} - {self.assignment}"
