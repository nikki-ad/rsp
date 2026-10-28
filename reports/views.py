from django.contrib.auth.decorators import login_required
from django.http import FileResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, render

from .models import StudentReportCard
from accounts.permissions import is_school_admin


@login_required
def download_report_card(request, report_card_id):

    cards = StudentReportCard.objects.all()
    if not is_school_admin(request.user):
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
