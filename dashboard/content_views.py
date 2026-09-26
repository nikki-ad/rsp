from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, render

from accounts.permissions import manager_required
from academic.models import Classroom


@manager_required
def content_classrooms(request, kind):
    return render(request, "dashboard/content_classrooms.html", {
        "kind": kind,
        "title": "مطالب آموزشی" if kind == "materials" else "تکالیف آموزشی",
        "detail_route": "manager_class_materials" if kind == "materials" else "manager_class_assignments",
        "classrooms": Classroom.objects.select_related("grade", "academic_year").order_by(
            "-academic_year__created_at", "grade__order", "name"
        ),
    })


@manager_required
def classroom_content(request, classroom_id, kind):
    classroom = get_object_or_404(
        Classroom.objects.select_related("grade", "academic_year"), pk=classroom_id
    )
    items = classroom.materials.all() if kind == "materials" else classroom.assignments.all()
    items = items.select_related("teacher__user").order_by("-created_at", "-pk")
    return render(request, "dashboard/classroom_content.html", {
        "classroom": classroom,
        "kind": kind,
        "title": "مطالب آموزشی" if kind == "materials" else "تکالیف آموزشی",
        "back_route": "manager_material_classrooms" if kind == "materials" else "manager_assignment_classrooms",
        "page_obj": Paginator(items, 30).get_page(request.GET.get("page")),
    })
