from django.conf import settings
from django.db import models

from core.models import BaseModel


class ActivityLog(BaseModel):

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="activity_logs",
        verbose_name="کاربر",
    )

    action = models.CharField(
        max_length=100,
        verbose_name="عملیات",
    )

    description = models.TextField(
        blank=True,
        verbose_name="توضیحات",
    )

    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        verbose_name="آدرس IP",
    )

    class Meta:
        verbose_name = "گزارش فعالیت"
        verbose_name_plural = "گزارش فعالیت‌ها"
        ordering = (
            "-created_at",
        )

    def __str__(self):
        if self.user:
            return f"{self.user} - {self.action}"

        return self.action