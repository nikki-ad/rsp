from core.upload_progress import render_upload_form, upload_success
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import HttpResponseForbidden
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from uuid import UUID

from accounts.permissions import is_school_admin
from activitylog.utils import log_activity
from notifications import constants as notification_constants
from notifications.services import create_notification
from .forms import (
    LanguageAssignmentForm, LanguageGroupForm, LanguageMaterialForm, LanguageSubmissionForm,
)
from .models import LanguageAssignment, LanguageAssignmentSubmission, LanguageGroup, LanguageMaterial
from accounts.models import StudentProfile
from academic.models import AcademicYear


def _language_teacher(request):
    return getattr(request.user, "teacher_profile", None)


def _teacher_group_or_404(teacher, group_id):
    if teacher is None:
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied()
    return get_object_or_404(LanguageGroup, id=group_id, teachers=teacher,
        is_active=True, academic_year__status=AcademicYear.Status.ACTIVE)


@login_required
def student_language_dashboard(request):
    student = getattr(request.user, "student_profile", None)
    if not student:
        return HttpResponseForbidden("این بخش مخصوص دانش‌آموزان است.")
    groups = LanguageGroup.objects.filter(
        students=student, is_active=True, academic_year__status="active"
    ).prefetch_related("teachers__user", "materials", "assignments")
    materials = []
    assignments = []
    for group in groups:
        materials.extend(group.materials.all())
        assignments.extend(group.assignments.all())
    submissions = {
        item.assignment_id: item
        for item in student.language_submissions.filter(assignment__in=assignments)
    }
    assignment_items = [
        {"assignment": item, "submission": submissions.get(item.id)} for item in assignments
    ]
    language_teachers = []
    seen = set()
    for group in groups:
        for teacher in group.teachers.all():
            if teacher.id not in seen:
                seen.add(teacher.id)
                language_teachers.append(teacher)
    return render(request, "language_unit/student_dashboard.html", {
        "groups": groups, "materials": materials, "assignment_items": assignment_items,
        "language_teachers": language_teachers,
    })


@login_required
def teacher_language_dashboard(request):
    teacher = _language_teacher(request)
    if not teacher:
        return HttpResponseForbidden("این بخش مخصوص معلمان است.")
    groups = LanguageGroup.objects.filter(
        teachers=teacher, is_active=True, academic_year__status="active"
    ).prefetch_related("students__user")
    return render(request, "language_unit/teacher_dashboard.html", {"groups": groups})


@login_required
def language_group_detail(request, group_id):
    teacher = _language_teacher(request)
    group = _teacher_group_or_404(teacher, group_id)
    query = (request.GET.get("q") or "").strip()
    students = group.students.select_related("user")
    if query:
        students = students.filter(
            Q(user__first_name__icontains=query) | Q(user__last_name__icontains=query)
        )
    return render(request, "language_unit/group_detail.html", {
        "group": group, "students": students, "query": query,
    })


@login_required
def create_language_material(request, group_id):
    teacher = _language_teacher(request)
    group = _teacher_group_or_404(teacher, group_id)
    form = LanguageMaterialForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        item = form.save(commit=False)
        item.group, item.teacher, item.created_by = group, teacher, request.user
        item.save()
        for student in group.students.select_related("user"):
            create_notification(recipient=student.user,
                                notification_type=notification_constants.MATERIAL,
                                title=f"مطلب جدید واحد زبان: {item.title}",
                                message=f"در گروه {group.title} مطلب جدیدی منتشر شد.",
                                url=reverse("student_language_dashboard"))
        return upload_success(request, "language_group_detail", group_id=group.id)
    return render_upload_form(request, "dashboard/form.html", {
        "form": form, "page_title": "مطلب جدید واحد زبان",
        "back_url": reverse("language_group_detail", args=[group.id]),
    })


