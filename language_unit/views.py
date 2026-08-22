from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from accounts.permissions import is_school_admin
from activitylog.utils import log_activity
from notifications import constants as notification_constants
from notifications.services import create_notification
from .forms import (
    LanguageAssignmentForm, LanguageGroupForm, LanguageMaterialForm, LanguageSubmissionForm,
)
from .models import LanguageAssignment, LanguageAssignmentSubmission, LanguageGroup


def _language_teacher(request):
    return getattr(request.user, "teacher_profile", None)


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
    group = get_object_or_404(LanguageGroup, id=group_id, teachers=teacher, is_active=True)
    query = (request.GET.get("q") or "").strip()
    students = group.students.select_related("user")
    if query:
        students = students.filter(
            Q(user__first_name__icontains=query) | Q(user__last_name__icontains=query)
        )
    return render(request, "language_unit/group_detail.html", {
        "group": group, "students": students, "query": query,
        "materials": group.materials.filter(teacher=teacher),
        "assignments": group.assignments.filter(teacher=teacher),
    })


@login_required
def create_language_material(request, group_id):
    teacher = _language_teacher(request)
    group = get_object_or_404(LanguageGroup, id=group_id, teachers=teacher, is_active=True)
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
        messages.success(request, "مطلب واحد زبان منتشر شد.")
        return redirect("language_group_detail", group_id=group.id)
    return render(request, "dashboard/form.html", {
        "form": form, "page_title": "مطلب جدید واحد زبان",
        "back_url": reverse("language_group_detail", args=[group.id]),
    })


@login_required
def create_language_assignment(request, group_id):
    teacher = _language_teacher(request)
    group = get_object_or_404(LanguageGroup, id=group_id, teachers=teacher, is_active=True)
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
        messages.success(request, "تکلیف واحد زبان منتشر شد.")
        return redirect("language_group_detail", group_id=group.id)
    return render(request, "dashboard/form.html", {
        "form": form, "page_title": "تکلیف جدید واحد زبان",
        "back_url": reverse("language_group_detail", args=[group.id]),
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
    return render(request, "dashboard/form.html", {
        "form": form, "wide": True,
        "page_title": "ویرایش گروه زبان" if instance else "گروه زبان جدید",
        "page_subtitle": "معلمان و دانش‌آموزان این گروه را انتخاب کنید.",
        "back_url": reverse("manage_language_groups"),
    })


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
