from .announcements import announcements_for, ensure_announcement_notifications
from django.db.models import Q
from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from .models import Notification
from django.shortcuts import get_object_or_404, redirect, render
from django.contrib import messages

@login_required
def notification_list(request):

    visible = announcements_for(request.user)
    ensure_announcement_notifications(request.user, visible)
    notifications = Notification.objects.filter(
        recipient=request.user,
    ).filter(Q(announcement__isnull=True) | Q(announcement__in=visible)).select_related("announcement")

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
    if notification.announcement_id and not announcements_for(request.user).filter(pk=notification.announcement_id).exists():
        from django.http import Http404
        raise Http404()

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


@login_required
def delete_all_notifications(request):
    if request.method != "POST":
        return redirect("notification_list")
    deleted_count, _ = Notification.objects.filter(recipient=request.user).delete()
    messages.success(request, f"{deleted_count} اعلان حذف شد.")
    return redirect("notification_list")


@login_required
def recipient_announcement_list(request):
    from accounts.choices import Role
    from accounts.permissions import post_login_redirect_name
    from django.http import HttpResponseForbidden
    from django.urls import reverse

    if request.user.role not in {Role.STUDENT, Role.TEACHER}:
        return HttpResponseForbidden()
    visible = announcements_for(request.user)
    ensure_announcement_notifications(request.user, visible)
    return render(request, "notifications/announcement_list.html", {
        "announcements": visible,
        "back_url": reverse(post_login_redirect_name(request.user)),
    })
