from datetime import date, datetime
import re

import jdatetime
from django import forms
from django.utils import timezone
from django.forms.utils import from_current_timezone


DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")


def jalali_format(value, with_time=False):
    if not value:
        return ""
    if isinstance(value, datetime):
        if timezone.is_aware(value):
            value = timezone.localtime(value)
        converted = jdatetime.datetime.fromgregorian(datetime=value)
    else:
        converted = jdatetime.date.fromgregorian(date=value)
    return converted.strftime("%Y/%m/%d %H:%M" if with_time else "%Y/%m/%d")


def parse_jalali(value, with_time=False):
    value = str(value).translate(DIGITS).strip()
    pattern = r"(\d{4})[/-](\d{1,2})[/-](\d{1,2})"
    if with_time:
        pattern += r"[ T](\d{1,2}):(\d{2})(?::(\d{2}))?"
    match = re.fullmatch(pattern, value)
    if not match:
        raise ValueError("invalid date")
    parts = [int(part or 0) for part in match.groups()]
    # Preserve compatibility with existing integrations that send ISO Gregorian dates.
    if parts[0] >= 1700:
        return datetime(*parts) if with_time else date(*parts)
    return (jdatetime.datetime(*parts) if with_time else jdatetime.date(*parts)).togregorian()


class JalaliDateInput(forms.TextInput):
    def __init__(self, attrs=None, **kwargs):
        super().__init__({"dir": "ltr", "placeholder": "۱۴۰۵/۰۷/۱۱", "data-jalali": "date", **(attrs or {})})

    def format_value(self, value):
        return jalali_format(value) if isinstance(value, date) else value


class JalaliDateTimeInput(JalaliDateInput):
    def __init__(self, attrs=None, **kwargs):
        super().__init__({"placeholder": "۱۴۰۵/۰۷/۱۱ ۱۸:۳۰", "data-jalali": "datetime", **(attrs or {})})

    def format_value(self, value):
        return jalali_format(value, True) if isinstance(value, date) else value


class JalaliDateField(forms.DateField):
    widget = JalaliDateInput

    def to_python(self, value):
        if value in self.empty_values or isinstance(value, date):
            return super().to_python(value)
        try:
            return parse_jalali(value)
        except (ValueError, OverflowError):
            raise forms.ValidationError("تاریخ شمسی معتبر به شکل ۱۴۰۵/۰۷/۱۱ وارد کنید.", code="invalid")


class JalaliDateTimeField(forms.DateTimeField):
    widget = JalaliDateTimeInput

    def to_python(self, value):
        if value in self.empty_values or isinstance(value, date):
            return super().to_python(value)
        try:
            return from_current_timezone(parse_jalali(value, True))
        except (ValueError, OverflowError):
            raise forms.ValidationError("تاریخ و ساعت شمسی معتبر به شکل ۱۴۰۵/۰۷/۱۱ ۱۸:۳۰ وارد کنید.", code="invalid")
