from .models import Notification
from . import constants

def create_notification(
    *,
    recipient,
    notification_type=constants.SYSTEM,    
    title,
    message="",
    url="",
):
    return Notification.objects.create(
        recipient=recipient,
        notification_type=notification_type,
        title=title,
        message=message,
        url=url,
    )