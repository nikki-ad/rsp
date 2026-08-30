from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from academic.models import AcademicYear, Classroom, Enrollment, Grade, TeacherClassAssignment
from accounts.choices import Role
from accounts.forms import (
    StudentCreateForm,
    StudentEditForm,
    TeacherCreateForm,
    TeacherEditForm,
)
from accounts.models import StudentProfile, TeacherProfile
from accounts.permissions import manager_required
from activitylog.models import ActivityLog
from activitylog.utils import log_activity
from notifications import constants as notification_constants
from notifications.models import Announcement
from notifications.services import create_notification
from online_classes.models import BBBConfiguration, OnlineClass
from reports.models import StudentReportCard

from .forms import (
    AcademicYearForm,
    AnnouncementForm,
    BBBConfigurationForm,
    ClassroomForm,
    EnrollmentManageForm,
    GradeForm,
    OnlineClassForm,
    ReportCardForm,
)


def _save_created_by(form, request):
    obj = form.save(commit=False)
    if not obj.pk:
        obj.created_by = request.user
    obj.save()
    if hasattr(form, "save_m2m"):
        form.save_m2m()
    return obj


def _form_page(request, *, form, title, subtitle="", back_url="", wide=False, extra=None):
    context = {
        "form": form,
        "page_title": title,
        "page_subtitle": subtitle,
        "back_url": back_url,
        "wide": wide,
    }
    if extra:
        context.update(extra)
    return render(request, "dashboard/form.html", context)


@manager_required
def student_list(request):
    query = (request.GET.get("q") or "").strip()
    students = StudentProfile.objects.select_related("user").order_by(
        "user__last_name",
        "user__first_name",
    )
    if query:
        students = students.filter(
            Q(user__first_name__icontains=query)
            | Q(user__last_name__icontains=query)
            | Q(user__username__icontains=query)
            | Q(national_code__icontains=query)
            | Q(guardian_name__icontains=query)
        )

    active_year = AcademicYear.objects.filter(status=AcademicYear.Status.ACTIVE).first()
    enrollments = {}
    if active_year:
        for enrollment in Enrollment.objects.filter(
            academic_year=active_year,
            is_active=True,
        ).select_related("classroom", "classroom__grade", "student"):
            enrollments[enrollment.student_id] = enrollment

    student_rows = []
    for student in students:
        student_rows.append(
            {
                "student": student,
                "enrollment": enrollments.get(student.id),
            }
        )

    return render(
        request,
        "dashboard/student_list.html",
        {
            "student_rows": student_rows,
            "query": query,
            "active_year": active_year,
        },
    )


@manager_required
def create_student(request):
    if request.method == "POST":
        form = StudentCreateForm(request.POST)
        if form.is_valid():
            user = form.save(created_by=request.user)
            log_activity(
                request,
                action="student_created",
                description=f"دانش‌آموز {user.get_full_name()} ثبت شد.",
            )
            messages.success(
                request,
                f"دانش‌آموز {user.get_full_name()} ثبت شد. نام کاربری: {user.username}",
            )
            return redirect("student_list")
    else:
        form = StudentCreateForm()

    return _form_page(
        request,
        form=form,
        title="ثبت دانش‌آموز",
        subtitle="دانش‌آموز در سال تحصیلی فعال ثبت‌نام می‌شود.",
        back_url=reverse("student_list"),
    )


