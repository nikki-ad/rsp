from functools import wraps
from itertools import groupby

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, HttpResponseForbidden, JsonResponse
from django.shortcuts import render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from accounts.choices import Role
from accounts.permissions import is_school_admin
from core.jalali import jalali_format
from dashboard.deficiency_xlsx import build_deficiency_report_xlsx
from .homework_models import HomeworkDeficiency
from .homework_report_forms import HomeworkDeficiencyReportForm


def deficiency_report_allowed(user):
    return user.is_authenticated and (is_school_admin(user) or user.role == Role.OPERATOR)


def report_manager_required(view):
    @login_required
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if not deficiency_report_allowed(request.user):
            return HttpResponseForbidden("شما اجازه دریافت گزارش نقص تکلیف را ندارید.")
        return view(request, *args, **kwargs)
    return wrapped


@report_manager_required
@never_cache
@require_GET
def deficiency_report_filter(request):
    return render(request, "assignments/deficiency_report_page.html", {"form": HomeworkDeficiencyReportForm()})


@report_manager_required
@never_cache
@require_GET
def deficiency_report_download(request):
    form = HomeworkDeficiencyReportForm(request.GET)
    if not form.is_valid():
        if request.headers.get("Accept") == "application/json":
            return JsonResponse({"errors": form.errors.get_json_data()}, status=400)
        return render(request, "assignments/deficiency_report_page.html", {"form": form}, status=400)
    start, end = form.cleaned_data["start_date"], form.cleaned_data["end_date"]
    records = HomeworkDeficiency.objects.filter(record_date__range=(start, end)).select_related(
        "student__user", "teacher__user", "classroom__grade", "classroom__academic_year",
    ).order_by("classroom__academic_year__title", "classroom__grade__order", "classroom__name",
               "classroom_id", "-record_date", "student__user__last_name", "student__user__first_name", "pk")

    def sheets():
        found = False
        for _, group in groupby(records.iterator(chunk_size=1000), key=lambda r: r.classroom_id):
            group = iter(group)
            first = next(group)
            classroom = first.classroom
            found = True
            def rows(first=first, group=group):
                yield [str(first.student), first.subject, jalali_format(first.record_date), str(first.teacher)]
                for record in group:
                    yield [str(record.student), record.subject, jalali_format(record.record_date), str(record.teacher)]
            yield f"{classroom} - {classroom.academic_year.title}", rows()
        if not found:
            yield "بدون نقص تکلیف", [["در بازه انتخاب‌شده نقص تکلیفی ثبت نشده است.", "", "", ""]]

    response = HttpResponse(build_deficiency_report_xlsx(sheets()), content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    response["Content-Disposition"] = f'attachment; filename="homework-deficiencies-{start.isoformat()}-to-{end.isoformat()}.xlsx"'
    response["X-Content-Type-Options"] = "nosniff"
    return response


@report_manager_required
@never_cache
@require_GET
def deficiency_report_calendar(request):
    from core.jalali_calendar import calendar_response
    return calendar_response(request)
