from functools import wraps

from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from .choices import Role


def is_school_admin(user) -> bool:
    return bool(
        getattr(user, "is_authenticated", False)
        and (
            user.is_superuser
            or getattr(user, "role", None) in (
                Role.SUPER_ADMIN,
                Role.SCHOOL_MANAGER,
            )
        )
    )


def manager_required(view_func):
    @login_required
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not is_school_admin(request.user):
            return render(
                request,
                "dashboard/access_denied.html",
                status=403,
            )
        return view_func(request, *args, **kwargs)

    return _wrapped


def post_login_redirect_name(user):
    if is_school_admin(user):
        return "admin_dashboard"

    if user.role == Role.FINANCE:
        return "cafeteria_pending_receipts"

    if hasattr(user, "teacher_profile"):
        return "teacher_dashboard"

    if hasattr(user, "student_profile"):
        return "student_dashboard"

    return "profile"