@manager_required
def edit_student(request, student_id):
    student = get_object_or_404(
        StudentProfile.objects.select_related("user"),
        id=student_id,
    )
    active_year = AcademicYear.objects.filter(status=AcademicYear.Status.ACTIVE).first()
    enrollment = None
    if active_year:
        enrollment = Enrollment.objects.filter(
            student=student,
            academic_year=active_year,
        ).select_related("classroom").first()

    initial = {
        "first_name": student.user.first_name,
        "last_name": student.user.last_name,
        "is_active": student.user.is_active,
        "national_code": student.national_code or "",
        "birth_date": student.birth_date,
        "guardian_name": student.guardian_name,
        "guardian_phone": student.guardian_phone,
        "address": student.address,
        "classroom": enrollment.classroom if enrollment and enrollment.is_active else None,
    }

    if request.method == "POST":
        form = StudentEditForm(request.POST, student=student)
        if form.is_valid():
            form.save()
            log_activity(
                request,
                action="student_updated",
                description=f"اطلاعات دانش‌آموز {student.user.get_full_name()} ویرایش شد.",
            )
            messages.success(request, "اطلاعات دانش‌آموز ذخیره شد.")
            return redirect("student_list")
    else:
        form = StudentEditForm(student=student, initial=initial)

    return _form_page(
        request,
        form=form,
        title=f"ویرایش {student.user.get_full_name() or student.user.username}",
        subtitle=f"نام کاربری: {student.user.username}",
        back_url=reverse("student_list"),
    )


@manager_required
def teacher_list(request):
    query = (request.GET.get("q") or "").strip()
    teachers = TeacherProfile.objects.select_related("user").order_by(
        "user__last_name",
        "user__first_name",
    )
    if query:
        teachers = teachers.filter(
            Q(user__first_name__icontains=query)
            | Q(user__last_name__icontains=query)
            | Q(user__username__icontains=query)
            | Q(personnel_code__icontains=query)
            | Q(expertise__icontains=query)
        )
    return render(
        request,
        "dashboard/teacher_list.html",
        {"teachers": teachers, "query": query},
    )


@manager_required
def create_teacher(request):
    if request.method == "POST":
        form = TeacherCreateForm(request.POST)
        if form.is_valid():
            user = form.save(created_by=request.user)
            log_activity(
                request,
                action="teacher_created",
                description=f"معلم {user.get_full_name()} ثبت شد.",
            )
            messages.success(
                request,
                f"معلم {user.get_full_name()} ثبت شد. نام کاربری: {user.username}",
            )
            return redirect("teacher_list")
    else:
        form = TeacherCreateForm()

    return _form_page(
        request,
        form=form,
        title="ثبت معلم",
        subtitle="حساب معلم ساخته می‌شود و می‌تواند به کلاس‌ها اختصاص داده شود.",
        back_url=reverse("teacher_list"),
        wide=True,
    )


@manager_required
def edit_teacher(request, teacher_id):
    teacher = get_object_or_404(
        TeacherProfile.objects.select_related("user"),
        id=teacher_id,
    )
    active_year = AcademicYear.objects.filter(status=AcademicYear.Status.ACTIVE).first()
    assigned = TeacherClassAssignment.objects.filter(teacher=teacher)
    if active_year:
        assigned = assigned.filter(classroom__academic_year=active_year)

    initial = {
        "first_name": teacher.user.first_name,
        "last_name": teacher.user.last_name,
        "is_active": teacher.user.is_active,
        "personnel_code": teacher.personnel_code or "",
        "expertise": teacher.expertise or "",
        "description": teacher.description or "",
        "classrooms": [item.classroom_id for item in assigned],
    }

    if request.method == "POST":
        form = TeacherEditForm(request.POST, teacher=teacher)
        if form.is_valid():
            form.save()
            log_activity(
                request,
                action="teacher_updated",
                description=f"اطلاعات معلم {teacher.user.get_full_name()} ویرایش شد.",
            )
            messages.success(request, "اطلاعات معلم ذخیره شد.")
            return redirect("teacher_list")
    else:
        form = TeacherEditForm(teacher=teacher, initial=initial)

    return _form_page(
        request,
        form=form,
        title=f"ویرایش {teacher.user.get_full_name() or teacher.user.username}",
        subtitle=f"نام کاربری: {teacher.user.username}",
        back_url=reverse("teacher_list"),
        wide=True,
    )


@manager_required
def academic_year_list(request):
    years = AcademicYear.objects.annotate(
        classroom_count=Count("classrooms", distinct=True),
        enrollment_count=Count("enrollments", distinct=True),
    )
    return render(request, "dashboard/academic_year_list.html", {"years": years})


