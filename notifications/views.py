from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from .models import Notification
from django.shortcuts import get_object_or_404, redirect, render

@login_required
def notification_list(request):

    notifications = Notification.objects.filter(
        recipient=request.user,
    )

    unread_count = notifications.filter(
        is_read=False,
    ).count()

    return render(
        request,
        "notifications/notification_list.html",
        {
            "notifications": notifications,
            "unread_count": unread_count,
        },
    )


@login_required
def open_notification(request, notification_id):

    notification = get_object_or_404(
        Notification,
        id=notification_id,
        recipient=request.user,
    )

    if not notification.is_read:
        notification.is_read = True
        notification.save(
            update_fields=[
                "is_read",
                "updated_at",
            ]
        )

    if notification.url:
        return redirect(notification.url)

    return redirect("notification_list")