from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.db.models import Q , Count
from notifications import constants as notification_constants
from .forms import MessageForm
from .models import Conversation, Message
from .services import get_or_create_conversation
from django.contrib.auth import get_user_model
from django.http import HttpResponseForbidden
from notifications.services import create_notification
from accounts.choices import Role
from django.urls import reverse



User = get_user_model()


@login_required
def conversation_list(request):

    conversations = (
        Conversation.objects.filter(
            Q(participant_1=request.user)
            | Q(participant_2=request.user)
        )
        .annotate(
            unread_count=Count(
                "messages",
                filter=(
                    Q(messages__is_read=False)
                    & ~Q(messages__sender=request.user)
                ),
            )
        )
        .order_by("-last_message_at", "-updated_at")
    )

    return render(
        request,
        "messaging/conversation_list.html",
        {
            "conversations": conversations,
        }
    )



@login_required
def start_conversation(request, user_id):

    other_user = get_object_or_404(
        request.user.__class__,
        id=user_id,
        is_active=True,
    )

    conversation, created = get_or_create_conversation(
        request.user,
        other_user,
    )

    return redirect(
        "chat_view",
        conversation_id=conversation.id,
    )



@login_required
def chat_view(request, conversation_id):

    conversation = get_object_or_404(
        Conversation,
        id=conversation_id,
    )

    if request.user not in [
        conversation.participant_1,
        conversation.participant_2,
    ]:
        return redirect("conversation_list")

    messages = conversation.messages.all().order_by(
        "created_at",
    )

    conversation.messages.filter(
        is_read=False,
    ).exclude(
        sender=request.user,
    ).update(
        is_read=True,
    )

    if request.method == "POST":

        form = MessageForm(
            request.POST,
            request.FILES,
        )

        if form.is_valid():

            message = form.save(commit=False)

            message.conversation = conversation
            message.sender = request.user

            message.save()

            conversation.last_message = message
            conversation.last_message_at = message.created_at

            conversation.save()
            if conversation.participant_1 == request.user:
                recipient = conversation.participant_2
            else:
                recipient = conversation.participant_1

            sender_name = (
                request.user.get_full_name()
                or request.user.username
            )

            create_notification(
                recipient=recipient,
                notification_type=notification_constants.MESSAGE,   
                title=f"پیام جدید از {sender_name}",
                message=message.text or "یک فایل برای شما ارسال شده است.",
                url=reverse(
                    "chat_view",
                    args=[conversation.id],
                ),
            )

            return redirect(
                "chat_view",
                conversation_id=conversation.id,
            )

    else:

        form = MessageForm()

    return render(
        request,
        "messaging/chat.html",
        {
            "conversation": conversation,
            "messages": messages,
            "form": form,
        }
    )

@login_required
def user_list_for_messaging(request):

    if not (
        request.user.is_superuser
        or request.user.role in [
            Role.SUPER_ADMIN,
            Role.SCHOOL_MANAGER,
        ]
    ):
        return HttpResponseForbidden(
            "شما اجازه دسترسی به این صفحه را ندارید."
        )

    users = User.objects.filter(
        is_active=True,
    ).exclude(
        id=request.user.id,
    ).order_by(
        "role",
        "first_name",
        "last_name",
        "username",
    )

    return render(
        request,
        "messaging/user_list.html",
        {
            "users": users,
        }
    )