@login_required
def edit_language_material(request, material_id):
    teacher = _language_teacher(request)
    item = get_object_or_404(
        LanguageMaterial, id=material_id, teacher=teacher,
        group__teachers=teacher, group__is_active=True,
        group__academic_year__status=AcademicYear.Status.ACTIVE,
    )
    form = LanguageMaterialForm(
        request.POST if request.method == "POST" else None,
        request.FILES or None, instance=item,
    )
    if request.method == "POST" and form.is_valid():
        form.save()
        log_activity(request, action="language_material_updated",
                     description=f"مطلب زبان «{item.title}» ویرایش شد.")
        return upload_success(request, "language_group_detail", group_id=item.group_id)
    return render_upload_form(request, "dashboard/form.html", {
        "form": form, "page_title": "ویرایش مطلب واحد زبان",
        "back_url": reverse("language_group_detail", args=[item.group_id]),
    })


@login_required
def create_language_assignment(request, group_id):
    teacher = _language_teacher(request)
    group = _teacher_group_or_404(teacher, group_id)
    form = LanguageAssignmentForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        item = form.save(commit=False)
        item.group, item.teacher, item.created_by = group, teacher, request.user
        item.save()
        for student in group.students.select_related("user"):
            create_notification(recipient=student.user,
                                notification_type=notification_constants.ASSIGNMENT,
                                title=f"تکلیف جدید واحد زبان: {item.title}",
                                message=f"در گروه {group.title} تکلیف جدیدی ثبت شد.",
                                url=reverse("student_language_dashboard"))
        return upload_success(request, "language_group_detail", group_id=group.id)
    return render_upload_form(request, "dashboard/form.html", {
        "form": form, "page_title": "تکلیف جدید واحد زبان",
        "back_url": reverse("language_group_detail", args=[group.id]),
    })


@login_required
def edit_language_assignment(request, assignment_id):
    teacher = _language_teacher(request)
    item = get_object_or_404(
        LanguageAssignment, id=assignment_id, teacher=teacher,
        group__teachers=teacher, group__is_active=True,
        group__academic_year__status=AcademicYear.Status.ACTIVE,
    )
    form = LanguageAssignmentForm(
        request.POST if request.method == "POST" else None,
        request.FILES or None, instance=item,
    )
    if request.method == "POST" and form.is_valid():
        form.save()
        log_activity(request, action="language_assignment_updated",
                     description=f"تکلیف زبان «{item.title}» ویرایش شد.")
        return upload_success(request, "language_group_detail", group_id=item.group_id)
    return render_upload_form(request, "dashboard/form.html", {
        "form": form, "page_title": "ویرایش تکلیف واحد زبان",
        "back_url": reverse("language_group_detail", args=[item.group_id]),
    })


@login_required
def submit_language_assignment(request, assignment_id):
    student = getattr(request.user, "student_profile", None)
    assignment = get_object_or_404(
        LanguageAssignment, id=assignment_id, group__students=student,
        group__is_active=True, group__academic_year__status="active",
    )
    submission = LanguageAssignmentSubmission.objects.filter(
        assignment=assignment, student=student
    ).first()
    form = LanguageSubmissionForm(request.POST or None, request.FILES or None, instance=submission)
    if request.method == "POST" and form.is_valid():
        item = form.save(commit=False)
        item.assignment, item.student, item.created_by = assignment, student, request.user
        item.save()
        create_notification(recipient=assignment.teacher.user,
                            notification_type=notification_constants.ASSIGNMENT,
                            title="پاسخ جدید تکلیف زبان",
                            message=f"{student} پاسخ «{assignment.title}» را ارسال کرد.",
                            url=reverse("language_group_detail", args=[assignment.group_id]))
        messages.success(request, "پاسخ تکلیف زبان ذخیره شد.")
        return redirect("student_language_dashboard")
    return render(request, "dashboard/form.html", {
        "form": form, "page_title": assignment.title,
        "page_subtitle": assignment.description,
        "back_url": reverse("student_language_dashboard"),
    })