@manager_required
def academic_year_form(request, year_id=None):
    instance = get_object_or_404(AcademicYear, id=year_id) if year_id else None
    if request.method == "POST":
        form = AcademicYearForm(request.POST, instance=instance)
        if form.is_valid():
            year = _save_created_by(form, request)
            log_activity(
                request,
                action="academic_year_saved",
                description=f"سال تحصیلی {year.title} ذخیره شد.",
            )
            messages.success(request, "سال تحصیلی ذخیره شد.")
            return redirect("academic_year_list")
    else:
        form = AcademicYearForm(instance=instance)

    return _form_page(
        request,
        form=form,
        title="ویرایش سال تحصیلی" if instance else "سال تحصیلی جدید",
        back_url=reverse("academic_year_list"),
    )


@manager_required
def academic_year_delete(request, year_id):
    year = get_object_or_404(AcademicYear, id=year_id)
    if request.method == "POST":
        title = year.title
        year.delete()
        log_activity(request, action="academic_year_deleted", description=f"سال تحصیلی {title} حذف شد.")
        messages.success(request, "سال تحصیلی حذف شد.")
        return redirect("academic_year_list")
    return render(
        request,
        "dashboard/confirm_delete.html",
        {
            "object_label": f"سال تحصیلی {year.title}",
            "back_url": reverse("academic_year_list"),
        },
    )


@manager_required
def grade_list(request):
    grades = Grade.objects.annotate(classroom_count=Count("classrooms"))
    return render(request, "dashboard/grade_list.html", {"grades": grades})


@manager_required
def grade_form(request, grade_id=None):
    instance = get_object_or_404(Grade, id=grade_id) if grade_id else None
    if request.method == "POST":
        form = GradeForm(request.POST, instance=instance)
        if form.is_valid():
            grade = _save_created_by(form, request)
            log_activity(request, action="grade_saved", description=f"پایه {grade.title} ذخیره شد.")
            messages.success(request, "پایه تحصیلی ذخیره شد.")
            return redirect("grade_list")
    else:
        form = GradeForm(instance=instance)
    return _form_page(
        request,
        form=form,
        title="ویرایش پایه" if instance else "پایه جدید",
        back_url=reverse("grade_list"),
    )


@manager_required
def grade_delete(request, grade_id):
    grade = get_object_or_404(Grade, id=grade_id)
    if request.method == "POST":
        title = grade.title
        grade.delete()
        log_activity(request, action="grade_deleted", description=f"پایه {title} حذف شد.")
        messages.success(request, "پایه تحصیلی حذف شد.")
        return redirect("grade_list")
    return render(
        request,
        "dashboard/confirm_delete.html",
        {"object_label": f"پایه {grade.title}", "back_url": reverse("grade_list")},
    )


@manager_required
def classroom_list(request):
    classrooms = Classroom.objects.select_related(
        "academic_year", "grade", "daily_report_responsible__user"
    ).annotate(
        student_count=Count(
            "enrollments",
            filter=Q(enrollments__is_active=True),
            distinct=True,
        ),
        teacher_count=Count("teacher_assignments", distinct=True),
    )
    return render(request, "dashboard/classroom_list.html", {"classrooms": classrooms})


@manager_required
def classroom_form(request, classroom_id=None):
    instance = get_object_or_404(Classroom, id=classroom_id) if classroom_id else None
    if request.method == "POST":
        form = ClassroomForm(request.POST, instance=instance)
        if form.is_valid():
            classroom = form.save(commit=False)
            if not classroom.pk:
                classroom.created_by = request.user
            classroom.save()
            selected_teachers = form.cleaned_data.get("teachers") or []
            TeacherClassAssignment.objects.filter(classroom=classroom).exclude(
                teacher__in=selected_teachers,
            ).delete()
            for teacher in selected_teachers:
                TeacherClassAssignment.objects.get_or_create(
                    teacher=teacher,
                    classroom=classroom,
                    defaults={"created_by": request.user},
                )
            log_activity(
                request,
                action="classroom_saved",
                description=f"کلاس {classroom} ذخیره شد.",
            )
            messages.success(request, "کلاس ذخیره شد.")
            return redirect("classroom_list")
    else:
        initial = {}
        form = ClassroomForm(instance=instance, initial=initial)
        if instance:
            form.fields["teachers"].initial = list(
                instance.teacher_assignments.values_list("teacher_id", flat=True)
            )

    return _form_page(
        request,
        form=form,
        title="ویرایش کلاس" if instance else "کلاس جدید",
        back_url=reverse("classroom_list"),
        wide=True,
    )


