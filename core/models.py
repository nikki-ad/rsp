import uuid

from django.conf import settings
from django.db import models


class BaseModel(models.Model):

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        verbose_name="شناسه"
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="ایجاد شده در"
    )

    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="بروزرسانی در"
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="%(class)s_created",
        verbose_name="ایجاد کننده"
    )

    class Meta:
        abstract = True