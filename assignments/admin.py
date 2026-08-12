from django.contrib import admin

from .models import Assignment
from core.admin import BaseAdmin


@admin.register(Assignment)
class AssignmentAdmin(BaseAdmin):

    list_display = (
        "title",
        "teacher",
        "classroom",
        "created_at",
    )

    list_filter = (
        "classroom",
    )

    search_fields = (
        "title",
        "teacher__user__first_name",
        "teacher__user__last_name",
        "classroom__name",
    )