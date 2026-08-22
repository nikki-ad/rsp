from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from core.admin import BaseAdmin
from .models import *


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    list_display = (
        "username",
        "first_name",
        "last_name",
        "email",
        "role",
        "is_staff",
        "is_active",
    )

    list_filter = (
        "role",
        "is_staff",
        "is_superuser",
        "is_active",
    )

    search_fields = (
        "username",
        "first_name",
        "last_name",
        "email",
    )

    ordering = ("username",)

    fieldsets = UserAdmin.fieldsets + (
        ("اطلاعات مدرسه", {"fields": ("role", "avatar")}),
    )

    add_fieldsets = UserAdmin.add_fieldsets + (
        ("اطلاعات مدرسه", {"fields": ("role",)}),
    )


@admin.register(StudentProfile)
class StudentProfileAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "national_code",
        "guardian_name",
        "guardian_phone",
        "created_at",
    )

    search_fields = (
        "user__username",
        "user__first_name",
        "user__last_name",
        "national_code",
        "guardian_name",
        "guardian_phone",
    )

    fieldsets = (
    ("اطلاعات کاربر", {
        "fields": ("user",)
    }),

    ("اطلاعات هویتی", {
        "fields": ("national_code", "birth_date")
    }),

    ("اطلاعات ولی", {
        "fields": ("guardian_name", "guardian_phone")
    }),

    ("آدرس", {
        "fields": ("address",)
    }),

    ("اطلاعات سیستمی", {
        "fields": (
            "id",
            "created_by",
            "created_at",
            "updated_at",
        )
    }),
)

    readonly_fields = (
    "id",
    "created_at",
    "updated_at",
)
    search_fields = (
    "user__username",
    "user__first_name",
    "user__last_name",
)



@admin.register(TeacherProfile)
class TeacherProfileAdmin(BaseAdmin):

    list_display = (
        "user",
        "personnel_code",
        "expertise",
        "created_at",
    )

    search_fields = (
        "user__first_name",
        "user__last_name",
        "personnel_code",
    )

    readonly_fields = (
        "id",
        "created_at",
        "updated_at",
    )