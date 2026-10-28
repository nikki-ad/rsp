from django import forms

from accounts.models import StudentProfile
from core.jalali import JalaliDateField


class HomeworkDeficiencyForm(forms.Form):
    record_date = JalaliDateField(label="تاریخ نقص تکلیف")
    subject = forms.CharField(label="نام درس", max_length=150,
                              widget=forms.TextInput(attrs={"placeholder": "مثلاً ریاضی"}))
    students = forms.ModelMultipleChoiceField(
        label="دانش‌آموزان", queryset=StudentProfile.objects.none(),
        widget=forms.CheckboxSelectMultiple,
        error_messages={"required": "حداقل یک دانش‌آموز را انتخاب کنید.",
                        "invalid_choice": "دانش‌آموز انتخاب‌شده عضو فعال این کلاس نیست."},
    )

    def __init__(self, *args, classroom, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["students"].queryset = StudentProfile.objects.filter(
            enrollments__classroom=classroom, enrollments__is_active=True,
            user__is_active=True,
        ).select_related("user").distinct().order_by("user__last_name", "user__first_name", "pk")
