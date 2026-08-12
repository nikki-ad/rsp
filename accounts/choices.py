from django.db import models


class Role(models.TextChoices):
    SUPER_ADMIN = "super_admin", "سوپر ادمین"
    SCHOOL_MANAGER = "school_manager", "مدیر مدرسه"
    TEACHER = "teacher", "معلم"
    STUDENT = "student", "دانش‌آموز"
    FINANCE = "finance", "امور مالی"
    OPERATOR = "operator", "اپراتور"