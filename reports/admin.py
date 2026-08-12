from django.contrib import admin

from .models import StudentReportCard


@admin.register(StudentReportCard)
class StudentReportCardAdmin(admin.ModelAdmin):

    list_display = (
        "student",
        "title",
        "is_active",
        "created_at",
    )

    list_filter = (
        "is_active",
    )

    search_fields = (
        "student__user__first_name",
        "student__user__last_name",
        "title",
    )

    ordering = (
        "-created_at",
    )