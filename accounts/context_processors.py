from notifications.models import Notification


def ui_extras(request):
    if not request.user.is_authenticated:
        return {
            "unread_notification_count": 0,
        }

    return {
        "unread_notification_count": Notification.objects.filter(
            recipient=request.user,
            is_read=False,
        ).count(),
    }
