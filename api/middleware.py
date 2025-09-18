from urllib.parse import parse_qs


class TokenAuthMiddleware:
    """Simple token auth for Channels using DRF tokens via query string.
    Client connects to ws://.../ws/...?token=<token>
    """

    def __init__(self, inner):
        self.inner = inner

    async def __call__(self, scope, receive, send):
        query_string = scope.get('query_string', b'').decode()
        params = parse_qs(query_string)
        token_key = params.get('token', [None])[0]
        scope['user'] = await self.get_user(token_key)
        return await self.inner(scope, receive, send)

    @staticmethod
    async def get_user(token_key):
        # Lazy import to ensure Django apps are loaded
        from django.contrib.auth.models import AnonymousUser
        if not token_key:
            return AnonymousUser()
        try:
            token = await TokenAuthMiddleware._get_token(token_key)
            return token.user if token else AnonymousUser()
        except Exception:
            return AnonymousUser()

    @staticmethod
    async def _get_token(key):
        from asgiref.sync import sync_to_async
        # Lazy import Token model to avoid early model import
        from rest_framework.authtoken.models import Token
        return await sync_to_async(Token.objects.select_related('user').filter(key=key).first)()


def TokenAuthMiddlewareStack(inner):
    from channels.auth import AuthMiddlewareStack
    return TokenAuthMiddleware(AuthMiddlewareStack(inner))
