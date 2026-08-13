from django.contrib import admin

from .models import StudentReportCard
from activitylog.utils import log_activity

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

    def save_model(self, request, obj, form, change):

        super().save_model(
            request,
            obj,
            form,
            change,
        )

        student_name = obj.student.user.get_full_name()

        if change:
            action = "report_card_updated"
            description = (
                f"کارنامه «{obj.title}» "
                f"برای {student_name} ویرایش شد."
            )
        else:
            action = "report_card_created"
            description = (
                f"کارنامه «{obj.title}» "
                f"برای {student_name} ثبت شد."
            )

        log_activity(
            request,
            action=action,
            description=description,
        )

    def delete_model(self, request, obj):

        title = obj.title
        student_name = obj.student.user.get_full_name()

        super().delete_model(
            request,
            obj,
        )

        log_activity(
            request,
            action="report_card_deleted",
            description=(
                f"کارنامه «{title}» "
                f"برای {student_name} حذف شد."
            ),
        )


    def delete_queryset(self, request, queryset):

        report_cards = [
            (
                obj.title,
                obj.student.user.get_full_name(),
            )
            for obj in queryset.select_related(
                "student__user"
            )
        ]

        super().delete_queryset(
            request,
            queryset,
        )

        for title, student_name in report_cards:

            log_activity(
                request,
                action="report_card_deleted",
                description=(
                    f"کارنامه «{title}» "
                    f"برای {student_name} حذف شد."
                ),
            )