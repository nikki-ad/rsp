from django.contrib import messages
from django.contrib.auth import authenticate, login, get_user_model
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.db.models import Q
from django.utils import timezone

from academic.models import AcademicYear, Classroom, ClassroomSchedule, Enrollment, StudentDailyRoutine
from academic.routine_reports import classroom_routine_report
from activitylog.utils import log_activity
from materials.forms import EducationalMaterialCreateForm
from materials.models import EducationalMaterial
from notifications import constants as notification_constants
from notifications.models import Announcement, Notification
from notifications.services import create_notification
from reports.models import StudentReportCard

from .forms import ProfileForm, StudentSelfProfileForm, TeacherSelfProfileForm
from .routine_forms import StudentDailyRoutineForm
from .permissions import post_login_redirect_name

User = get_user_model()


@login_required
def profile(request):
    extra_form = None
    extra_instance = None
    if hasattr(request.user, "student_profile"):
        extra_instance = request.user.student_profile
    elif hasattr(request.user, "teacher_profile"):
        extra_instance = request.user.teacher_profile

    if request.method == "POST":
        form = ProfileForm(request.POST, request.FILES, instance=request.user)
        if extra_instance and hasattr(request.user, "student_profile"):
            extra_form = StudentSelfProfileForm(request.POST, instance=extra_instance)
        elif extra_instance:
            extra_form = TeacherSelfProfileForm(request.POST, instance=extra_instance)
        extra_valid = extra_form.is_valid() if extra_form else True
        if form.is_valid() and extra_valid:
            form.save()
            if extra_form:
                extra_form.save()
            messages.success(request, "پروفایل شما ذخیره شد.")
            return redirect("profile")
    else:
        form = ProfileForm(instance=request.user)
        if extra_instance and hasattr(request.user, "student_profile"):
            extra_form = StudentSelfProfileForm(instance=extra_instance)
        elif extra_instance:
            extra_form = TeacherSelfProfileForm(instance=extra_instance)

    return render(request, "accounts/profile.html", {"form": form, "extra_form": extra_form})


@login_required
def load_classrooms(request):
    academic_year_id = request.GET.get("academic_year")
    classrooms = Classroom.objects.filter(academic_year_id=academic_year_id).order_by("grade__order", "name")
    return JsonResponse({"classrooms": [{"id": classroom.id, "name": str(classroom)} for classroom in classrooms]})


@login_required
def teacher_dashboard(request):
    if not hasattr(request.user, "teacher_profile"):
        return render(request, "dashboard/access_denied.html", status=403)
    teacher = request.user.teacher_profile
    classrooms = Classroom.objects.filter(teacher_assignments__teacher=teacher, academic_year__status=AcademicYear.Status.ACTIVE).distinct()
    report_classrooms = Classroom.objects.filter(
        daily_report_responsible=teacher,
        academic_year__status=AcademicYear.Status.ACTIVE,
    ).select_related("grade", "academic_year")
    unread_notification_count = Notification.objects.filter(recipient=request.user, is_read=False).count()
    announcements = Announcement.objects.filter(is_active=True, publish_at__lte=timezone.now()).filter(Q(audience=Announcement.Audience.ALL) | Q(audience=Announcement.Audience.TEACHERS)).order_by("-publish_at")
    return render(request, "accounts/teacher_dashboard.html", {"classrooms": classrooms, "report_classrooms": report_classrooms, "unread_notification_count": unread_notification_count, "announcements": announcements})


@login_required
def teacher_routine_report(request, classroom_id):
    if not hasattr(request.user, "teacher_profile"):
        return render(request, "dashboard/access_denied.html", status=403)
    classroom = get_object_or_404(
        Classroom.objects.select_related("grade", "academic_year"),
        id=classroom_id,
        daily_report_responsible=request.user.teacher_profile,
        academic_year__status=AcademicYear.Status.ACTIVE,
    )
    return render(
        request,
        "accounts/teacher_routine_report.html",
        {"report": classroom_routine_report(classroom)},
    )


@login_required
def teacher_class_detail(request, classroom_id):
    if not hasattr(request.user, "teacher_profile"):
        return render(request, "dashboard/access_denied.html", status=403)
    teacher = request.user.teacher_profile
    classroom = get_object_or_404(Classroom, id=classroom_id, teacher_assignments__teacher=teacher, academic_year__status=AcademicYear.Status.ACTIVE)
    return render(request, "accounts/teacher_class_detail.html", {"classroom": classroom, "students": classroom.enrollments.filter(is_active=True), "materials": classroom.materials.all(), "assignments": classroom.assignments.all()})


@login_required
def create_material(request, classroom_id):
    if not hasattr(request.user, "teacher_profile"):
        return render(request, "dashboard/access_denied.html", status=403)
    teacher = request.user.teacher_profile
    classroom = get_object_or_404(Classroom, id=classroom_id, teacher_assignments__teacher=teacher, academic_year__status=AcademicYear.Status.ACTIVE)
    if request.method == "POST":
        form = EducationalMaterialCreateForm(request.POST, request.FILES, teacher=teacher, hide_classrooms=True)
        if form.is_valid():
            material = form.save(commit=False)
            material.teacher = teacher
            material.save()
            material.classrooms.add(classroom)
            for enrollment in classroom.enrollments.filter(is_active=True).select_related("student__user"):
                create_notification(recipient=enrollment.student.user, notification_type=notification_constants.MATERIAL, title=f"مطلب آموزشی جدید: {material.title}", message=f"برای کلاس {classroom} یک مطلب آموزشی جدید منتشر شد.", url=reverse("student_material_list"))
            return redirect("teacher_class_detail", classroom_id=classroom.id)
    else:
        form = EducationalMaterialCreateForm(teacher=teacher, hide_classrooms=True)
    return render(request, "accounts/create_material.html", {"form": form, "classroom": classroom})


