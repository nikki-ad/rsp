from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404
from accounts.permissions import is_school_admin, is_language_teacher
from core.uploads import attachment_response


def download_feedback(request, model, submission_id, language=False):
    filters = {}
    if not is_school_admin(request.user):
        filters["assignment__group__academic_year__status" if language else
                "assignment__classroom__academic_year__status"] = "active"
        student = getattr(request.user, "student_profile", None)
        teacher = getattr(request.user, "teacher_profile", None)
        if student:
            filters["student"] = student
            if language:
                filters.update(assignment__group__students=student, assignment__group__is_active=True)
            else:
                filters.update(assignment__classroom__enrollments__student=student,
                               assignment__classroom__enrollments__is_active=True)
        elif teacher:
            if not language and is_language_teacher(request.user):
                raise PermissionDenied()
            filters["assignment__teacher"] = teacher
            if language:
                filters.update(assignment__group__teachers=teacher, assignment__group__is_active=True)
        else:
            raise PermissionDenied()
    submission = get_object_or_404(model, pk=submission_id, **filters)
    return attachment_response(submission.feedback_file)
