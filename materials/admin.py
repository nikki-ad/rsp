from django.contrib import admin
from .models import EducationalMaterial
from core.admin import BaseAdmin


@admin.register(EducationalMaterial)
class EducationalMaterialAdmin(BaseAdmin):

    list_display = (
        "title",
        "teacher",
        "created_at",
    )

    search_fields = (
        "title",
        "teacher__user__first_name",
        "teacher__user__last_name",
    )

    filter_horizontal = (
        "classrooms",
    )