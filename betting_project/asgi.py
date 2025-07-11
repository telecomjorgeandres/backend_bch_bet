import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack # For potential future authentication on websockets
import api.routing # Import your app's routing

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'betting_project.settings')

application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    "websocket": AuthMiddlewareStack( # Use AuthMiddlewareStack for session/user access
        URLRouter(
            api.routing.websocket_urlpatterns # Point to your app's WebSocket URLs
        )
    ),
})