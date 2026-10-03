from django import template
from core.jalali import jalali_format

register = template.Library()


@register.filter
def jalali_date(value):
    return jalali_format(value)


@register.filter
def jalali_datetime(value):
    return jalali_format(value, True)
