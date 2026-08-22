from django.contrib.auth.views import LogoutView
from django.urls import path

from . import views

urlpatterns = [
    path("login/", views.user_login, name="user_login"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("profile/", views.profile, name="profile"),
    path("load-classrooms/", views.load_classrooms, name="load_classrooms"),
    path("teacher/dashboard/", views.teacher_dashboard, name="teacher_dashboard"),
    path(
        "teacher/class/<uuid:classroom_id>/",
        views.teacher_class_detail,
        name="teacher_class_detail",
    ),
    path(
        "teacher/class/<uuid:classroom_id>/material/create/",
        views.create_material,
        name="create_class_material",
    ),
    path("student/dashboard/", views.student_dashboard, name="student_dashboard"),
    path("manager/dashboard/", views.manager_dashboard, name="manager_dashboard"),
    path(
        "material/<uuid:material_id>/delete/",
        views.delete_material,
        name="delete_material",
    ),
]
