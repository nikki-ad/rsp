from django.contrib import admin
from .models import LanguageAssignment, LanguageAssignmentSubmission, LanguageGroup, LanguageMaterial

admin.site.register(LanguageGroup)
admin.site.register(LanguageMaterial)
admin.site.register(LanguageAssignment)
admin.site.register(LanguageAssignmentSubmission)
