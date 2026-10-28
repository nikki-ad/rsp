import jdatetime
from django import forms
from django.utils import timezone
from core.jalali import JalaliDateField


class HomeworkDeficiencyReportForm(forms.Form):
    start_date = JalaliDateField(label="از تاریخ")
    end_date = JalaliDateField(label="تا تاریخ")

    def __init__(self, *args, **kwargs):
        today = timezone.localdate()
        jalali_today = jdatetime.date.fromgregorian(date=today)
        kwargs.setdefault("initial", {
            "start_date": jalali_today.replace(day=1).togregorian(),
            "end_date": today,
        })
        super().__init__(*args, **kwargs)

    def clean(self):
        data = super().clean()
        start, end = data.get("start_date"), data.get("end_date")
        if start and end and start > end:
            self.add_error("end_date", "تاریخ پایان نباید قبل از تاریخ شروع باشد.")
        return data
