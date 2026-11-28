from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, render

from accounts.permissions import is_operator, supervisor_required
from academic.models import Classroom


def visible_classrooms(user):
    rooms = Classroom.objects.select_related("grade", "academic_year")
    return rooms.filter(supervising_operators=user) if is_operator(user) else rooms


@supervisor_required
def content_classrooms(request, kind):
    return render(request, "dashboard/content_classrooms.html", {
        "kind": kind,
        "title": "مطالب آموزشی" if kind == "materials" else "تکالیف آموزشی",
        "detail_route": "manager_class_materials" if kind == "materials" else "manager_class_assignments",
        "classrooms": visible_classrooms(request.user).order_by(
            "-academic_year__created_at", "grade__order", "name"
        ),
    })


@supervisor_required
def classroom_content(request, classroom_id, kind):
    classroom = get_object_or_404(
        visible_classrooms(request.user), pk=classroom_id
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
