from functools import wraps

import jdatetime
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_http_methods

from activitylog.utils import log_activity
from core.jalali import jalali_format
from materials.forms import assigned_active_classrooms
from notifications.services import create_notification
from .homework_forms import HomeworkDeficiencyForm
from .homework_models import HomeworkDeficiency


def regular_teacher_required(view):
    @login_required
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        teacher = getattr(request.user, "teacher_profile", None)
        if request.user.role != "teacher" or teacher is None or teacher.is_language_teacher:
            return HttpResponseForbidden("این بخش مخصوص معلمان کلاس‌های مدرسه است.")
        return view(request, *args, **kwargs)
    return wrapped


@regular_teacher_required
@require_GET
def deficiency_classrooms(request):
    return render(request, "assignments/deficiency_classrooms.html", {
        "classrooms": assigned_active_classrooms(request.user.teacher_profile),
    })


@regular_teacher_required
@require_http_methods(["GET", "POST"])
def deficiency_create(request, classroom_id):
    teacher = request.user.teacher_profile
    classroom = get_object_or_404(assigned_active_classrooms(teacher), pk=classroom_id)
    form = HomeworkDeficiencyForm(
        request.POST if request.method == "POST" else None, classroom=classroom,
        initial={"record_date": timezone.localdate()},
    )
    if request.method == "POST" and form.is_valid():
        count = 0
        with transaction.atomic():
            for student in form.cleaned_data["students"]:
                record, created = HomeworkDeficiency.objects.get_or_create(
                    teacher=teacher, classroom=classroom, student=student,
                    record_date=form.cleaned_data["record_date"], subject=form.cleaned_data["subject"],
                    defaults={"created_by": request.user},
                )
                if created:
                    create_notification(
                        recipient=student.user, title="ثبت نقص تکلیف",
                        message=f"در تاریخ {jalali_format(record.record_date)} برای شما توسط معلم {teacher} در درس {record.subject} یک نقص تکلیف ثبت شده است.",
                        url=reverse("student_deficiency_list"),
                    )
                    count += 1
            if count:
                log_activity(request, action="homework_deficiency_created",
                             description=f"ثبت نقص تکلیف درس {form.cleaned_data['subject']} برای {count} دانش‌آموز کلاس {classroom}")
        if count:
            messages.success(request, f"نقص تکلیف برای {count} دانش‌آموز ثبت شد و اعلان ارسال شد.")
        else:
            messages.info(request, "این نقص تکلیف قبلاً برای دانش‌آموزان انتخاب‌شده ثبت شده است.")
        return redirect("teacher_deficiency_create", classroom_id=classroom.pk)
    return render(request, "assignments/deficiency_form.html", {"form": form, "classroom": classroom})


@login_required
@require_GET
def student_deficiency_list(request):
    student = getattr(request.user, "student_profile", None)
    if request.user.role != "student" or student is None:
        return HttpResponseForbidden("این بخش مخصوص دانش‌آموزان است.")
    records = HomeworkDeficiency.objects.filter(student=student).select_related("teacher__user")
    return render(request, "assignments/deficiency_list.html", {
        "page_obj": Paginator(records, 30).get_page(request.GET.get("page")),
    })


@regular_teacher_required
@require_GET
def deficiency_calendar(request):
    today = jdatetime.date.fromgregorian(date=timezone.localdate())
    try:
        year = int(request.GET.get("year", today.year))
        month = int(request.GET.get("month", today.month))
        if not 1200 <= year <= 1600 or not 1 <= month <= 12:
            raise ValueError
        first = jdatetime.date(year, month, 1)
    except (TypeError, ValueError, OverflowError):
        return JsonResponse({"error": "تاریخ معتبر نیست."}, status=400)
    days = 31 if month <= 6 else 30 if month <= 11 or first.isleap() else 29
    return JsonResponse({
        "year": year, "month": month, "days": days,
        "offset": (first.togregorian().weekday() + 2) % 7,
        "today": today.strftime("%Y/%m/%d"),
    })
