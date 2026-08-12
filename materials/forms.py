from django import forms
from .models import EducationalMaterial
from academic.models import Classroom

class EducationalMaterialCreateForm(forms.ModelForm):

    def __init__(self, *args, teacher=None, **kwargs):
        super().__init__(*args, **kwargs)

        if teacher is not None:
            self.fields["classrooms"].queryset = Classroom.objects.filter(
                teacher_assignments__teacher=teacher,
            ).distinct()

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