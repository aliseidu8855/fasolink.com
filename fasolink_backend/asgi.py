"""
ASGI config for fasolink_backend project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/asgi/
"""

import os

# IMPORTANT: Configure settings before importing Django/Channels components
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'fasolink_backend.settings')

from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.security.websocket import AllowedHostsOriginValidator

# Initialize Django first so app registry is ready before importing modules that access models
django_asgi_app = get_asgi_application()

# Now import middleware and routing that depend on Django apps/models
from api.middleware import TokenAuthMiddlewareStack  # noqa: E402
import api.routing  # noqa: E402

application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": AllowedHostsOriginValidator(
        TokenAuthMiddlewareStack(
            URLRouter(
                api.routing.websocket_urlpatterns
            )
        )
    ),
})
