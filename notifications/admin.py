from django.contrib import admin

from core.admin import BaseAdmin
from .models import Notification , Announcement
from django import forms
from academic.models import Classroom

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