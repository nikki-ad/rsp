from django.contrib.auth.decorators import login_required
from django.shortcuts import render
import requests
from .models import OnlineClass
from django.shortcuts import get_object_or_404, redirect
from .services import create_bbb_meeting, build_bbb_join_url
from .services import (
    create_bbb_meeting,
    build_bbb_join_url,
    get_bbb_live_attendees,
)
from accounts.choices import Role
from academic.models import AcademicYear




@login_required
def online_class_list(request):

    user = request.user

    online_classes = OnlineClass.objects.none()

    if hasattr(user, "student_profile"):

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

    elif user.is_superuser or user.role in [
        Role.SUPER_ADMIN,
        Role.SCHOOL_MANAGER,
    ]:
        online_classes = OnlineClass.objects.filter(
            is_active=True,
            academic_year__status=AcademicYear.Status.ACTIVE,
        ).select_related(
            "academic_year",
            "bbb_configuration",
        )

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
    if hasattr(user, "student_profile"):

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

    elif user.is_superuser or user.role in [
        Role.SUPER_ADMIN,
        Role.SCHOOL_MANAGER,
    ]:
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

        # اگر جلسه وجود نداشته باشد BBB آن را ایجاد می‌کند.
        create_bbb_meeting(
            online_class
        )

        join_url = build_bbb_join_url(
            online_class=online_class,
            user=user,
            role=role,
        )

        return redirect(join_url)


    return redirect("online_class_list")


@login_required
def live_attendance(request, class_id):

    online_class = get_object_or_404(
        OnlineClass,
        id=class_id,
        provider="bbb",
        is_active=True,
        academic_year__status=AcademicYear.Status.ACTIVE,
    )

    if not (
        request.user.is_staff
        or request.user.is_superuser
        or request.user.role in [
            Role.SUPER_ADMIN,
            Role.SCHOOL_MANAGER,
        ]
    ):
        return redirect("online_class_list")

    try:

        attendees = get_bbb_live_attendees(
            online_class
        )

        attendance_error = None

    except (
        requests.RequestException,
        ValueError,
    ):

        attendees = []
        attendance_error = (
            "در حال حاضر امکان دریافت وضعیت زنده "
            "از BigBlueButton وجود ندارد."
        )

    present_user_ids = {
        attendee["user_id"]
        for attendee in attendees
        if attendee.get("user_id")
    }

    students = (
        online_class.students
        .select_related("user")
        .all()
    )

    attendance_rows = []

    for student in students:

        attendance_rows.append(
            {
                "student": student,
                "is_present": str(student.user.id) in present_user_ids,
            }
        )

    return render(
        request,
        "online_classes/live_attendance.html",
        {
            "online_class": online_class,
            "attendance_rows": attendance_rows,
            "attendees": attendees,
            "attendance_error": attendance_error,
        },
    )