@manager_required
def classroom_delete(request, classroom_id):
    classroom = get_object_or_404(Classroom, id=classroom_id)
    if request.method == "POST":
        label = str(classroom)
        classroom.delete()
        log_activity(request, action="classroom_deleted", description=f"کلاس {label} حذف شد.")
        messages.success(request, "کلاس حذف شد.")
        return redirect("classroom_list")
    return render(
        request,
        "dashboard/confirm_delete.html",
        {"object_label": str(classroom), "back_url": reverse("classroom_list")},
    )


@manager_required
def enrollment_list(request):
    enrollments = Enrollment.objects.select_related(
        "student__user",
        "academic_year",
        "classroom",
        "classroom__grade",
    ).order_by("-academic_year__title", "classroom__grade__order", "student__user__last_name")
    query = (request.GET.get("q") or "").strip()
    if query:
        enrollments = enrollments.filter(
            Q(student__user__first_name__icontains=query)
            | Q(student__user__last_name__icontains=query)
            | Q(classroom__name__icontains=query)
        )
    return render(
        request,
        "dashboard/enrollment_list.html",
        {"enrollments": enrollments, "query": query},
    )


@manager_required
def enrollment_form(request, enrollment_id=None):
    instance = get_object_or_404(Enrollment, id=enrollment_id) if enrollment_id else None
    if request.method == "POST":
        form = EnrollmentManageForm(request.POST, instance=instance)
        if form.is_valid():
            enrollment = _save_created_by(form, request)
            log_activity(
                request,
                action="enrollment_saved",
                description=f"ثبت‌نام {enrollment} ذخیره شد.",
            )
            messages.success(request, "ثبت‌نام ذخیره شد.")
            return redirect("enrollment_list")
    else:
        form = EnrollmentManageForm(instance=instance)
    return _form_page(
        request,
        form=form,
        title="ویرایش ثبت‌نام" if instance else "ثبت‌نام جدید",
        back_url=reverse("enrollment_list"),
    )


@manager_required
def enrollment_delete(request, enrollment_id):
    enrollment = get_object_or_404(Enrollment, id=enrollment_id)
    if request.method == "POST":
        label = str(enrollment)
        enrollment.delete()
        log_activity(request, action="enrollment_deleted", description=f"ثبت‌نام {label} حذف شد.")
        messages.success(request, "ثبت‌نام حذف شد.")
        return redirect("enrollment_list")
    return render(
        request,
        "dashboard/confirm_delete.html",
        {"object_label": str(enrollment), "back_url": reverse("enrollment_list")},
    )


@manager_required
def announcement_list(request):
    announcements = Announcement.objects.select_related("classroom", "classroom__grade")
    return render(
        request,
        "dashboard/announcement_list.html",
        {"announcements": announcements},
    )


def _notify_announcement(announcement):
    recipients = []
    if announcement.audience == Announcement.Audience.ALL:
        from django.contrib.auth import get_user_model
        User = get_user_model()
        recipients = User.objects.filter(is_active=True).exclude(
            role__in=[Role.SUPER_ADMIN],
        )
    elif announcement.audience == Announcement.Audience.STUDENTS:
        recipients = [
            profile.user
            for profile in StudentProfile.objects.select_related("user").filter(user__is_active=True)
        ]
    elif announcement.audience == Announcement.Audience.TEACHERS:
        recipients = [
            profile.user
            for profile in TeacherProfile.objects.select_related("user").filter(user__is_active=True)
        ]
    elif announcement.audience == Announcement.Audience.CLASSROOM and announcement.classroom:
        recipients = [
            enrollment.student.user
            for enrollment in announcement.classroom.enrollments.filter(
                is_active=True,
            ).select_related("student__user")
        ]

    for recipient in recipients:
        create_notification(
            recipient=recipient,
            notification_type=notification_constants.ANNOUNCEMENT,
            title=announcement.title,
            message=announcement.message,
            url=reverse("notification_list"),
        )


