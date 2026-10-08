from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, render
from django.urls import reverse

from accounts.permissions import is_school_admin
from academic.models import AcademicYear
from .models import LanguageGroup, LanguageMaterial, LanguageAssignment


def active_teacher_groups(user):
    teacher = getattr(user, "teacher_profile", None)
    if teacher is None:
        return LanguageGroup.objects.none()
    return LanguageGroup.objects.filter(teachers=teacher, is_active=True,
        academic_year__status=AcademicYear.Status.ACTIVE)


@login_required
def teacher_language_content(request, kind):
    teacher = getattr(request.user, "teacher_profile", None)
    if teacher is None:
        return HttpResponseForbidden()
    groups = active_teacher_groups(request.user)
    model = LanguageMaterial if kind == "materials" else LanguageAssignment
    items = model.objects.filter(group__in=groups, teacher=teacher).select_related("group", "teacher__user").order_by("-created_at", "-id")
    return render(request, "language_unit/content_list.html", {
        "groups": groups, "items": items, "kind": kind,
        "page_title": "مطالب زبان" if kind == "materials" else "تکالیف زبان",
    })


@login_required
def manager_language_group_content(request, group_id):
    if not is_school_admin(request.user):
        return HttpResponseForbidden()
    group = get_object_or_404(LanguageGroup.objects.select_related("academic_year"), pk=group_id)
    return render(request, "language_unit/group_detail.html", {
        "group": group, "students": group.students.select_related("user"), "manager_view": True,
    })


@login_required
def language_group_content(request, group_id, kind):
    manager_view = is_school_admin(request.user)
    if manager_view:
        group = get_object_or_404(LanguageGroup.objects.select_related("academic_year"), pk=group_id)
        back_url = reverse("manager_language_group_content", args=[group.id])
    else:
        teacher = getattr(request.user, "teacher_profile", None)
        if teacher is None:
            return HttpResponseForbidden()
        group = get_object_or_404(active_teacher_groups(request.user), pk=group_id)
        back_url = reverse("language_group_detail", args=[group.id])
    model = LanguageMaterial if kind == "materials" else LanguageAssignment
    items = model.objects.filter(group=group)
    if not manager_view:
        items = items.filter(teacher=teacher)
    items = items.select_related("group", "teacher__user").order_by("-created_at", "-id")
    return render(request, "language_unit/content_list.html", {
        "group": group, "groups": [group], "items": items, "kind": kind,
        "manager_view": manager_view, "back_url": back_url,
        "page_title": ("همهٔ مطالب" if kind == "materials" else "همهٔ تکالیف") + " — " + group.title,
    })
