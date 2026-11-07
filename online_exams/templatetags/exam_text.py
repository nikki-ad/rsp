from django import template
from online_exams.formatting import render_text

register = template.Library()
register.filter("exam_text", render_text)
