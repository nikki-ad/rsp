from django import template
from assignments.homework_report_forms import HomeworkDeficiencyReportForm
from assignments.homework_report_views import deficiency_report_allowed

register = template.Library()


@register.inclusion_tag("assignments/deficiency_report_dialog.html", takes_context=True)
def homework_report_dialog(context):
    request = context.get("request")
    return {"allowed": bool(request and deficiency_report_allowed(request.user)),
            "form": HomeworkDeficiencyReportForm()}
