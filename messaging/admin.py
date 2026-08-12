from django.contrib import admin

from core.admin import BaseAdmin
from .models import Conversation, Message


@admin.register(Conversation)
class ConversationAdmin(BaseAdmin):

    list_display = (
        "participant_1",
        "participant_2",
        "created_at",
        "updated_at",
    )

    search_fields = (
        "participant_1__username",
        "participant_1__first_name",
        "participant_1__last_name",
        "participant_2__username",
        "participant_2__first_name",
        "participant_2__last_name",
    )


@admin.register(Message)
class MessageAdmin(BaseAdmin):

    list_display = (
        "conversation",
        "sender",
        "is_read",
        "created_at",
    )

    list_filter = (
        "is_read",
        "created_at",
    )

    search_fields = (
        "text",
        "sender__username",
        "sender__first_name",
        "sender__last_name",
    )