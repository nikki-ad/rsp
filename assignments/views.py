from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from academic.models import Classroom
from .models import Assignment, AssignmentSubmission
from .forms import (
    AssignmentCreateForm,
    AssignmentSubmissionForm,
    AssignmentEvaluationForm,
)
from django.urls import reverse
from activitylog.utils import log_activity
from notifications import constants as notification_constants
from notifications.services import create_notification


@login_required
def create_assignment(request, classroom_id):

    teacher = request.user.teacher_profile

    classroom = get_object_or_404(
        Classroom,
        id=classroom_id,
        teacher_assignments__teacher=teacher,
    )

    if request.method == "POST":

        form = AssignmentCreateForm(
            request.POST,
            request.FILES,
        )

        if form.is_valid():

            assignment = form.save(commit=False)

            assignment.teacher = teacher
            assignment.classroom = classroom

            assignment.save()

            log_activity(
                request,
                action="assignment_created",
                description=(
                    f"تکلیف «{assignment.title}» "
                    f"برای کلاس {classroom} توسط معلم ایجاد شد."
                ),
            )

            active_enrollments = classroom.enrollments.filter(
                is_active=True,
            ).select_related(
                "student__user",
            )

            for enrollment in active_enrollments:
                create_notification(
                    recipient=enrollment.student.user,
                    notification_type=notification_constants.ASSIGNMENT,
                    title=f"تکلیف جدید: {assignment.title}",
                    message=f"یک تکلیف جدید برای کلاس {classroom} ثبت شده است.",
                    url=reverse("student_dashboard"),
                )

            return redirect(
                "teacher_class_detail",
                classroom_id=classroom.id,
            )

    else:

        form = AssignmentCreateForm()

    return render(
        request,
        "assignments/create_assignment.html",
        {
            "form": form,
            "classroom": classroom,
        }
    )

@login_required
def submit_assignment(request, assignment_id):

    student = request.user.student_profile

    assignment = get_object_or_404(
        Assignment,
        id=assignment_id,
        classroom__enrollments__student=student,
        classroom__enrollments__is_active=True,
    )


    submission = AssignmentSubmission.objects.filter(
        assignment=assignment,
        student=student,
    ).first()


    if request.method == "POST":

        form = AssignmentSubmissionForm(
            request.POST,
            request.FILES,
            instance=submission,
        )

        if form.is_valid():

            if submission is None:
                submission = form.save(commit=False)
                submission.assignment = assignment
                submission.student = student
                submission.save()
            else:
                form.save()

            log_activity(
                request,
                action="assignment_submission",
                description=(
                    f"پاسخ تکلیف «{assignment.title}» "
                    f"توسط {student.user.get_full_name()} ثبت یا ویرایش شد."
                ),
            )

            teacher_user = assignment.teacher.user

            create_notification(
                recipient=teacher_user,
                notification_type=notification_constants.ASSIGNMENT,
                title="پاسخ جدید برای تکلیف",
                message=f"{student.user.get_full_name()} پاسخ تکلیف «{assignment.title}» را ارسال کرد.",
                url=reverse(
                    "assignment_submissions",
                    args=[assignment.id],
                ),
            )

            return redirect(
                "student_dashboard"
            )

    else:

        form = AssignmentSubmissionForm(
            instance=submission
        )


    return render(
        request,
        "assignments/submit_assignment.html",
        {
            "assignment": assignment,
            "form": form,
        }
    )


@login_required
def assignment_submissions(request, assignment_id):

    teacher = request.user.teacher_profile

    assignment = get_object_or_404(
        Assignment,
        id=assignment_id,
        teacher=teacher,
    )

    submissions = assignment.submissions.all()

    return render(
        request,
        "assignments/submissions.html",
        {
            "assignment": assignment,
            "submissions": submissions,
        }
    )


@login_required
def evaluate_submission(request, submission_id):

    teacher = request.user.teacher_profile

    submission = get_object_or_404(
        AssignmentSubmission,
        id=submission_id,
        assignment__teacher=teacher,
    )

    if request.method == "POST":

        form = AssignmentEvaluationForm(
            request.POST,
            instance=submission,
        )

        if form.is_valid():

            form.save()

            log_activity(
                request,
                action="assignment_evaluation",
                description=(
                    f"تکلیف «{submission.assignment.title}» "
                    f"برای {submission.student.user.get_full_name()} "
                    f"توسط معلم ارزیابی شد."
                ),
            )

            student_user = submission.student.user
            create_notification(
                recipient=student_user,
                notification_type=notification_constants.ASSIGNMENT,
                title="تکلیف شما ارزیابی شد",
                message=(
                    f"ارزیابی تکلیف «{submission.assignment.title}» "
                    f"ثبت شد: {submission.get_evaluation_display()}"
                ),
                url=reverse("student_dashboard"),
            )

            return redirect(
                "assignment_submissions",
                assignment_id=submission.assignment.id,
            )

    else:

        form = AssignmentEvaluationForm(
            instance=submission,
        )

    return render(
        request,
        "assignments/evaluate_submission.html",
        {
            "submission": submission,
            "form": form,
        },
    )

@login_required
def delete_assignment(request, assignment_id):

    teacher = request.user.teacher_profile

    assignment = get_object_or_404(
        Assignment,
        id=assignment_id,
        teacher=teacher,
    )

    if request.method == "POST":
        classroom_id = assignment.classroom.id
        assignment_title = assignment.title

        assignment.delete()

        log_activity(
            request,
            action="assignment_deleted",
            description=(
                f"تکلیف «{assignment_title}» "
                f"توسط معلم حذف شد."
            ),
        )

        return redirect(
            "teacher_class_detail",
            classroom_id=classroom_id,
        )

    return render(
        request,
        "assignments/delete_assignment.html",
        {
            "assignment": assignment,
        },
    )