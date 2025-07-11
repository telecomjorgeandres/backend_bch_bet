# api/routing.py
from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    # WebSocket endpoint for transaction updates.
    # The <str:match_id> allows clients to connect to a specific match's updates.
    re_path(r'ws/match_updates/(?P<match_id>\w{8}-\w{4}-\w{4}-\w{4}-\w{12})/$', consumers.MatchUpdateConsumer.as_asgi()),
    # A general WebSocket endpoint for BCH rate updates (optional, but good for real-time price)
    re_path(r'ws/bch_rate/$', consumers.BCHRateConsumer.as_asgi()),
]
