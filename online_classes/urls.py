from django.urls import path

from . import views


urlpatterns = [
    path("<uuid:class_id>/attendance/enable/", views.enable_attendance_tracking, name="enable_attendance_tracking"),
    path("bbb-events/<uuid:config_id>/<uuid:class_id>/", views.bbb_attendance_callback, name="bbb_attendance_callback"),
    path(
        "",
        views.online_class_list,
        name="online_class_list",
    ),

    path(
        "<uuid:class_id>/join/",
        views.join_online_class,
        name="join_online_class",
    ),

    path(
        "<uuid:class_id>/attendance/",
        views.live_attendance,
        name="live_attendance",
    ),


]