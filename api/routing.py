from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    # Per-conversation socket: ws://<host>/ws/conversations/<id>/
    re_path(r"^ws/conversations/(?P<conversation_id>\d+)/$", consumers.ChatConsumer.as_asgi()),
    # Per-user notifications: ws://<host>/ws/notifications/
    re_path(r"^ws/notifications/$", consumers.UserNotificationsConsumer.as_asgi()),
]
