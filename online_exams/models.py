from datetime import timedelta
import os
from pathlib import Path

from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from core.models import BaseModel


class PrivateExamStorage(FileSystemStorage):
    @property
    def base_location(self):
        # Evaluate lazily so isolated tests/custom deployments can override it.
        return getattr(settings, "EXAM_PRIVATE_ROOT", Path(settings.BASE_DIR) / "private_exam_files")

    @property
    def location(self):
        return os.path.abspath(self.base_location)

    def url(self, name):
        raise ValueError("Private exam files have no public URL")


def private_storage():
    # Never use MEDIA_ROOT: nginx serves that directory without authentication.
    return PrivateExamStorage()


class Exam(BaseModel):
    title = models.CharField("عنوان آزمون", max_length=200)
    subject = models.CharField("درس", max_length=100)
    mode = models.CharField("روش ورود سؤال", max_length=10,
                            choices=(("pdf", "فایل PDF"), ("typed", "سؤال تایپی")))
    question_pdf = models.FileField("فایل سؤال‌ها", storage=private_storage,
                                   upload_to="questions/%Y/%m/", blank=True)
    question_count = models.PositiveSmallIntegerField("تعداد سؤال‌ها", default=1,
        validators=[MinValueValidator(1), MaxValueValidator(300)])
    duration_minutes = models.PositiveSmallIntegerField("مدت آزمون (دقیقه)", default=20,
        validators=[MinValueValidator(1), MaxValueValidator(1440)])
    opens_at = models.DateTimeField("شروع بازه مجاز")
    closes_at = models.DateTimeField("پایان قطعی آزمون")
    negative_marking = models.BooleanField("نمره منفی (هر سه غلط، یک درست)", default=False)
    show_key_immediately = models.BooleanField("نمایش فوری پاسخ صحیح", default=True)
    published = models.BooleanField(default=False)
    report_files_deleted = models.BooleanField(default=False)
    results_deleted = models.BooleanField(default=False)

    class Meta:
        ordering = ("-created_at",)
        constraints = [models.CheckConstraint(condition=models.Q(closes_at__gt=models.F("opens_at")),
                                               name="exam_valid_window")]

    def __str__(self):
        return self.title

    def deadline(self, started_at):
        return min(started_at + timedelta(minutes=self.duration_minutes), self.closes_at)


class Question(BaseModel):
    exam = models.ForeignKey(Exam, on_delete=models.CASCADE, related_name="questions")
    number = models.PositiveSmallIntegerField()
    text = models.TextField(blank=True, max_length=10000)
    options = models.JSONField(default=list)
    correct_option = models.PositiveSmallIntegerField(null=True, blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(4)])

    class Meta:
        ordering = ("number",)
        constraints = [models.UniqueConstraint(fields=("exam", "number"), name="exam_unique_question"),
            models.CheckConstraint(condition=models.Q(correct_option__isnull=True) |
                models.Q(correct_option__gte=1, correct_option__lte=4), name="exam_valid_key")]


class Participation(BaseModel):
    exam = models.ForeignKey(Exam, on_delete=models.CASCADE, related_name="participations")
    student = models.ForeignKey("accounts.StudentProfile", on_delete=models.PROTECT,
                                related_name="exam_participations")
    classroom_label = models.CharField(max_length=200, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    deadline_at = models.DateTimeField(null=True, blank=True, db_index=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    answers = models.JSONField(default=dict)
    correct = models.PositiveSmallIntegerField(null=True, blank=True)
    wrong = models.PositiveSmallIntegerField(null=True, blank=True)
    blank = models.PositiveSmallIntegerField(null=True, blank=True)
    percentage = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True)
    report = models.FileField(storage=private_storage, upload_to="reports/", blank=True)
    result_deleted = models.BooleanField(default=False)

    class Meta:
        ordering = ("student__user__last_name", "student__user__first_name")
        constraints = [models.UniqueConstraint(fields=("exam", "student"), name="exam_one_participation")]
