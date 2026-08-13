from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render , get_object_or_404
from django.http import JsonResponse
from .forms import StudentCreateForm, TeacherCreateForm
from academic.models import *
from materials.forms import EducationalMaterialCreateForm
from materials.models import EducationalMaterial
from django.contrib.auth import get_user_model
from notifications.models import Notification
from academic.models import Classroom
from materials.models import EducationalMaterial
from assignments.models import Assignment
from messaging.models import Conversation
from django.http import HttpResponseForbidden
from .choices import Role
from django.urls import reverse
from notifications import constants as notification_constants
from notifications.services import create_notification
from reports.models import StudentReportCard
from django.db.models import Q
from django.utils import timezone
from notifications.models import Announcement






User = get_user_model()

@login_required
def create_student(request):
    if request.method == "POST":
        form = StudentCreateForm(request.POST)

        if form.is_valid():
            user = form.save()

            messages.success(
                request,
                f"دانش‌آموز {user.get_full_name()} با موفقیت ثبت شد."
            )

            return redirect("create_student")

    else:
        form = StudentCreateForm()

    return render(
        request,
        "accounts/create_student.html",
        {
            "form": form,
        }
    )



def create_teacher(request):

    if request.method == "POST":
        form = TeacherCreateForm(request.POST)

        if form.is_valid():
            form.save()
            return redirect("create_teacher")

    else:
        form = TeacherCreateForm()

    return render(
        request,
        "accounts/create_teacher.html",
        {
            "form": form,
        }
    )


def load_classrooms(request):
    academic_year_id = request.GET.get("academic_year")

    classrooms = Classroom.objects.filter(
        academic_year_id=academic_year_id
    ).order_by(
        "grade__order",
        "name",
    )

    data = [
        {
            "id": classroom.id,
            "name": str(classroom),
        }
        for classroom in classrooms
    ]

    return JsonResponse(
        {
            "classrooms": data
        }
    )


@login_required
def teacher_dashboard(request):

    teacher = request.user.teacher_profile

    classrooms = Classroom.objects.filter(
        teacher_assignments__teacher=teacher
    )
    unread_notification_count = Notification.objects.filter(
        recipient=request.user,
        is_read=False,
    ).count()


    announcements = Announcement.objects.filter(
        is_active=True,
        publish_at__lte=timezone.now(),
    ).filter(
        Q(audience=Announcement.Audience.ALL)
        | Q(audience=Announcement.Audience.TEACHERS)
    ).order_by("-publish_at")


    return render(
        request,
        "accounts/teacher_dashboard.html",
        {
            "classrooms": classrooms,
            "unread_notification_count": unread_notification_count,
            "announcements": announcements,
        }
    )



@login_required
def teacher_class_detail(request, classroom_id):

    teacher = request.user.teacher_profile

    classroom = Classroom.objects.get(
        id=classroom_id,
        teacher_assignments__teacher=teacher,
    )

    students = classroom.enrollments.filter(
        is_active=True
    )
    materials = classroom.materials.all()
    assignments = classroom.assignments.all()
    return render(
        request,
        "accounts/teacher_class_detail.html",
        {
            "classroom": classroom,
            "students": students,
            "materials": materials,
            "assignments": assignments,
        }
    )


@login_required
def create_material(request, classroom_id):

    teacher = request.user.teacher_profile

    classroom = Classroom.objects.get(
        id=classroom_id,
        teacher_assignments__teacher=teacher,
    )

    if request.method == "POST":
        form = EducationalMaterialCreateForm(request.POST, request.FILES)

        if form.is_valid():
            material = form.save(commit=False)

            material.teacher = teacher

            material.save()

            material.classrooms.add(classroom)
            active_enrollments = classroom.enrollments.filter(
                is_active=True,
            ).select_related(
                "student__user",
            )

            for enrollment in active_enrollments:
                create_notification(
                    recipient=enrollment.student.user,
                    notification_type=notification_constants.MATERIAL,
                    title=f"مطلب آموزشی جدید: {material.title}",
                    message=f"برای کلاس {classroom} یک مطلب آموزشی جدید منتشر شد.",
                    url=reverse("student_dashboard"),
                )

            return redirect(
                "teacher_class_detail",
                classroom_id=classroom.id,
            )

    else:
        form = EducationalMaterialCreateForm()

    return render(
        request,
        "accounts/create_material.html",
        {
            "form": form,
            "classroom": classroom,
        }
    )

