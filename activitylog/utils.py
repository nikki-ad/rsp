from .models import ActivityLog


def get_client_ip(request):

    x_forwarded_for = request.META.get(
        "HTTP_X_FORWARDED_FOR"
    )

    if x_forwarded_for:
        return x_forwarded_for.split(",")[0].strip()

    return request.META.get("REMOTE_ADDR")


def log_activity(
    request,
    action,
    description="",
):

    user = None

    if request.user.is_authenticated:
        user = request.user

    ActivityLog.objects.create(
        user=user,
        action=action,
        description=description,
        ip_address=get_client_ip(request),
    )