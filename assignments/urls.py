from django.urls import path

from . import views


urlpatterns = [
    path(
        "create/<uuid:classroom_id>/",
        views.create_assignment,
        name="create_assignment",
    ),

    path(
        "submit/<uuid:assignment_id>/",
        views.submit_assignment,
        name="submit_assignment",
    ),

    path(
        "submissions/<uuid:assignment_id>/",
        views.assignment_submissions,
        name="assignment_submissions",
    ),


    path(
        "submission/<uuid:submission_id>/evaluate/",
        views.evaluate_submission,
        name="evaluate_submission",
    ),


    path(
        "assignment/<uuid:assignment_id>/delete/",
        views.delete_assignment,
        name="delete_assignment",
    ),

    path(
        "<uuid:assignment_id>/download/",
        views.download_assignment_file,
        name="download_assignment_file",
    ),


    path(
        "submission/<uuid:submission_id>/download/",
        views.download_submission_file,
        name="download_submission_file",
    ),




]