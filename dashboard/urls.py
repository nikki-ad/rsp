from django.urls import path

from . import views


urlpatterns = [
    path(
        "",
        views.admin_dashboard,
        name="admin_dashboard",
    ),

    path(
        "archive/<uuid:year_id>/",
        views.academic_year_archive,
        name="academic_year_archive",
    ),



]