from django.contrib.auth.decorators import login_required
from django.shortcuts import render
import requests
from .models import OnlineClass
from django.shortcuts import get_object_or_404, redirect
from .services import (
    create_bbb_meeting,
    build_bbb_join_url,
    get_bbb_live_snapshot,
)
from accounts.permissions import is_school_admin
from django.contrib import messages
from academic.models import AcademicYear
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseForbidden
import json
from .attendance import register_attendance_hook, attendance_rows, valid_callback_signature, store_callback
from .models import BBBAttendanceHook




@login_required
def online_class_list(request):

    user = request.user

    online_classes = OnlineClass.objects.none()

    if is_school_admin(user):
        online_classes = OnlineClass.objects.filter(
            is_active=True,
            academic_year__status=AcademicYear.Status.ACTIVE,
        ).select_related("academic_year", "bbb_configuration")

    elif hasattr(user, "student_profile"):

        online_classes = OnlineClass.objects.filter(
            students=user.student_profile,
            is_active=True,
            academic_year__status=AcademicYear.Status.ACTIVE,
        ).select_related(
            "academic_year",
            "bbb_configuration",
        ).distinct()

    elif hasattr(user, "teacher_profile"):

        online_classes = OnlineClass.objects.filter(
            teachers=user.teacher_profile,
            is_active=True,
            academic_year__status=AcademicYear.Status.ACTIVE,
        ).select_related(
            "academic_year",
            "bbb_configuration",
        ).distinct()

    return render(
        request,
        "online_classes/online_class_list.html",
        {
            "online_classes": online_classes,
        },
    )



@login_required
def join_online_class(request, class_id):

    online_class = get_object_or_404(
        OnlineClass,
        id=class_id,
        is_active=True,
        academic_year__status=AcademicYear.Status.ACTIVE,
    )

    user = request.user

    # دانش‌آموز
    if is_school_admin(user):
        role = "moderator"

    elif hasattr(user, "student_profile"):

        if not online_class.students.filter(
            id=user.student_profile.id,
        ).exists():
            return redirect("online_class_list")

        role = "attendee"

    # معلم
    elif hasattr(user, "teacher_profile"):

        if not online_class.teachers.filter(
            id=user.teacher_profile.id,
        ).exists():
            return redirect("online_class_list")

        role = "moderator"

    else:
        return redirect("online_class_list")


    # Skyroom
    if online_class.provider == "skyroom":

        if not online_class.skyroom_url:
            return redirect("online_class_list")

        return redirect(
            online_class.skyroom_url
        )


    # BigBlueButton
    if online_class.provider == "bbb":

        if not online_class.bbb_configuration:
            return redirect("online_class_list")

        # Register before creating the meeting so the first actual join is captured.
        # Hook support is optional at the provider and must not block class entry.
        try:
            register_attendance_hook(online_class)
        except (requests.RequestException, ValueError):
            pass

        try:
            create_bbb_meeting(online_class)
        except (requests.RequestException, ValueError):
            messages.error(request, "اتصال به BBB برقرار نشد. مدیر سامانه تنظیمات سرویس را بررسی کند.")
            return redirect("online_class_list")

        join_url = build_bbb_join_url(
            online_class=online_class,
            user=user,
            role=role,
        )

        return redirect(join_url)


    return redirect("online_class_list")


@login_required
@never_cache
def live_attendance(request, class_id):
    online_class = get_object_or_404(
        OnlineClass.objects.select_related("bbb_configuration"), id=class_id, provider="bbb",
        is_active=True, academic_year__status=AcademicYear.Status.ACTIVE,
    )
    if not is_school_admin(request.user):
        return HttpResponseForbidden("حضور و غیاب فقط در دسترس مدیر سامانه است.")
    error = None
    snapshot = None
    try:
        snapshot = get_bbb_live_snapshot(online_class)
    except (requests.RequestException, ValueError):
        error = "دریافت وضعیت از BBB ناموفق بود؛ وضعیت افراد نامشخص است. دوباره تازه‌سازی کنید."
    captured_at = timezone.now()
    rows = attendance_rows(online_class, snapshot, captured_at) if snapshot else []
    students = [row for row in rows if row["kind"] == "دانش‌آموز"]
    teachers = [row for row in rows if row["kind"] == "معلم"]
    hook = BBBAttendanceHook.objects.filter(online_class=online_class,
        configuration_id=online_class.bbb_configuration_id).first()
    return render(request, "online_classes/live_attendance.html", {
        "online_class": online_class, "attendance_rows": rows, "attendance_error": error,
        "captured_at": captured_at, "meeting_running": bool(snapshot and snapshot["running"]),
        "student_total": len(students), "student_present": sum(row["is_present"] for row in students),
        "student_absent": sum(not row["is_present"] for row in students),
        "teacher_present": sum(row["is_present"] for row in teachers), "hook": hook,
    })


@login_required
@require_POST
def enable_attendance_tracking(request, class_id):
    if not is_school_admin(request.user):
        return HttpResponseForbidden()
    online_class = get_object_or_404(OnlineClass, id=class_id, provider="bbb", is_active=True)
    try:
        register_attendance_hook(online_class, force=True)
    except (requests.RequestException, ValueError):
        messages.error(request, "ثبت زمان‌ها فعال نشد. ارائه‌دهنده BBB باید قابلیت Webhooks و دسترسی به نشانی سامانه را فعال کند.")
    else:
        messages.success(request, "درخواست ثبت ورود و خروج فعال شد. دریافت زمان‌ها با اولین رویداد واقعی کلاس قابل تأیید است؛ زمان‌های گذشته بازیابی نمی‌شوند.")
    return redirect("live_attendance", class_id=class_id)


@csrf_exempt
@require_POST
def bbb_attendance_callback(request, config_id, class_id):
    hook = get_object_or_404(BBBAttendanceHook.objects.select_related(
        "configuration", "online_class"), online_class_id=class_id, configuration_id=config_id,
        configuration__is_active=True, online_class__bbb_configuration_id=config_id)
    body = request.body
    if len(body) > 131072:
        return HttpResponse(status=413)
    if not valid_callback_signature(hook, body, request.GET.get("checksum", "")):
        return HttpResponseForbidden()
    try:
        store_callback(hook, json.loads(request.POST.get("event", "")))
    except (ValueError, TypeError, KeyError, AttributeError, OverflowError, OSError):
        return HttpResponseBadRequest("Invalid attendance event")
    return HttpResponse(status=204)