@login_required
def student_dashboard(request):
    if not hasattr(request.user, "student_profile"):
        return render(request, "dashboard/access_denied.html", status=403)

    student = request.user.student_profile
    today = timezone.localdate()
    today_routine = StudentDailyRoutine.objects.filter(student=student, record_date=today).first()
    if request.method == "POST":
        routine_form = StudentDailyRoutineForm(request.POST, instance=today_routine)
        if routine_form.is_valid():
            routine = routine_form.save(commit=False)
            routine.student = student
            routine.record_date = today
            if not routine.pk:
                routine.created_by = request.user
            routine.save()
            messages.success(request, "برنامه امروزت با موفقیت ثبت شد 🌱")
            return redirect("student_dashboard")
    else:
        routine_form = StudentDailyRoutineForm(instance=today_routine)
    recent_routines = student.daily_routines.order_by("-record_date")[:7]
    enrollment = Enrollment.objects.filter(student=student, is_active=True, academic_year__status=AcademicYear.Status.ACTIVE).select_related("academic_year", "classroom").first()
    teachers = []
    materials = []
    assignments = []
    submitted_assignment_ids = set()
    student_submissions = {}
    assignment_items = []

    schedule_days = [
        {"key": ClassroomSchedule.Day.SATURDAY, "label": "شنبه", "css": "schedule-saturday"},
        {"key": ClassroomSchedule.Day.SUNDAY, "label": "یکشنبه", "css": "schedule-sunday"},
        {"key": ClassroomSchedule.Day.MONDAY, "label": "دوشنبه", "css": "schedule-monday"},
        {"key": ClassroomSchedule.Day.TUESDAY, "label": "سه‌شنبه", "css": "schedule-tuesday"},
        {"key": ClassroomSchedule.Day.WEDNESDAY, "label": "چهارشنبه", "css": "schedule-wednesday"},
    ]
    schedule_lookup = {}

    if enrollment:
        classroom = enrollment.classroom
        teachers = classroom.teacher_assignments.select_related("teacher__user")
        materials = classroom.materials.all().order_by("-created_at")[:1]
        assignments = classroom.assignments.all().order_by("-created_at")[:1]
        submitted_assignment_ids = set(student.assignment_submissions.values_list("assignment_id", flat=True))
        student_submissions = {submission.assignment_id: submission for submission in student.assignment_submissions.select_related("assignment")}
        assignment_items = [{"assignment": assignment, "submission": student_submissions.get(assignment.id)} for assignment in assignments]
        schedule_lookup = {(item.day, item.period): item.subject for item in classroom.weekly_schedule.all()}

    weekly_schedule = []
    for day in schedule_days:
        weekly_schedule.append({
            **day,
            "periods": [schedule_lookup.get((day["key"], period), "") for period in range(1, 6)],
        })

    unread_notification_count = Notification.objects.filter(recipient=request.user, is_read=False).count()
    cafeteria_reservation = student.cafeteria_reservations.select_related("week").order_by("-created_at").first()
    report_cards = StudentReportCard.objects.filter(student=student, is_active=True).order_by("-created_at")
    announcements = Announcement.objects.filter(is_active=True, publish_at__lte=timezone.now()).filter(
        Q(audience=Announcement.Audience.ALL)
        | Q(audience=Announcement.Audience.STUDENTS)
        | Q(audience=Announcement.Audience.CLASSROOM, classroom=enrollment.classroom if enrollment else None)
    ).order_by("-publish_at")

    return render(request, "accounts/student_dashboard.html", {
        "student": student,
        "enrollment": enrollment,
        "materials": materials,
        "assignments": assignments,
        "submitted_assignment_ids": submitted_assignment_ids,
        "teachers": teachers,
        "unread_notification_count": unread_notification_count,
        "student_submissions": student_submissions,
        "assignment_items": assignment_items,
        "cafeteria_reservation": cafeteria_reservation,
        "report_cards": report_cards,
        "announcements": announcements,
        "weekly_schedule": weekly_schedule,
        "routine_form": routine_form,
        "today_routine": today_routine,
        "recent_routines": recent_routines,
    })


@login_required
def manager_dashboard(request):
    return redirect("admin_dashboard")


@login_required
def delete_material(request, material_id):
    if not hasattr(request.user, "teacher_profile"):
        return render(request, "dashboard/access_denied.html", status=403)
    teacher = request.user.teacher_profile
    material = get_object_or_404(EducationalMaterial, id=material_id, teacher=teacher)
    classroom = material.classrooms.filter(teacher_assignments__teacher=teacher, academic_year__status=AcademicYear.Status.ACTIVE).first()
    if classroom is None:
        return HttpResponseForbidden("شما اجازه حذف این مطلب را ندارید.")
    if request.method == "POST":
        classroom_id = classroom.id
        material.delete()
        return redirect("teacher_class_detail", classroom_id=classroom_id)
    return render(request, "accounts/delete_material.html", {"material": material, "classroom": classroom})


def user_login(request):
    error = None
    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            log_activity(request, action="login", description="ورود موفق به سامانه")
            return redirect(post_login_redirect_name(user))
        error = "نام کاربری یا رمز عبور اشتباه است."
    return render(request, "accounts/login.html", {"error": error})