@login_required
def manage_language_groups(request):
    if not is_school_admin(request.user):
        return HttpResponseForbidden("دسترسی مدیریت لازم است.")
    query = (request.GET.get("q") or "").strip()
    groups = LanguageGroup.objects.select_related("academic_year").prefetch_related(
        "teachers__user", "students__user"
    )
    if query:
        groups = groups.filter(
            Q(title__icontains=query) | Q(students__user__first_name__icontains=query)
            | Q(students__user__last_name__icontains=query)
        ).distinct()
    return render(request, "language_unit/manage_groups.html", {"groups": groups, "query": query})


@login_required
def language_group_form(request, group_id=None):
    if not is_school_admin(request.user):
        return HttpResponseForbidden("دسترسی مدیریت لازم است.")
    instance = get_object_or_404(LanguageGroup, id=group_id) if group_id else None
    form = LanguageGroupForm(request.POST or None, instance=instance)
    if request.method == "POST" and form.is_valid():
        group = form.save(commit=False)
        if not group.pk:
            group.created_by = request.user
        group.save()
        form.save_m2m()
        log_activity(request, action="language_group_saved",
                     description=f"گروه زبان «{group.title}» ذخیره شد.")
        messages.success(request, "گروه زبان ذخیره شد.")
        return redirect("manage_language_groups")
    return render(request, "language_unit/group_form.html", {
        "form": form, "wide": True,
        "page_title": "ویرایش گروه زبان" if instance else "گروه زبان جدید",
        "page_subtitle": "معلمان و دانش‌آموزان این گروه را انتخاب کنید.",
        "back_url": reverse("manage_language_groups"),
    })


@login_required
def search_language_students(request):
    if not is_school_admin(request.user):
        return HttpResponseForbidden("دسترسی مدیریت لازم است.")
    year_id = request.GET.get("academic_year")
    query = (request.GET.get("q") or "").strip()
    if not year_id or not query:
        return JsonResponse({"students": []})
    try:
        UUID(year_id)
    except (ValueError, TypeError):
        return JsonResponse({"students": []})
    if not AcademicYear.objects.filter(pk=year_id).exists():
        return JsonResponse({"students": []})
    students = StudentProfile.objects.filter(
        enrollments__academic_year_id=year_id, enrollments__is_active=True
    ).select_related("user")
    for word in query.split():
        students = students.filter(
            Q(user__first_name__icontains=word) |
            Q(user__last_name__icontains=word) |
            Q(user__username__icontains=word)
        )
    results = [{"id": str(student.pk), "name": str(student)}
               for student in students.distinct().order_by(
                   "user__last_name", "user__first_name"
               )[:20]]
    return JsonResponse({"students": results})


@login_required
def language_group_delete(request, group_id):
    if not is_school_admin(request.user):
        return HttpResponseForbidden("دسترسی مدیریت لازم است.")
    group = get_object_or_404(LanguageGroup, id=group_id)
    if request.method == "POST":
        group.delete()
        messages.success(request, "گروه زبان حذف شد.")
        return redirect("manage_language_groups")
    return render(request, "dashboard/confirm_delete.html", {
        "object_label": f"گروه زبان {group.title}",
        "back_url": reverse("manage_language_groups"),
    })


def _language_content_for_download(request, model, item_id):
    if is_school_admin(request.user):
        return get_object_or_404(model, pk=item_id)
    student = getattr(request.user, "student_profile", None)
    teacher = _language_teacher(request)
    filters = {"group__is_active": True, "group__academic_year__status": AcademicYear.Status.ACTIVE}
    if student:
        filters["group__students"] = student
    elif teacher:
        filters.update(teacher=teacher, group__teachers=teacher)
    else:
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied()
    return get_object_or_404(model, pk=item_id, **filters)


@login_required
def download_language_material(request, material_id):
    from core.uploads import attachment_response
    item = _language_content_for_download(request, LanguageMaterial, material_id)
    return attachment_response(item.file)


@login_required
def download_language_assignment(request, assignment_id, attachment="file"):
    from core.uploads import attachment_response
    from django.http import Http404
    if attachment not in {"file", "image", "video"}:
        raise Http404()
    item = _language_content_for_download(request, LanguageAssignment, assignment_id)
    return attachment_response(getattr(item, attachment))
