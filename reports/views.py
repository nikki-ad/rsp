from django.contrib.auth.decorators import login_required
from django.http import FileResponse
from django.shortcuts import get_object_or_404

from .models import StudentReportCard


@login_required
def download_report_card(request, report_card_id):

    report_card = get_object_or_404(
        StudentReportCard,
        id=report_card_id,
        is_active=True,
        student__user=request.user,
    )

    return FileResponse(
        report_card.file.open("rb"),
        as_attachment=True,
        filename=report_card.file.name.split("/")[-1],
    )