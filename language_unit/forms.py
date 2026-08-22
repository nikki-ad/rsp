from django import forms

from accounts.models import StudentProfile, TeacherProfile
from academic.models import AcademicYear
from .models import (
    LanguageAssignment, LanguageAssignmentSubmission, LanguageGroup, LanguageMaterial,
)


class LanguageGroupForm(forms.ModelForm):
    class Meta:
        model = LanguageGroup
        fields = ("title", "academic_year", "teachers", "students", "is_active")
        widgets = {
            "teachers": forms.CheckboxSelectMultiple,
            "students": forms.CheckboxSelectMultiple,
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["teachers"].queryset = TeacherProfile.objects.select_related("user").order_by(
            "user__last_name", "user__first_name"
        )
        students = StudentProfile.objects.select_related("user")
        year_id = self.data.get("academic_year") if self.is_bound else self.instance.academic_year_id
        if year_id:
            students = students.filter(
                enrollments__academic_year_id=year_id, enrollments__is_active=True
            ).distinct()
        self.fields["students"].queryset = students.order_by("user__last_name", "user__first_name")


class LanguageMaterialForm(forms.ModelForm):
    class Meta:
        model = LanguageMaterial
        fields = ("title", "content_type", "content", "file", "link")

    def clean(self):
        data = super().clean()
        kind = data.get("content_type")
        if kind == "text" and not (data.get("content") or "").strip():
            self.add_error("content", "متن مطلب را وارد کنید.")
        if kind == "file" and not data.get("file") and not self.instance.file:
            self.add_error("file", "فایل را انتخاب کنید.")
        if kind == "link" and not data.get("link"):
            self.add_error("link", "لینک را وارد کنید.")
        return data


class LanguageAssignmentForm(forms.ModelForm):
    class Meta:
        model = LanguageAssignment
        fields = ("title", "description", "file")


class LanguageSubmissionForm(forms.ModelForm):
    class Meta:
        model = LanguageAssignmentSubmission
        fields = ("answer_text", "file")

    def clean(self):
        data = super().clean()
        if not (data.get("answer_text") or "").strip() and not data.get("file") and not self.instance.file:
            raise forms.ValidationError("حداقل متن پاسخ یا یک فایل ارسال کنید.")
        return data
