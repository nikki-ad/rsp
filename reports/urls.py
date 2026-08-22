from django.urls import path

from . import views


urlpatterns = [
    path(
        "<uuid:report_card_id>/download/",
        views.download_report_card,
        name="download_report_card",
    ),
]