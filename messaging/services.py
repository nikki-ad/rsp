from django.core.exceptions import ValidationError
from django.db.models import Q

from .models import Conversation


def get_or_create_conversation(user_1, user_2):

    if user_1 == user_2:
        raise ValidationError(
            "کاربر نمی‌تواند با خودش گفتگو ایجاد کند."
        )

    existing_conversation = Conversation.objects.filter(
        Q(
            participant_1=user_1,
            participant_2=user_2,
        )
        |
        Q(
            participant_1=user_2,
            participant_2=user_1,
        )
    ).first()

    if existing_conversation:
        return existing_conversation, False

    participants = sorted(
        [user_1, user_2],
        key=lambda user: str(user.pk),
    )

    conversation = Conversation.objects.create(
        participant_1=participants[0],
        participant_2=participants[1],
    )

    return conversation, True