from functools import wraps

from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.http import HttpResponseForbidden

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


def is_language_teacher(user):
    teacher = getattr(user, "teacher_profile", None)
    return bool(teacher and teacher.is_language_teacher and not is_school_admin(user))


def school_teacher_only(view_func):
    """Block school classroom endpoints even when old assignments still exist."""
    @wraps(view_func)
    def wrapped(request, *args, **kwargs):
        if is_language_teacher(request.user):
            return HttpResponseForbidden("این حساب فقط به گروه‌های واحد زبان دسترسی دارد.")
        return view_func(request, *args, **kwargs)
    return wrapped


def language_teacher_redirect(target):
    def decorator(view_func):
        @wraps(view_func)
        def wrapped(request, *args, **kwargs):
            if is_language_teacher(request.user):
                if request.method != "GET":
                    return HttpResponseForbidden("برای ثبت محتوا، گروه زبان خود را انتخاب کنید.")
                return redirect(target)
            return view_func(request, *args, **kwargs)
        return wrapped
    return decorator


def post_login_redirect_name(user):
    if is_school_admin(user):
        return "admin_dashboard"

    if user.role == Role.FINANCE:
        return "cafeteria_pending_receipts"

    if is_language_teacher(user):
        return "teacher_language_dashboard"

    if hasattr(user, "teacher_profile"):
        return "teacher_dashboard"

    if hasattr(user, "student_profile"):
        return "student_dashboard"

    return "profile"