@manager_required
def announcement_form(request, announcement_id=None):
    instance = get_object_or_404(Announcement, id=announcement_id) if announcement_id else None
    is_new = instance is None
    if request.method == "POST":
        form = AnnouncementForm(request.POST, instance=instance)
        if form.is_valid():
            announcement = form.save(commit=False)
            announcement.full_clean()
            if is_new:
                announcement.created_by = request.user
            announcement.save()
            log_activity(
                request,
                action="announcement_saved",
                description=f"اطلاعیه «{announcement.title}» ذخیره شد.",
            )
            if is_new and announcement.is_active and announcement.publish_at <= timezone.now():
                _notify_announcement(announcement)
            messages.success(request, "اطلاعیه ذخیره شد.")
            return redirect("announcement_list")
    else:
        form = AnnouncementForm(instance=instance)
    return _form_page(
        request,
        form=form,
        title="ویرایش اطلاعیه" if instance else "اطلاعیه جدید",
        back_url=reverse("announcement_list"),
    )


@manager_required
def announcement_delete(request, announcement_id):
    announcement = get_object_or_404(Announcement, id=announcement_id)
    if request.method == "POST":
        title = announcement.title
        announcement.delete()
        log_activity(request, action="announcement_deleted", description=f"اطلاعیه «{title}» حذف شد.")
        messages.success(request, "اطلاعیه حذف شد.")
        return redirect("announcement_list")
    return render(
        request,
        "dashboard/confirm_delete.html",
        {"object_label": announcement.title, "back_url": reverse("announcement_list")},
    )


@manager_required
def report_card_list(request):
    query = (request.GET.get("q") or "").strip()
    report_cards = StudentReportCard.objects.select_related("student__user")
    if query:
        report_cards = report_cards.filter(
            Q(title__icontains=query)
            | Q(student__user__first_name__icontains=query)
            | Q(student__user__last_name__icontains=query)
        )
    return render(
        request,
        "dashboard/report_card_list.html",
        {"report_cards": report_cards, "query": query},
    )


@manager_required
def report_card_form(request, report_card_id=None):
    instance = get_object_or_404(StudentReportCard, id=report_card_id) if report_card_id else None
    if request.method == "POST":
        form = ReportCardForm(request.POST, request.FILES, instance=instance)
        if form.is_valid():
            report_card = _save_created_by(form, request)
            log_activity(
                request,
                action="report_card_saved",
                description=f"کارنامه «{report_card.title}» برای {report_card.student} ذخیره شد.",
            )
            messages.success(request, "کارنامه ذخیره شد.")
            return redirect("report_card_list")
    else:
        form = ReportCardForm(instance=instance)
    return _form_page(
        request,
        form=form,
        title="ویرایش کارنامه" if instance else "ثبت کارنامه",
        back_url=reverse("report_card_list"),
    )


@manager_required
def report_card_delete(request, report_card_id):
    report_card = get_object_or_404(StudentReportCard, id=report_card_id)
    if request.method == "POST":
        title = report_card.title
        report_card.delete()
        log_activity(request, action="report_card_deleted", description=f"کارنامه «{title}» حذف شد.")
        messages.success(request, "کارنامه حذف شد.")
        return redirect("report_card_list")
    return render(
        request,
        "dashboard/confirm_delete.html",
        {"object_label": str(report_card), "back_url": reverse("report_card_list")},
    )


@manager_required
def online_class_manage_list(request):
    online_classes = OnlineClass.objects.select_related(
        "academic_year",
        "bbb_configuration",
    ).annotate(
        student_count=Count("students", distinct=True),
        teacher_count=Count("teachers", distinct=True),
    )
    return render(
        request,
        "dashboard/online_class_manage_list.html",
        {"online_classes": online_classes},
    )


