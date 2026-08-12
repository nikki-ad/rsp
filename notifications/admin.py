from django.contrib import admin

from core.admin import BaseAdmin
from .models import Notification


@admin.register(Notification)
class NotificationAdmin(BaseAdmin):

    list_display = (
        "recipient",
        "notification_type",
        "title",
        "is_read",
        "created_at",
    )

    list_filter = (
        "notification_type",
        "is_read",
        "created_at",
    )

    search_fields = (
        "recipient__username",
        "recipient__first_name",
        "recipient__last_name",
        "title",
        "message",
    )