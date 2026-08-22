from django.urls import path
from . import views

urlpatterns = [
    path("", views.student_language_dashboard, name="student_language_dashboard"),
    path("teacher/", views.teacher_language_dashboard, name="teacher_language_dashboard"),
    path("teacher/groups/<uuid:group_id>/", views.language_group_detail, name="language_group_detail"),
    path("teacher/groups/<uuid:group_id>/materials/create/", views.create_language_material,
         name="create_language_material"),
    path("teacher/groups/<uuid:group_id>/assignments/create/", views.create_language_assignment,
         name="create_language_assignment"),
    path("assignments/<uuid:assignment_id>/submit/", views.submit_language_assignment,
         name="submit_language_assignment"),
    path("manage/", views.manage_language_groups, name="manage_language_groups"),
    path("manage/create/", views.language_group_form, name="language_group_create"),
    path("manage/<uuid:group_id>/edit/", views.language_group_form, name="language_group_edit"),
    path("manage/<uuid:group_id>/delete/", views.language_group_delete, name="language_group_delete"),
]
