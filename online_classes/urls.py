from django.urls import path

from . import views


urlpatterns = [
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