@manager_required
def online_class_form(request, class_id=None):
    instance = get_object_or_404(OnlineClass, id=class_id) if class_id else None
    if request.method == "POST":
        form = OnlineClassForm(request.POST, instance=instance)
        if form.is_valid():
            online_class = form.save(commit=False)
            if not online_class.pk:
                online_class.created_by = request.user
            online_class.save()
            form.save_m2m()
            log_activity(
                request,
                action="online_class_saved",
                description=f"کلاس آنلاین «{online_class.title}» ذخیره شد.",
            )
            messages.success(request, "کلاس آنلاین ذخیره شد.")
            return redirect("online_class_manage_list")
    else:
        form = OnlineClassForm(instance=instance)
    return _form_page(
        request,
        form=form,
        title="ویرایش کلاس آنلاین" if instance else "کلاس آنلاین جدید",
        back_url=reverse("online_class_manage_list"),
        wide=True,
        extra={"year_people_endpoint": reverse("load_year_people")},
    )


@manager_required
def online_class_delete(request, class_id):
    online_class = get_object_or_404(OnlineClass, id=class_id)
    if request.method == "POST":
        title = online_class.title
        online_class.delete()
        log_activity(request, action="online_class_deleted", description=f"کلاس آنلاین «{title}» حذف شد.")
        messages.success(request, "کلاس آنلاین حذف شد.")
        return redirect("online_class_manage_list")
    return render(
        request,
        "dashboard/confirm_delete.html",
        {"object_label": online_class.title, "back_url": reverse("online_class_manage_list")},
    )


@manager_required
def bbb_config_list(request):
    configs = BBBConfiguration.objects.all()
    return render(request, "dashboard/bbb_config_list.html", {"configs": configs})


@manager_required
def bbb_config_form(request, config_id=None):
    instance = get_object_or_404(BBBConfiguration, id=config_id) if config_id else None
    if request.method == "POST":
        form = BBBConfigurationForm(request.POST, instance=instance)
        if form.is_valid():
            _save_created_by(form, request)
            messages.success(request, "تنظیمات BigBlueButton ذخیره شد.")
            return redirect("bbb_config_list")
    else:
        form = BBBConfigurationForm(instance=instance)
    return _form_page(
        request,
        form=form,
        title="ویرایش سرویس BBB" if instance else "سرویس BBB جدید",
        back_url=reverse("bbb_config_list"),
    )


@manager_required
def bbb_config_delete(request, config_id):
    config = get_object_or_404(BBBConfiguration, id=config_id)
    if request.method == "POST":
        config.delete()
        messages.success(request, "سرویس حذف شد.")
        return redirect("bbb_config_list")
    return render(
        request,
        "dashboard/confirm_delete.html",
        {"object_label": config.name, "back_url": reverse("bbb_config_list")},
    )


@manager_required
def activity_log_list(request):
    query = (request.GET.get("q") or "").strip()
    logs = ActivityLog.objects.select_related("user")
    if query:
        logs = logs.filter(
            Q(action__icontains=query)
            | Q(description__icontains=query)
            | Q(user__first_name__icontains=query)
            | Q(user__last_name__icontains=query)
            | Q(user__username__icontains=query)
        )
    return render(
        request,
        "dashboard/activity_log_list.html",
        {"logs": logs[:400], "query": query},
    )


@login_required
def load_year_people(request):
    if not request.user.is_school_admin:
        return JsonResponse({"students": [], "teachers": []}, status=403)

    year_id = request.GET.get("academic_year")
    students = StudentProfile.objects.select_related("user")
    if year_id:
        students = students.filter(
            enrollments__academic_year_id=year_id,
            enrollments__is_active=True,
        ).distinct()

    teachers = TeacherProfile.objects.select_related("user").order_by(
        "user__last_name",
        "user__first_name",
    )
    students = students.order_by("user__last_name", "user__first_name")

    return JsonResponse(
        {
            "students": [
                {"id": str(item.id), "name": str(item)}
                for item in students
            ],
            "teachers": [
                {"id": str(item.id), "name": str(item)}
                for item in teachers
            ],
        }
    )
