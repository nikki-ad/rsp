from datetime import datetime

from django import forms

from academic.models import StudentDailyRoutine


class StudentDailyRoutineForm(forms.ModelForm):
    class Meta:
        model = StudentDailyRoutine
        fields = (
            "study_start",
            "study_end",
            "homework_start",
            "homework_end",
            "sleep_time",
        )
        widgets = {
            field: forms.TimeInput(attrs={"type": "time"}, format="%H:%M")
            for field in fields
        }

    def clean(self):
        cleaned_data = super().clean()
        intervals = (
            ("study_start", "study_end", "بازه مطالعه"),
            ("homework_start", "homework_end", "بازه انجام تکالیف"),
        )
        for start_name, end_name, label in intervals:
            start = cleaned_data.get(start_name)
            end = cleaned_data.get(end_name)
            if start and end:
                start_value = datetime.combine(datetime.min.date(), start)
                end_value = datetime.combine(datetime.min.date(), end)
                if end_value <= start_value:
                    self.add_error(end_name, f"زمان پایان {label} باید بعد از زمان شروع باشد.")
        return cleaned_data
