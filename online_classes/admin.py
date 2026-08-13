from django.contrib import admin

from .models import (
    BBBConfiguration,
    OnlineClass,
)
from accounts.models import StudentProfile, TeacherProfile
from django.urls import reverse
from django.utils.html import format_html
from activitylog.utils import log_activity


@admin.register(BBBConfiguration)
class BBBConfigurationAdmin(admin.ModelAdmin):

    list_display = (
        "name",
        "api_url",
        "is_active",
    )

    list_filter = (
        "is_active",
    )

    search_fields = (
        "name",
        "api_url",
    )


@admin.register(OnlineClass)
class OnlineClassAdmin(admin.ModelAdmin):

    list_display = (
        "title",
        "academic_year",
        "provider",
        "is_active",
        "live_attendance_link",
    )

    list_filter = (
        "academic_year",
        "provider",
        "is_active",
    )

    search_fields = (
        "title",
    )

    filter_horizontal = (
        "students",
        "teachers",
    )

    def save_model(self, request, obj, form, change):

        super().save_model(
            request,
            obj,
            form,
            change,
        )

        if change:
            action = "online_class_updated"
            description = (
                f"کلاس آنلاین «{obj.title}» ویرایش شد."
            )
        else:
            action = "online_class_created"
            description = (
                f"کلاس آنلاین «{obj.title}» ایجاد شد."
            )

        log_activity(
            request,
            action=action,
            description=description,
        )

    def formfield_for_manytomany(self, db_field, request, **kwargs):

        academic_year_id = None

        object_id = request.resolver_match.kwargs.get(
            "object_id"
        )

        if object_id:

            online_class = OnlineClass.objects.filter(
                id=object_id,
            ).first()

            if online_class:
                academic_year_id = online_class.academic_year_id

        elif request.method == "POST":

            academic_year_id = request.POST.get(
                "academic_year"
            )


        if db_field.name == "students":

            if academic_year_id:

                kwargs["queryset"] = (
                    StudentProfile.objects.filter(
                        enrollments__academic_year_id=academic_year_id,
                        enrollments__is_active=True,
                    )
                    .distinct()
                )

            else:

                kwargs["queryset"] = StudentProfile.objects.none()


        if db_field.name == "teachers":

            if academic_year_id:

                kwargs["queryset"] = (
                    TeacherProfile.objects.filter(
                        class_assignments__classroom__academic_year_id=academic_year_id,
                    )
                    .distinct()
                )

            else:

                kwargs["queryset"] = TeacherProfile.objects.none()


        return super().formfield_for_manytomany(
            db_field,
            request,
            **kwargs,
        )

    @admin.display(description="حضور زنده")
    def live_attendance_link(self, obj):

        if obj.provider != "bbb":
            return "-"

        url = reverse(
            "live_attendance",
            args=[obj.id],
        )

        return format_html(
            '<a href="{}">مشاهده حضور زنده</a>',
            url,
        )


    def delete_model(self, request, obj):

        title = obj.title

        super().delete_model(
            request,
            obj,
        )

        log_activity(
            request,
            action="online_class_deleted",
            description=f"کلاس آنلاین «{title}» حذف شد.",
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
                action="online_class_deleted",
                description=f"کلاس آنلاین «{title}» حذف شد.",
            )