from django import forms
from core.uploads import AttachmentFormMixin, validate_video

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
            "students": forms.SelectMultiple(attrs={"hidden": "hidden"}),
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
        else:
            students = students.none()
        self.fields["students"].queryset = students.order_by("user__last_name", "user__first_name")


class LanguageMaterialForm(AttachmentFormMixin, forms.ModelForm):
    class Meta:
        model = LanguageMaterial
        fields = ("title", "content_type", "content", "file", "link")

    def clean(self):
        data = super().clean()
        kind = data.get("content_type")
        if kind == "text" and not (data.get("content") or "").strip():
            self.add_error("content", "متن مطلب را وارد کنید.")
        if kind in {"file", "image", "video"} and not data.get("file"):
            self.add_error("file", "فایل را انتخاب کنید.")
        if kind == "link" and not data.get("link"):
            self.add_error("link", "لینک را وارد کنید.")
        upload = data.get("file")
        if kind == "video" and upload and "file" in self.files:
            try:
                validate_video(upload)
            except forms.ValidationError as error:
                self.add_error("file", error)
        if kind == "image" and upload and "file" in self.files:
            try:
                forms.ImageField().clean(upload)
            except forms.ValidationError as error:
                self.add_error("file", error)
        return data


class LanguageAssignmentForm(AttachmentFormMixin, forms.ModelForm):
    class Meta:
        model = LanguageAssignment
        fields = ("title", "description", "file", "image", "video")


class LanguageSubmissionForm(forms.ModelForm):
    class Meta:
        model = LanguageAssignmentSubmission
        fields = ("answer_text", "file")

    def clean(self):
        data = super().clean()
        if not (data.get("answer_text") or "").strip() and not data.get("file"):
            raise forms.ValidationError("حداقل متن پاسخ یا یک فایل ارسال کنید.")
        return data
