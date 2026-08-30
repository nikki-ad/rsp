from django.urls import path

from . import crud
from . import views

urlpatterns = [
    path("", views.admin_dashboard, name="admin_dashboard"),
    path("routine-reports/", views.routine_report_list, name="routine_report_list"),
    path("routine-reports/excel/", views.routine_report_excel, name="routine_report_excel"),
    path("users/", views.user_list, name="user_list"),
    path(
        "archive/<uuid:year_id>/",
        views.academic_year_archive,
        name="academic_year_archive",
    ),
    path("students/", crud.student_list, name="student_list"),
    path("students/create/", crud.create_student, name="create_student"),
    path("students/<uuid:student_id>/edit/", crud.edit_student, name="edit_student"),
    path("teachers/", crud.teacher_list, name="teacher_list"),
    path("teachers/create/", crud.create_teacher, name="create_teacher"),
    path("teachers/<uuid:teacher_id>/edit/", crud.edit_teacher, name="edit_teacher"),
    path("academic-years/", crud.academic_year_list, name="academic_year_list"),
    path("academic-years/create/", crud.academic_year_form, name="academic_year_create"),
    path(
        "academic-years/<uuid:year_id>/edit/",
        crud.academic_year_form,
        name="academic_year_edit",
    ),
    path(
        "academic-years/<uuid:year_id>/delete/",
        crud.academic_year_delete,
        name="academic_year_delete",
    ),
    path("grades/", crud.grade_list, name="grade_list"),
    path("grades/create/", crud.grade_form, name="grade_create"),
    path("grades/<uuid:grade_id>/edit/", crud.grade_form, name="grade_edit"),
    path("grades/<uuid:grade_id>/delete/", crud.grade_delete, name="grade_delete"),
    path("classrooms/", crud.classroom_list, name="classroom_list"),
    path("classrooms/create/", crud.classroom_form, name="classroom_create"),
    path(
        "classrooms/<uuid:classroom_id>/edit/",
        crud.classroom_form,
        name="classroom_edit",
    ),
    path(
        "classrooms/<uuid:classroom_id>/delete/",
        crud.classroom_delete,
        name="classroom_delete",
    ),
    path("enrollments/", crud.enrollment_list, name="enrollment_list"),
    path("enrollments/create/", crud.enrollment_form, name="enrollment_create"),
    path(
        "enrollments/<uuid:enrollment_id>/edit/",
        crud.enrollment_form,
        name="enrollment_edit",
    ),
    path(
        "enrollments/<uuid:enrollment_id>/delete/",
        crud.enrollment_delete,
        name="enrollment_delete",
    ),
    path("announcements/", crud.announcement_list, name="announcement_list"),
    path("announcements/create/", crud.announcement_form, name="announcement_create"),
    path(
        "announcements/<uuid:announcement_id>/edit/",
        crud.announcement_form,
        name="announcement_edit",
    ),
    path(
        "announcements/<uuid:announcement_id>/delete/",
        crud.announcement_delete,
        name="announcement_delete",
    ),
    path("report-cards/", crud.report_card_list, name="report_card_list"),
    path("report-cards/create/", crud.report_card_form, name="report_card_create"),
    path(
        "report-cards/<uuid:report_card_id>/edit/",
        crud.report_card_form,
        name="report_card_edit",
    ),
    path(
        "report-cards/<uuid:report_card_id>/delete/",
        crud.report_card_delete,
        name="report_card_delete",
    ),
    path(
        "online-classes/",
        crud.online_class_manage_list,
        name="online_class_manage_list",
    ),
    path(
        "online-classes/create/",
        crud.online_class_form,
        name="online_class_create",
    ),
    path(
        "online-classes/<uuid:class_id>/edit/",
        crud.online_class_form,
        name="online_class_edit",
    ),
    path(
        "online-classes/<uuid:class_id>/delete/",
        crud.online_class_delete,
        name="online_class_delete",
    ),
    path("bbb/", crud.bbb_config_list, name="bbb_config_list"),
    path("bbb/create/", crud.bbb_config_form, name="bbb_config_create"),
    path("bbb/<uuid:config_id>/edit/", crud.bbb_config_form, name="bbb_config_edit"),
    path(
        "bbb/<uuid:config_id>/delete/",
        crud.bbb_config_delete,
        name="bbb_config_delete",
    ),
    path("activity-logs/", crud.activity_log_list, name="activity_log_list"),
    path("load-year-people/", crud.load_year_people, name="load_year_people"),
]
