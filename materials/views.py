from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from .models import EducationalMaterial
from .forms import EducationalMaterialCreateForm
from django.urls import reverse

from notifications import constants as notification_constants
from notifications.services import create_notification
from django.http import HttpResponseForbidden , FileResponse
from academic.models import AcademicYear



@login_required
def create_material(request):


    if not hasattr(request.user, "teacher_profile"):
        return HttpResponseForbidden(
            "شما اجازه ایجاد مطلب آموزشی را ندارید."
        )

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


@login_required
def download_material(request, material_id):

    if not hasattr(request.user, "student_profile"):
        return HttpResponseForbidden(
            "شما اجازه دریافت این فایل را ندارید."
        )

    student = request.user.student_profile

    material = get_object_or_404(
        EducationalMaterial,
        id=material_id,
        content_type="file",
        classrooms__academic_year__status=AcademicYear.Status.ACTIVE,
        classrooms__enrollments__student=student,
        classrooms__enrollments__is_active=True,
    )

    if not material.file:
        return HttpResponseForbidden(
            "فایلی برای این مطلب وجود ندارد."
        )

    return FileResponse(
        material.file.open("rb"),
        as_attachment=True,
        filename=material.file.name.split("/")[-1],
    )