@login_required
def student_dashboard(request):

    student = request.user.student_profile

    enrollment = Enrollment.objects.filter(
        student=student,
        is_active=True,
    ).first()

    teachers = []

    if enrollment:
        teachers = enrollment.classroom.teacher_assignments.select_related(
            "teacher__user"
        )

    materials = []
    assignments = []
    submitted_assignment_ids = set()

    if enrollment:
        classroom = enrollment.classroom

        materials = classroom.materials.all().order_by("-created_at")
        assignments = classroom.assignments.all().order_by("-created_at")

        submitted_assignment_ids = set(
            student.assignment_submissions.values_list(
                "assignment_id",
                flat=True,
            )
        )

        student_submissions = {
            submission.assignment_id: submission
            for submission in student.assignment_submissions.select_related(
                "assignment"
            )
        }

        assignment_items = [
            {
                "assignment": assignment,
                "submission": student_submissions.get(assignment.id),
            }
            for assignment in assignments
        ]


    unread_notification_count = Notification.objects.filter(
        recipient=request.user,
        is_read=False,
    ).count()

    cafeteria_reservation = (
        student.cafeteria_reservations
        .select_related("week")
        .order_by("-created_at")
        .first()
    )

    report_cards = StudentReportCard.objects.filter(
        student=student,
        is_active=True,
    ).order_by("-created_at")


    announcements = Announcement.objects.filter(
        is_active=True,
        publish_at__lte=timezone.now(),
    ).filter(
        Q(audience=Announcement.Audience.ALL)
        | Q(audience=Announcement.Audience.STUDENTS)
        | Q(
            audience=Announcement.Audience.CLASSROOM,
            classroom=enrollment.classroom if enrollment else None,
        )
    ).order_by("-publish_at")

    return render(
        request,
        "accounts/student_dashboard.html",
        {
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
        }
    )


@login_required
def manager_dashboard(request):

    if not (
        request.user.is_superuser
        or request.user.role in [
            Role.SUPER_ADMIN,
            Role.SCHOOL_MANAGER,
        ]
    ):
        return HttpResponseForbidden(
            "شما اجازه دسترسی به این صفحه را ندارید."
        )
    
    unread_notification_count = Notification.objects.filter(
        recipient=request.user,
        is_read=False,
    ).count()

    context = {
        "student_count": User.objects.filter(
            role=Role.STUDENT,
            is_active=True,
        ).count(),

        "teacher_count": User.objects.filter(
            role=Role.TEACHER,
            is_active=True,
        ).count(),

        "classroom_count": Classroom.objects.count(),

        "material_count": EducationalMaterial.objects.count(),

        "assignment_count": Assignment.objects.count(),

        "conversation_count": Conversation.objects.count(),

        "unread_notification_count": unread_notification_count,
    }


    return render(
        request,
        "accounts/manager_dashboard.html",
        context,
    )


@login_required
def delete_material(request, material_id):

    teacher = request.user.teacher_profile

    material = get_object_or_404(
        EducationalMaterial,
        id=material_id,
        teacher=teacher,
    )

    classroom = material.classrooms.filter(
        teacher_assignments__teacher=teacher,
    ).first()

    if classroom is None:
        return HttpResponseForbidden(
            "شما اجازه حذف این مطلب را ندارید."
        )

    if request.method == "POST":

        classroom_id = classroom.id

        material.delete()

        return redirect(
            "teacher_class_detail",
            classroom_id=classroom_id,
        )

    return render(
        request,
        "accounts/delete_material.html",
        {
            "material": material,
            "classroom": classroom,
        },
    )