from django import forms
from .models import EducationalMaterial
from academic.models import AcademicYear, Classroom


def assigned_active_classrooms(teacher):
    if teacher is None:
        return Classroom.objects.none()

    return (
        Classroom.objects.filter(
            teacher_assignments__teacher=teacher,
            academic_year__status=AcademicYear.Status.ACTIVE,
        )
        .select_related("grade", "academic_year")
        .distinct()
        .order_by("grade__order", "name")
    )


class EducationalMaterialCreateForm(forms.ModelForm):

    classrooms = forms.ModelMultipleChoiceField(
        queryset=Classroom.objects.none(),
        required=True,
        label="کلاس‌ها",
        widget=forms.CheckboxSelectMultiple,
        help_text="فقط کلاس‌هایی که به شما اختصاص داده شده‌اند قابل انتخاب هستند.",
    )

    def __init__(self, *args, teacher=None, hide_classrooms=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.teacher = teacher
        self.hide_classrooms = hide_classrooms

        classrooms = assigned_active_classrooms(teacher)

        if hide_classrooms:
            self.fields.pop("classrooms", None)
            return

        self.fields["classrooms"].queryset = classrooms
        if not classrooms.exists():
            self.fields["classrooms"].help_text = (
                "شما به هیچ کلاس فعالی اختصاص داده نشده‌اید."
            )

    def clean_classrooms(self):
        classrooms = self.cleaned_data.get("classrooms")
        if not classrooms:
            return classrooms
        allowed = set(
            assigned_active_classrooms(self.teacher).values_list("id", flat=True)
        )
        invalid = [c for c in classrooms if c.id not in allowed]
        if invalid:
            raise forms.ValidationError(
                "فقط می‌توانید برای کلاس‌هایی که عضو آن هستید مطلب ارسال کنید."
            )
        return classrooms

    def clean(self):
        cleaned_data = super().clean()
        content_type = cleaned_data.get("content_type")

        if content_type == "text" and not (cleaned_data.get("content") or "").strip():
            self.add_error("content", "متن مطلب را وارد کنید.")

        if content_type == "file" and not cleaned_data.get("file"):
            self.add_error("file", "فایل مطلب را انتخاب کنید.")

        if content_type == "link" and not cleaned_data.get("link"):
            self.add_error("link", "لینک مطلب را وارد کنید.")

        return cleaned_data

    class Meta:
        model = EducationalMaterial

        fields = [
            "title",
            "content_type",
            "content",
            "file",
            "link",
            "classrooms",
        ]

        labels = {
            "title": "عنوان",
            "content_type": "نوع محتوا",
            "content": "متن مطلب",
            "file": "فایل",
            "link": "لینک",
            "classrooms": "کلاس‌ها",
        }
