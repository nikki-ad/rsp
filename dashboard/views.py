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


        archived_years = AcademicYear.objects.filter(
            status=AcademicYear.Status.ARCHIVED,
        ).order_by("-title")

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
        "archived_years": archived_years,
    }

    return render(
        request,
        "dashboard/admin_dashboard.html",
        context,
    )

@login_required
def academic_year_archive(request, year_id):

    if not request.user.is_staff:
        return render(
            request,
            "dashboard/access_denied.html",
        )

    academic_year = AcademicYear.objects.get(
        id=year_id,
    )

    enrollments = (
        academic_year.enrollments
        .select_related(
            "student__user",
            "classroom",
            "classroom__grade",
        )
        .order_by(
            "classroom__grade__order",
            "classroom__name",
            "student__user__last_name",
        )
    )

    teachers = (
        TeacherProfile.objects.filter(
            class_assignments__classroom__academic_year=academic_year,
        )
        .distinct()
        .order_by(
            "user__last_name",
            "user__first_name",
        )
    )

    classrooms = (
        Classroom.objects.filter(
            academic_year=academic_year,
        )
        .select_related(
            "grade",
        )
        .order_by(
            "grade__order",
            "name",
        )
    )

    return render(
        request,
        "dashboard/academic_year_archive.html",
        {
            "academic_year": academic_year,
            "enrollments": enrollments,
            "teachers": teachers,
            "classrooms": classrooms,
        },
    )