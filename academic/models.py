from django.db import models
from accounts.models import *
from django.core.exceptions import ValidationError
from core.models import BaseModel


class AcademicYear(BaseModel):
    """
    Academic year model.

    Example:
        1405-1406
    """

    class Status(models.TextChoices):
        DRAFT = "draft", "پیش‌نویس"
        ACTIVE = "active", "فعال"
        ARCHIVED = "archived", "آرشیو"

    title = models.CharField(
        max_length=20,
        unique=True,
        verbose_name="سال تحصیلی"
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
        verbose_name="وضعیت"
    )

    description = models.TextField(
        blank=True,
        verbose_name="توضیحات"
    )

    start_date = models.DateField(
        null=True,
        blank=True,
        verbose_name="تاریخ شروع"
    )

    end_date = models.DateField(
        null=True,
        blank=True,
        verbose_name="تاریخ پایان"
    )
    
    class Meta:
        verbose_name = "سال تحصیلی"
        verbose_name_plural = "سالهای تحصیلی"
        ordering = ["-title"]

        constraints = [
            models.UniqueConstraint(
                fields=["status"],
                condition=models.Q(status="active"),
                name="unique_active_academic_year",
            ),
        ]

        

    def __str__(self) -> str:
            return self.title
    


    

class Grade(BaseModel):
    """
    School grades.

    Example:
        اول
        دوم
        سوم
    """

    code = models.CharField(
        max_length=10,
        unique=True,
        verbose_name="کد پایه"
    )

    title = models.CharField(
        max_length=50,
        unique=True,
        verbose_name="نام پایه"
    )

    order = models.PositiveSmallIntegerField(
        unique=True,
        verbose_name="ترتیب نمایش"
    )

    description = models.TextField(
        blank=True,
        verbose_name="توضیحات"
    )

    class Meta:
        verbose_name = "پایه تحصیلی"
        verbose_name_plural = "پایه‌های تحصیلی"
        ordering = ["order"]

    def __str__(self) -> str:
        return self.title


class Classroom(BaseModel):
    """
    Classroom model.

    Example:
        یاس 1
        یاس 2
    """

    academic_year = models.ForeignKey(
        AcademicYear,
        on_delete=models.PROTECT,
        related_name="classrooms",
        verbose_name="سال تحصیلی",
    )

    grade = models.ForeignKey(
        Grade,
        on_delete=models.PROTECT,
        related_name="classrooms",
        verbose_name="پایه تحصیلی",
    )

    name = models.CharField(
        max_length=50,
        verbose_name="نام کلاس",
    )

    capacity = models.PositiveSmallIntegerField(
        verbose_name="ظرفیت",
    )

    description = models.TextField(
        blank=True,
        verbose_name="توضیحات",
    )

    class Meta:
        verbose_name = "کلاس"
        verbose_name_plural = "کلاس‌ها"
        ordering = ["-academic_year__title", "grade__order", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["academic_year", "name"],
                name="unique_classroom_per_academic_year_name",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.grade.title} {self.name}"



class Enrollment(BaseModel):

    student = models.ForeignKey(
        StudentProfile,
        on_delete=models.CASCADE,
        related_name="enrollments",
        verbose_name="دانش‌آموز",
    )

    academic_year = models.ForeignKey(
        AcademicYear,
        on_delete=models.CASCADE,
        related_name="enrollments",
        verbose_name="سال تحصیلی",
    )

    classroom = models.ForeignKey(
        Classroom,
        on_delete=models.CASCADE,
        related_name="enrollments",
        verbose_name="کلاس",
    )

    roll_number = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="شماره لیست",
    )

    is_active = models.BooleanField(
        default=True,
        verbose_name="فعال",
    )

    def clean(self):
        super().clean()

        if (
            self.classroom_id
            and self.academic_year_id
            and self.classroom.academic_year_id != self.academic_year_id
        ):

            raise ValidationError(
                {
                    "classroom": (
                        "کلاس انتخاب‌شده متعلق به "
                        "سال تحصیلی انتخاب‌شده نیست."
                    )
                }
            )
    class Meta:
        verbose_name = "ثبت‌نام"
        verbose_name_plural = "ثبت‌نام‌ها"

        constraints = [
            models.UniqueConstraint(
                fields=["student", "academic_year"],
                condition=models.Q(is_active=True),
                name="unique_active_student_per_academic_year",
    )
]

    def __str__(self):
        return f"{self.student} | {self.academic_year} | {self.classroom}"


class TeacherClassAssignment(BaseModel):

    teacher = models.ForeignKey(
        "accounts.TeacherProfile",
        on_delete=models.CASCADE,
        related_name="class_assignments",
        verbose_name="معلم",
    )

    classroom = models.ForeignKey(
        Classroom,
        on_delete=models.CASCADE,
        related_name="teacher_assignments",
        verbose_name="کلاس",
    )

    class Meta:
        verbose_name = "تخصیص معلم به کلاس"
        verbose_name_plural = "تخصیص معلمان به کلاس‌ها"

        constraints = [
            models.UniqueConstraint(
                fields=[
                    "teacher",
                    "classroom",
                ],
                name="unique_teacher_classroom",
            )
        ]

    def __str__(self):
        return f"{self.teacher} - {self.classroom}"