from django.urls import path

from . import views


urlpatterns = [
    path("announcements/", views.recipient_announcement_list, name="recipient_announcement_list"),
    path("delete-all/", views.delete_all_notifications, name="delete_all_notifications"),
    path(
        "",
        views.notification_list,
        name="notification_list",
    ),

    path(
        "<uuid:notification_id>/open/",
        views.open_notification,
        name="open_notification",
    ),
]
