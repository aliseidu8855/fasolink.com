import json
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser
from django.shortcuts import get_object_or_404
from .models import Conversation, Message, MessageRead


class ChatConsumer(AsyncJsonWebsocketConsumer):
    """Per-conversation websocket. Group name: convo_<id>.
    Client should send JSON messages with action keys: 'typing', 'message', 'read'.
    """

    async def connect(self):
        self.conversation_id = self.scope['url_route']['kwargs']['conversation_id']
        self.group_name = f"convo_{self.conversation_id}"
        user = self.scope.get('user')

        # Only authenticated participants can join
        is_allowed = await self._user_allowed(user, self.conversation_id)
        if not is_allowed:
            await self.close(code=4403)  # Forbidden
            return

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive_json(self, content, **kwargs):
        action = content.get('action')
        user = self.scope.get('user')
        if action == 'typing':
            await self.channel_layer.group_send(self.group_name, {
                'type': 'chat.typing',
                'user_id': getattr(user, 'id', None),
            })
        elif action == 'message':
            text = (content.get('content') or '').strip()
            if text:
                msg = await self._create_message(user, self.conversation_id, text)
                payload = {
                    'id': msg.id,
                    'content': msg.content,
                    'sender_id': msg.sender_id,
                    'sender': msg.sender.username,
                    'timestamp': msg.timestamp.isoformat(),
                }
                await self.channel_layer.group_send(self.group_name, {
                    'type': 'chat.message',
                    'message': payload,
                })
        elif action == 'read':
            updated = await self._mark_read(user, self.conversation_id)
            await self.channel_layer.group_send(self.group_name, {
                'type': 'chat.read',
                'user_id': getattr(user, 'id', None),
                'updated': updated,
            })

    async def chat_message(self, event):
        await self.send_json({'event': 'message.created', 'message': event['message']})

    async def chat_typing(self, event):
        await self.send_json({'event': 'typing', 'user_id': event.get('user_id')})

    async def chat_read(self, event):
        await self.send_json({'event': 'read', 'user_id': event.get('user_id'), 'updated': event.get('updated', 0)})

    @database_sync_to_async
    def _user_allowed(self, user, conversation_id):
        if not user or isinstance(user, AnonymousUser) or not user.is_authenticated:
            return False
        convo = get_object_or_404(Conversation, pk=conversation_id)
        return convo.participants.filter(pk=user.id).exists()

    @database_sync_to_async
    def _create_message(self, user, conversation_id, content):
        convo = Conversation.objects.get(pk=conversation_id)
        return Message.objects.create(conversation=convo, sender=user, content=content)

    @database_sync_to_async
    def _mark_read(self, user, conversation_id):
        convo = Conversation.objects.get(pk=conversation_id)
        unread = convo.messages.exclude(sender=user).exclude(reads__user=user)
        to_create = [MessageRead(message=m, user=user) for m in unread]
        if to_create:
            MessageRead.objects.bulk_create(to_create, ignore_conflicts=True)
        return len(to_create)


class UserNotificationsConsumer(AsyncJsonWebsocketConsumer):
    """Per-user notifications channel. Group name: user_<id>. Pushes conversation list updates or unread counts."""

    async def connect(self):
        user = self.scope.get('user')
        if not user or not user.is_authenticated:
            await self.close(code=4403)
            return
        self.group_name = f"user_{user.id}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive_json(self, content, **kwargs):
        # Currently no client commands; placeholder for ping/subscribe events
        pass

    async def notify(self, event):
        # Generic notification passthrough
        await self.send_json(event.get('data', {}))
