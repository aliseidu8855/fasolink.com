from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer


def broadcast_conversation_message(conversation_id, message_payload):
    layer = get_channel_layer()
    async_to_sync(layer.group_send)(
        f"convo_{conversation_id}",
        {"type": "chat.message", "message": message_payload},
    )


def broadcast_conversation_read(conversation_id, user_id, updated):
    layer = get_channel_layer()
    async_to_sync(layer.group_send)(
        f"convo_{conversation_id}",
        {"type": "chat.read", "user_id": user_id, "updated": updated},
    )


def notify_user(user_id, data: dict):
    layer = get_channel_layer()
    async_to_sync(layer.group_send)(
        f"user_{user_id}",
        {"type": "notify", "data": data},
    )
