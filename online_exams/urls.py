from django.urls import path
from . import views

urlpatterns = [
    path("", views.index, name="exam_list"),
    path("create/", views.create, name="exam_create"),
    path("preview/", views.preview, name="exam_preview"),
    path("<uuid:pk>/", views.detail, name="exam_detail"),
    path("<uuid:pk>/edit/", views.create, name="exam_edit"),
    path("<uuid:pk>/questions/", views.questions, name="exam_questions"),
    path("<uuid:pk>/key/", views.key, name="exam_key"),
    path("<uuid:pk>/publish/", views.publish, name="exam_publish"),
    path("<uuid:pk>/take/", views.take, name="exam_take"),
    path("<uuid:pk>/answer/", views.answer, name="exam_answer"),
    path("<uuid:pk>/submit/", views.submit, name="exam_submit"),
    path("<uuid:pk>/result/", views.result, name="exam_result"),
    path("<uuid:pk>/pdf/", views.pdf, name="exam_pdf"),
    path("<uuid:pk>/reports/<uuid:participant_id>/", views.report, name="exam_report"),
    path("<uuid:pk>/reports/", views.reports_zip, name="exam_reports_zip"),
    path("<uuid:pk>/delete-results/", views.delete_results, name="exam_delete_results"),
]
