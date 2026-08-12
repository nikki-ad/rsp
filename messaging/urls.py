from django.urls import path

from . import views


urlpatterns = [
    path(
        "",
        views.conversation_list,
        name="conversation_list",
    ),


    path(
        "users/",
        views.user_list_for_messaging,
        name="user_list_for_messaging",
    ),

    path(
        "start/<uuid:user_id>/",
        views.start_conversation,
        name="start_conversation",
    ),


    path(
        "<uuid:conversation_id>/",
        views.chat_view,
        name="chat_view",
    ),
]