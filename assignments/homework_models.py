from django.db import models

from core.models import BaseModel


class HomeworkDeficiency(BaseModel):
    teacher = models.ForeignKey("accounts.TeacherProfile", on_delete=models.PROTECT,
                               related_name="homework_deficiencies", verbose_name="معلم")
    classroom = models.ForeignKey("academic.Classroom", on_delete=models.PROTECT,
                                 related_name="homework_deficiencies", verbose_name="کلاس")
    student = models.ForeignKey("accounts.StudentProfile", on_delete=models.CASCADE,
                               related_name="homework_deficiencies", verbose_name="دانش‌آموز")
    record_date = models.DateField(verbose_name="تاریخ نقص تکلیف")
    subject = models.CharField(max_length=150, verbose_name="نام درس")

    class Meta:
        verbose_name = "نقص تکلیف"
        verbose_name_plural = "نقص‌های تکلیف"
        ordering = ["-record_date", "-created_at", "-pk"]
        constraints = [models.UniqueConstraint(
            fields=["teacher", "classroom", "student", "record_date", "subject"],
            name="unique_homework_deficiency",
        )]

    def __str__(self):
        return f"{self.student} | {self.subject}"
