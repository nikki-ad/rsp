from django.contrib import admin

from core.admin import BaseAdmin
from .models import Notification , Announcement
from django import forms
from academic.models import Classroom
from activitylog.utils import log_activity



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


class ClassroomChoiceField(forms.ModelChoiceField):

    def label_from_instance(self, obj):
        return (
            f"{obj.academic_year.title} | "
            f"{obj.grade.title} | "
            f"{obj.name}"
        )


class AnnouncementAdminForm(forms.ModelForm):

    classroom = ClassroomChoiceField(
        queryset=Classroom.objects.select_related(
            "academic_year",
            "grade",
        ).all(),
        required=False,
        label="کلاس مخاطب",
    )

    class Meta:
        model = Announcement
        fields = "__all__"




@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin):
    
    form = AnnouncementAdminForm

    list_display = (
        "title",
        "audience",
        "publish_at",
        "is_active",
    )

    list_filter = (
        "audience",
        "is_active",
    )

    search_fields = (
        "title",
        "message",
    )

    ordering = (
        "-publish_at",
    )

    def save_model(self, request, obj, form, change):

        super().save_model(
            request,
            obj,
            form,
            change,
        )

        if change:
            action = "announcement_updated"
            description = f"اطلاعیه «{obj.title}» ویرایش شد."
        else:
            action = "announcement_created"
            description = f"اطلاعیه «{obj.title}» ایجاد شد."

        log_activity(
            request,
            action=action,
            description=description,
        )

    def delete_model(self, request, obj):

        title = obj.title

        super().delete_model(
            request,
            obj,
        )

        log_activity(
            request,
            action="announcement_deleted",
            description=f"اطلاعیه «{title}» حذف شد.",
        )


    def delete_queryset(self, request, queryset):

        titles = list(
            queryset.values_list(
                "title",
                flat=True,
            )
        )

        super().delete_queryset(
            request,
            queryset,
        )

        for title in titles:

            log_activity(
                request,
                action="announcement_deleted",
                description=f"اطلاعیه «{title}» حذف شد.",
            )