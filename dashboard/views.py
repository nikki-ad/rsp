from django.contrib.auth import get_user_model
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from accounts.models import TeacherProfile
from accounts.choices import Role
from accounts.permissions import is_school_admin
from academic.models import AcademicYear, Classroom, Enrollment
from academic.routine_reports import classroom_routine_report
from assignments.models import Assignment
from cafeteria.models import CafeteriaReservation
from materials.models import EducationalMaterial
from messaging.models import Conversation
from online_classes.models import OnlineClass
from .xlsx_export import build_routine_report_xlsx
from .forms import GeneralUserForm
from activitylog.utils import log_activity

User = get_user_model()


def _routine_reports_for_active_year():
    active_year = AcademicYear.objects.filter(status=AcademicYear.Status.ACTIVE).first()
    if not active_year:
        return active_year, []
    reports = [
        classroom_routine_report(classroom)
        for classroom in Classroom.objects.filter(academic_year=active_year)
        .select_related("grade", "daily_report_responsible__user")
        .order_by("grade__order", "name")
    ]
    return active_year, reports


@login_required
def admin_dashboard(request):
    if not is_school_admin(request.user):
        return render(request, "dashboard/access_denied.html", status=403)

    active_year = AcademicYear.objects.filter(
        status=AcademicYear.Status.ACTIVE,
    ).first()

    student_count = 0
    teacher_count = 0
    classroom_count = 0
    online_class_count = 0
    pending_receipt_count = 0

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
        pending_receipt_count = (
            CafeteriaReservation.objects.filter(
                payment_status="receipt_pending",
                student__enrollments__academic_year=active_year,
                student__enrollments__is_active=True,
            )
            .distinct()
            .count()
        )

    archived_years = AcademicYear.objects.filter(
        status=AcademicYear.Status.ARCHIVED,
    ).order_by("-title")

    context = {
        "active_year": active_year,
        "student_count": student_count,
        "teacher_count": teacher_count,
        "classroom_count": classroom_count,
        "online_class_count": online_class_count,
        "pending_receipt_count": pending_receipt_count,
        "material_count": EducationalMaterial.objects.count(),
        "assignment_count": Assignment.objects.count(),
        "conversation_count": Conversation.objects.count(),
        "archived_years": archived_years,
    }

    return render(request, "dashboard/admin_dashboard.html", context)


@login_required
def routine_report_list(request):
    if not is_school_admin(request.user):
        return render(request, "dashboard/access_denied.html", status=403)
    active_year, routine_reports = _routine_reports_for_active_year()
    return render(request, "dashboard/routine_report_list.html", {
        "active_year": active_year,
        "routine_reports": routine_reports,
    })


@login_required
def routine_report_excel(request):
    if not is_school_admin(request.user):
        return render(request, "dashboard/access_denied.html", status=403)

    active_year, routine_reports = _routine_reports_for_active_year()
    headers = [
        "کلاس", "سال تحصیلی", "مسئول پیگیری", "تعداد دانش‌آموزان",
        "درصد مشارکت", "میانگین مطالعه", "میانگین انجام تکالیف",
        "میانگین ساعت خواب", "نیازمند پیگیری",
    ]
    rows = []
    for report in routine_reports:
        responsible = report["classroom"].daily_report_responsible
        rows.append([
            str(report["classroom"]),
            active_year.title if active_year else "—",
            str(responsible) if responsible else "تعیین نشده",
            report["student_count"],
            report["participation_percent"] / 100,
            report["study_average"],
            report["homework_average"],
            report["sleep_average"],
            report["follow_up_count"],
        ])

    response = HttpResponse(
        build_routine_report_xlsx(headers, rows),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    response["Content-Disposition"] = 'attachment; filename="daily-routine-report.xlsx"'
    return response


@login_required
def user_list(request):
    if not is_school_admin(request.user):
        return render(request, "dashboard/access_denied.html", status=403)

    query = (request.GET.get("q") or "").strip()
    selected_role = (request.GET.get("role") or "").strip()
    valid_roles = {value for value, _label in Role.choices}
    users = User.objects.all().order_by("last_name", "first_name", "username")
    if query:
        users = users.filter(
            Q(first_name__icontains=query)
            | Q(last_name__icontains=query)
            | Q(username__icontains=query)
        )
    if selected_role in valid_roles:
        users = users.filter(role=selected_role)
    else:
        selected_role = ""

    return render(request, "dashboard/user_list.html", {
        "users": users,
        "query": query,
        "selected_role": selected_role,
        "role_choices": Role.choices,
    })


@login_required
def general_user_form(request, user_id=None):
    if not is_school_admin(request.user):
        return render(request, "dashboard/access_denied.html", status=403)

    user_obj = get_object_or_404(User, id=user_id) if user_id else None
    if user_obj and user_obj.role == Role.STUDENT and hasattr(user_obj, "student_profile"):
        return redirect("edit_student", student_id=user_obj.student_profile.id)
    if user_obj and user_obj.role == Role.TEACHER and hasattr(user_obj, "teacher_profile"):
        return redirect("edit_teacher", teacher_id=user_obj.teacher_profile.id)
    if user_obj and (user_obj.is_superuser or user_obj.role == Role.SUPER_ADMIN) and not request.user.is_superuser:
        return render(request, "dashboard/access_denied.html", status=403)

    if request.method == "POST":
        form = GeneralUserForm(
            request.POST,
            instance=user_obj,
            allow_super_admin=request.user.is_superuser,
        )
        if form.is_valid():
            saved_user = form.save()
            log_activity(
                request,
                action="user_updated" if user_obj else "user_created",
                description=f"حساب کاربری {saved_user.username} ذخیره شد.",
            )
            messages.success(request, "حساب کاربری با موفقیت ذخیره شد.")
            return redirect("user_list")
    else:
        form = GeneralUserForm(
            instance=user_obj,
            allow_super_admin=request.user.is_superuser,
        )

    return render(request, "dashboard/form.html", {
        "form": form,
        "page_title": "ویرایش کاربر" if user_obj else "کاربر مدیریتی جدید",
        "page_subtitle": "برای مدیر، امور مالی و اپراتور حساب بسازید یا رمز را تغییر دهید.",
        "back_url": reverse("user_list"),
    })


@login_required
def academic_year_archive(request, year_id):
    if not is_school_admin(request.user):
        return render(request, "dashboard/access_denied.html", status=403)

    academic_year = get_object_or_404(AcademicYear, id=year_id)

    query = (request.GET.get("q") or "").strip()
    enrollments = (
        academic_year.enrollments.select_related(
            "student__user",
            "classroom",
            "classroom__grade",
        ).order_by(
            "classroom__grade__order",
            "classroom__name",
            "student__user__last_name",
        )
    )
    if query:
        enrollments = enrollments.filter(
            Q(student__user__first_name__icontains=query)
            | Q(student__user__last_name__icontains=query)
        )

    teachers = (
        TeacherProfile.objects.filter(
            class_assignments__classroom__academic_year=academic_year,
        )
        .distinct()
        .order_by("user__last_name", "user__first_name")
    )

    classrooms = (
        Classroom.objects.filter(academic_year=academic_year)
        .select_related("grade")
        .order_by("grade__order", "name")
    )

    return render(
        request,
        "dashboard/academic_year_archive.html",
        {
            "academic_year": academic_year,
            "enrollments": enrollments,
            "teachers": teachers,
            "classrooms": classrooms,
            "query": query,
        },
    )
