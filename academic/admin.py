from django.contrib import admin
from django import forms
from core.admin import BaseAdmin

from .models import *


@admin.register(AcademicYear)
class AcademicYearAdmin(BaseAdmin):
    list_display = ("title", "status", "start_date", "end_date", "created_at")
    list_filter = ("status",)
    search_fields = ("title",)
    ordering = ("-title",)
    fieldsets = (
        ("اطلاعات اصلی", {"fields": ("title", "status", "description")}),
        ("بازه زمانی", {"fields": ("start_date", "end_date")}),
        ("اطلاعات سیستمی", {"fields": ("created_by", "created_at", "updated_at")}),
    )


@admin.register(Grade)
class GradeAdmin(BaseAdmin):
    list_display = ("order", "title", "code", "created_at")
    search_fields = ("title", "code")
    ordering = ("order",)
    fieldsets = (
        ("اطلاعات پایه", {"fields": ("code", "title", "order", "description")}),
        ("اطلاعات سیستمی", {"fields": ("created_by", "created_at", "updated_at")}),
    )


class ClassroomScheduleInline(admin.TabularInline):
    model = ClassroomSchedule
    extra = 0
    fields = ("day", "period", "subject")
    verbose_name = "زنگ برنامه هفتگی"
    verbose_name_plural = "برنامه هفتگی (اختیاری، شنبه تا چهارشنبه / ۵ زنگ)"


@admin.register(Classroom)
class ClassroomAdmin(BaseAdmin):
    list_display = ("name", "grade", "academic_year", "capacity", "student_count", "remaining_capacity", "created_at")
    list_filter = ("academic_year", "grade")
    search_fields = ("name", "grade__title", "academic_year__title")
    ordering = ("-academic_year__title", "grade__order", "name")
    inlines = (ClassroomScheduleInline,)
    fieldsets = (
        ("اطلاعات اصلی", {"fields": ("academic_year", "grade", "name", "capacity", "description")}),
        ("اطلاعات سیستمی", {"fields": ("created_by", "created_at", "updated_at")}),
    )

    @admin.display(description="تعداد دانش‌آموز")
    def student_count(self, obj):
        return obj.enrollments.filter(is_active=True).count()

    @admin.display(description="ظرفیت باقی‌مانده")
    def remaining_capacity(self, obj):
        return obj.capacity - obj.enrollments.filter(is_active=True).count()


@admin.register(ClassroomSchedule)
class ClassroomScheduleAdmin(admin.ModelAdmin):
    list_display = ("classroom", "day", "period", "subject")
    list_filter = ("day", "classroom__academic_year", "classroom")
    search_fields = ("subject", "classroom__name", "classroom__grade__title")
    ordering = ("classroom", "day", "period")


class EnrollmentAdminForm(forms.ModelForm):
    override_capacity = forms.BooleanField(required=False, label="تأیید ثبت‌نام بیش از ظرفیت", help_text="فقط در شرایط استثنایی این گزینه را فعال کنید.")

    class Meta:
        model = Enrollment
        fields = "__all__"

    def clean(self):
        cleaned_data = super().clean()
        classroom = cleaned_data.get("classroom")
        is_active = cleaned_data.get("is_active")
        override_capacity = cleaned_data.get("override_capacity")

        if classroom and is_active:
            active_enrollments = classroom.enrollments.filter(is_active=True)
            if self.instance.pk:
                active_enrollments = active_enrollments.exclude(pk=self.instance.pk)
            if active_enrollments.count() >= classroom.capacity and not override_capacity:
                raise forms.ValidationError("ظرفیت این کلاس تکمیل شده است. برای ثبت‌نام استثنایی، گزینه تأیید ثبت‌نام بیش از ظرفیت را فعال کنید.")

        existing = Enrollment.objects.filter(
            student=cleaned_data.get("student"),
            academic_year=cleaned_data.get("academic_year"),
            is_active=True,
        )
        if self.instance.pk:
            existing = existing.exclude(pk=self.instance.pk)
        if existing.exists():
            raise forms.ValidationError("این دانش‌آموز در حال حاضر در این سال تحصیلی یک ثبت‌نام فعال دارد.")
        return cleaned_data


@admin.register(Enrollment)
class EnrollmentAdmin(BaseAdmin):
    form = EnrollmentAdminForm
    list_display = ("student", "academic_year", "classroom", "roll_number", "is_active")
    list_filter = ("academic_year", "classroom", "is_active")
    search_fields = ("student__user__username", "student__user__first_name", "student__user__last_name")
    ordering = ("-academic_year__start_date", "classroom__grade__order", "classroom__name", "roll_number")
    autocomplete_fields = ("student", "classroom")
    list_select_related = ("student__user", "academic_year", "classroom")
    list_per_page = 50
    list_display_links = ("student",)


@admin.register(TeacherClassAssignment)
class TeacherClassAssignmentAdmin(BaseAdmin):
    list_display = ("teacher", "classroom", "created_at")
    list_filter = ("classroom",)
    search_fields = ("teacher__user__first_name", "teacher__user__last_name", "classroom__name")
