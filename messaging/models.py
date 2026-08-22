from django.conf import settings
from django.db import models

from core.models import BaseModel

from django.core.exceptions import ValidationError
from django.db.models import Q


class Conversation(BaseModel):

    class Channel(models.TextChoices):
        GENERAL = "general", "پیام‌های مدرسه"
        LANGUAGE = "language", "واحد زبان"

    channel = models.CharField(
        max_length=20, choices=Channel.choices, default=Channel.GENERAL,
        verbose_name="بخش گفتگو",
    )

    participant_1 = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="conversations_as_participant_1",
        verbose_name="شرکت‌کننده اول",
    )

    participant_2 = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="conversations_as_participant_2",
        verbose_name="شرکت‌کننده دوم",
    )

    last_message = models.ForeignKey(
        "Message",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        verbose_name="آخرین پیام",
    )

    last_message_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="زمان آخرین پیام",
    )


    def clean(self):

        if self.participant_1 == self.participant_2:
            raise ValidationError(
                "کاربر نمی‌تواند با خودش گفتگو ایجاد کند."
            )

        if self.participant_1_id and self.participant_2_id:

            duplicate_conversation = Conversation.objects.filter(
                Q(
                    participant_1=self.participant_1,
                    participant_2=self.participant_2,
                )
                |
                Q(
                    participant_1=self.participant_2,
                    participant_2=self.participant_1,
                )
            ).filter(channel=self.channel).exclude(
                pk=self.pk
            )

            if duplicate_conversation.exists():
                raise ValidationError(
                    "بین این دو کاربر قبلاً یک گفتگو ایجاد شده است."
                )


    def save(self, *args, **kwargs):

        if (
            self.participant_1_id
            and self.participant_2_id
            and str(self.participant_1_id) > str(self.participant_2_id)
        ):
            self.participant_1, self.participant_2 = (
                self.participant_2,
                self.participant_1,
            )

        self.full_clean()

        return super().save(*args, **kwargs)

    class Meta:
        verbose_name = "گفتگو"
        verbose_name_plural = "گفتگوها"
        constraints = [
            models.UniqueConstraint(
                fields=("participant_1", "participant_2", "channel"),
                name="unique_conversation_participants_channel",
            )
        ]

    def __str__(self):
        return (
            f"{self.participant_1} ↔ "
            f"{self.participant_2}"
        )





class Message(BaseModel):

    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name="messages",
        verbose_name="گفتگو",
    )

    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="sent_messages",
        verbose_name="فرستنده",
    )

    text = models.TextField(
        blank=True,
        verbose_name="متن پیام",
    )

    file = models.FileField(
        upload_to="messages/",
        blank=True,
        null=True,
        verbose_name="فایل",
    )

    is_read = models.BooleanField(
        default=False,
        verbose_name="خوانده شده",
    )

    class Meta:
        verbose_name = "پیام"
        verbose_name_plural = "پیام‌ها"

    def __str__(self):
        return f"{self.sender}"
