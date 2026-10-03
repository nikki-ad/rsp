from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone

from accounts.choices import Role
from academic.models import AcademicYear
from .models import Announcement, Notification
from . import constants


def recipients_for(announcement):
    users = get_user_model().objects.filter(is_active=True)
    if announcement.audience == Announcement.Audience.ALL:
        return users.filter(role__in=[Role.STUDENT, Role.TEACHER])
    if announcement.audience == Announcement.Audience.TEACHERS:
        users = users.filter(teacher_profile__isnull=False)
        if announcement.targeted:
            users = users.filter(teacher_profile__in=announcement.teachers.all())
    elif announcement.audience in {Announcement.Audience.STUDENTS, Announcement.Audience.CLASSROOM}:
        users = users.filter(student_profile__isnull=False)
        if announcement.targeted or announcement.audience == Announcement.Audience.CLASSROOM:
            classes = announcement.classrooms.all() if announcement.targeted else [announcement.classroom_id]
            users = users.filter(
                student_profile__enrollments__classroom__in=classes,
                student_profile__enrollments__is_active=True,
                student_profile__enrollments__academic_year__status=AcademicYear.Status.ACTIVE,
                student_profile__enrollments__classroom__academic_year__status=AcademicYear.Status.ACTIVE,
            )
    else:
        return users.none()
    return users.distinct()


def announcements_for(user):
    active = Announcement.objects.filter(is_active=True, publish_at__lte=timezone.now())
    if not user.is_active:
        return active.none()
    query = Q(pk__in=[])
    if user.role in {Role.STUDENT, Role.TEACHER}:
        query |= Q(audience=Announcement.Audience.ALL)
    teacher = getattr(user, "teacher_profile", None)
    if teacher:
        query |= Q(audience=Announcement.Audience.TEACHERS, targeted=False)
        query |= Q(audience=Announcement.Audience.TEACHERS, targeted=True, teachers=teacher)
    student = getattr(user, "student_profile", None)
    if student:
        classes = student.enrollments.filter(
            is_active=True, academic_year__status=AcademicYear.Status.ACTIVE,
            classroom__academic_year__status=AcademicYear.Status.ACTIVE,
        ).values_list("classroom_id", flat=True)
        query |= Q(audience=Announcement.Audience.STUDENTS, targeted=False)
        query |= Q(audience=Announcement.Audience.STUDENTS, targeted=True, classrooms__in=classes)
        query |= Q(audience=Announcement.Audience.CLASSROOM, classroom__in=classes)
    return active.filter(query).distinct().order_by("-publish_at")


def _defaults(announcement):
    return dict(notification_type=constants.ANNOUNCEMENT, title=announcement.title,
                message=announcement.message, url=reverse("notification_list"))


@transaction.atomic
def sync_announcement(announcement):
    # Serialize edits and recipient synchronization for the same announcement.
    announcement = Announcement.objects.select_for_update().get(pk=announcement.pk)
    if not announcement.is_active or announcement.publish_at > timezone.now():
        announcement.notifications.all().delete()
        announcement.notified_users.clear()
        return
    recipients = recipients_for(announcement)
    announcement.notifications.exclude(recipient__in=recipients).delete()
    announcement.notified_users.remove(*announcement.notified_users.exclude(pk__in=recipients).values_list("pk", flat=True))
    for user in recipients:
        Notification.objects.update_or_create(
            announcement=announcement, recipient=user, defaults=_defaults(announcement)
        )
        announcement.notified_users.add(user)


@transaction.atomic
def ensure_announcement_notifications(user, announcements=None):
    # Scheduled and old announcements become available when the recipient signs in.
    visible = announcements if announcements is not None else announcements_for(user)
    for item in visible.exclude(notified_users=user):
        announcement = Announcement.objects.select_for_update().get(pk=item.pk)
        if announcement.notified_users.filter(pk=user.pk).exists():
            continue
        Notification.objects.get_or_create(
            announcement=announcement, recipient=user, defaults=_defaults(announcement)
        )
        announcement.notified_users.add(user)
