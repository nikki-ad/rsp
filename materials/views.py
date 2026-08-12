from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from .forms import EducationalMaterialCreateForm
from django.urls import reverse

from notifications import constants as notification_constants
from notifications.services import create_notification

@login_required
def create_material(request):

    teacher = request.user.teacher_profile

    if request.method == "POST":
        form = EducationalMaterialCreateForm(
            request.POST,
            request.FILES,
            teacher=teacher,
        )

        if form.is_valid():
            material = form.save(commit=False)
            material.teacher = teacher
            material.save()
            form.save_m2m()
            for classroom in material.classrooms.all():

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
                    print("اعلان مطلب برای:", enrollment.student.user.username)

            return redirect("teacher_dashboard")

    else:
        form = EducationalMaterialCreateForm(
            teacher=teacher,
        )

    return render(
        request,
        "materials/create_material.html",
        {
            "form": form,
        },
    )