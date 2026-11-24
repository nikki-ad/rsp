from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Exists, OuterRef
from django.views.decorators.cache import never_cache
from django.http import FileResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, render

from .models import StudentReportCard
from academic.models import Enrollment
from accounts.permissions import is_operator, is_school_admin


def supervised_cards(user):
    enrollments = Enrollment.objects.filter(
        student_id=OuterRef("student_id"),
        academic_year_id=OuterRef("period__academic_year_id"),
        classroom__supervising_operators=user,
        is_active=True,
    )
    return StudentReportCard.objects.filter(Exists(enrollments), is_active=True)


@login_required
@never_cache
def operator_report_cards(request):
    if not is_operator(request.user):
        return HttpResponseForbidden()
    cards = supervised_cards(request.user).select_related("period", "student__user")
    return render(request, "reports/operator_report_cards.html", {
        "page": Paginator(cards, 30).get_page(request.GET.get("page")),
    })


@login_required
@never_cache
def download_report_card(request, report_card_id):

    cards = StudentReportCard.objects.all()
    if is_operator(request.user):
        cards = supervised_cards(request.user)
    elif not is_school_admin(request.user):
        cards = cards.filter(is_active=True, student__user=request.user)
    report_card = get_object_or_404(cards, id=report_card_id)

    return FileResponse(
        report_card.file.open("rb"),
        as_attachment=True,
        filename=report_card.file.name.split("/")[-1],
    )

@login_required
def student_report_cards(request):
    if request.user.role != "student" or not hasattr(request.user, "student_profile"):
        return HttpResponseForbidden("شما اجازه مشاهده این صفحه را ندارید.")
    cards = StudentReportCard.objects.filter(
        student=request.user.student_profile, is_active=True,
    ).select_related("period").order_by("-period__created_at", "-created_at")
    return render(request, "reports/student_report_cards.html", {"report_cards": cards})
