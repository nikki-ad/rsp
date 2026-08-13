from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from accounts.models import TeacherProfile
from academic.models import (
    AcademicYear,
    Classroom,
    Enrollment,
    TeacherClassAssignment,
)
from cafeteria.models import CafeteriaReservation
from online_classes.models import OnlineClass


@login_required
def admin_dashboard(request):

    if not request.user.is_staff:
        return render(
            request,
            "dashboard/access_denied.html",
        )

    active_year = AcademicYear.objects.filter(
        status=AcademicYear.Status.ACTIVE,
    ).first()

    student_count = 0
    teacher_count = 0
    classroom_count = 0
    online_class_count = 0

    if active_year:

        student_count = Enrollment.objects.filter(
            academic_year=active_year,
            is_active=True,
        ).count()

        teacher_count = (
            TeacherProfile.objects.filter(
                class_assignments__classroom__academic_year=active_year,
            )
            .distinct()
            .count()
        )

        classroom_count = Classroom.objects.filter(
            academic_year=active_year,
        ).count()

        online_class_count = OnlineClass.objects.filter(
            academic_year=active_year,
            is_active=True,
        ).count()

    context = {
        "active_year": active_year,
        "student_count": student_count,
        "teacher_count": teacher_count,
        "classroom_count": classroom_count,
        "online_class_count": online_class_count,
        "pending_receipt_count": (
            CafeteriaReservation.objects.filter(
                payment_status="receipt_pending",
                student__enrollments__academic_year=active_year,
                student__enrollments__is_active=True,
            )
            .distinct()
            .count()
            if active_year
            else 0
        ),
    }

    return render(
        request,
        "dashboard/admin_dashboard.html",
        context,
    )