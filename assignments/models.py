from django.db import models

from core.models import BaseModel


class Assignment(BaseModel):

    teacher = models.ForeignKey(
        "accounts.TeacherProfile",
        on_delete=models.CASCADE,
        related_name="assignments",
        verbose_name="معلم",
    )

    classroom = models.ForeignKey(
        "academic.Classroom",
        on_delete=models.CASCADE,
        related_name="assignments",
        verbose_name="کلاس",
    )

    title = models.CharField(
        max_length=200,
        verbose_name="عنوان تکلیف",
    )

    description = models.TextField(
        blank=True,
        null=True,
        verbose_name="توضیحات",
    )

    file = models.FileField(
        upload_to="assignments/",
        blank=True,
        null=True,
        verbose_name="فایل تکلیف",
    )


    class Meta:
        verbose_name = "تکلیف"
        verbose_name_plural = "تکالیف"


    def __str__(self):
        return self.title

class AssignmentSubmission(BaseModel):

    assignment = models.ForeignKey(
        Assignment,
        on_delete=models.CASCADE,
        related_name="submissions",
        verbose_name="تکلیف",
    )

    student = models.ForeignKey(
        "accounts.StudentProfile",
        on_delete=models.CASCADE,
        related_name="assignment_submissions",
        verbose_name="دانش‌آموز",
    )

    answer_text = models.TextField(
        blank=True,
        null=True,
        verbose_name="متن پاسخ",
    )

    file = models.FileField(
        upload_to="assignment_submissions/",
        blank=True,
        null=True,
        verbose_name="فایل پاسخ",
    )

    EVALUATION_CHOICES = (
        ("excellent", "خیلی خوب"),
        ("good", "خوب"),
        ("acceptable", "قابل قبول"),
        ("needs_effort", "نیاز به تلاش"),
    )

    evaluation = models.CharField(
        max_length=20,
        choices=EVALUATION_CHOICES,
        blank=True,
        null=True,
        verbose_name="ارزیابی توصیفی",
    )

    teacher_feedback = models.TextField(
        blank=True,
        null=True,
        verbose_name="بازخورد معلم",
    )


    class Meta:
        verbose_name = "پاسخ تکلیف"
        verbose_name_plural = "پاسخ‌های تکلیف"

        constraints = [
            models.UniqueConstraint(
                fields=[
                    "assignment",
                    "student",
                ],
                name="unique_assignment_student_submission",
            )
        ]


    def __str__(self):
        return f"{self.student} - {self.assignment}"