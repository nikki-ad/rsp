from django.db import models

from core.models import BaseModel



class BBBConfiguration(BaseModel):

    name = models.CharField(
        max_length=100,
        verbose_name="نام سرویس",
    )

    api_url = models.URLField(
        verbose_name="آدرس API بیگ‌بلو‌باتن",
    )

    secret = models.CharField(
        max_length=255,
        verbose_name="کلید محرمانه API",
    )

    is_active = models.BooleanField(
        default=True,
        verbose_name="فعال",
    )

    class Meta:
        verbose_name = "تنظیمات BigBlueButton"
        verbose_name_plural = "تنظیمات BigBlueButton"

    def __str__(self):
        return self.name


class OnlineClass(BaseModel):

    PROVIDER_CHOICES = (
        ("bbb", "BigBlueButton"),
        ("skyroom", "Skyroom"),
    )

    title = models.CharField(
        max_length=200,
        verbose_name="عنوان کلاس آنلاین",
    )

    academic_year = models.ForeignKey(
        "academic.AcademicYear",
        on_delete=models.PROTECT,
        related_name="online_classes",
        verbose_name="سال تحصیلی",
    )

    bbb_configuration = models.ForeignKey(
        BBBConfiguration,
        on_delete=models.PROTECT,
        related_name="online_classes",
        blank=True,
        null=True,
        verbose_name="سرویس BigBlueButton",
    )

    provider = models.CharField(
        max_length=20,
        choices=PROVIDER_CHOICES,
        default="bbb",
        verbose_name="پلتفرم فعال",
    )

    bbb_room_id = models.CharField(
        max_length=200,
        blank=True,
        null=True,
        verbose_name="شناسه اتاق BBB",
    )

    skyroom_url = models.URLField(
        blank=True,
        null=True,
        verbose_name="لینک جایگزین Skyroom",
    )

    students = models.ManyToManyField(
        "accounts.StudentProfile",
        related_name="online_classes",
        blank=True,
        verbose_name="دانش‌آموزان",
    )

    teachers = models.ManyToManyField(
        "accounts.TeacherProfile",
        related_name="online_classes",
        blank=True,
        verbose_name="معلم‌ها",
    )

    is_active = models.BooleanField(
        default=True,
        verbose_name="فعال",
    )

    class Meta:
        verbose_name = "کلاس آنلاین"
        verbose_name_plural = "کلاس‌های آنلاین"
        ordering = (
            "title",
        )

    def __str__(self):
        return self.title

class BBBAttendanceEvent(models.Model):
    """Immutable, deduplicated BBB events; never inferred from a page refresh."""
    online_class = models.ForeignKey(OnlineClass, on_delete=models.CASCADE, related_name="attendance_events")
    configuration = models.ForeignKey(BBBConfiguration, on_delete=models.PROTECT)
    session_id = models.CharField(max_length=256)
    participant_id = models.CharField(max_length=256, blank=True)
    external_user_id = models.CharField(max_length=256, blank=True)
    full_name = models.CharField(max_length=200, blank=True)
    role = models.CharField(max_length=20, blank=True)
    event_type = models.CharField(max_length=30)
    occurred_at = models.DateTimeField()
    received_at = models.DateTimeField(auto_now_add=True)
    fingerprint = models.CharField(max_length=64, unique=True)

    class Meta:
        ordering = ["occurred_at", "id"]
        indexes = [models.Index(fields=["online_class", "configuration", "session_id"], name="bbb_attendance_session")]


class BBBAttendanceHook(models.Model):
    online_class = models.OneToOneField(OnlineClass, on_delete=models.CASCADE, related_name="attendance_hook")
    configuration = models.ForeignKey(BBBConfiguration, on_delete=models.CASCADE)
    callback_url = models.URLField(max_length=500)
    registered_at = models.DateTimeField(null=True, blank=True)
    last_attempt_at = models.DateTimeField(null=True, blank=True)
    last_received_at = models.DateTimeField(null=True, blank=True)
