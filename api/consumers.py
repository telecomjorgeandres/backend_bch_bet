import json
from channels.generic.websocket import AsyncWebsocketConsumer
import logging

logger = logging.getLogger(__name__)

class MatchUpdateConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for real-time updates on match transactions.
    Clients can connect to a specific match_id to receive updates relevant to that match.
    """
    async def connect(self):
        self.match_id = self.scope['url_route']['kwargs']['match_id']
        self.match_group_name = f'match_{self.match_id}'

        # Join match group
        await self.channel_layer.group_add(
            self.match_group_name,
            self.channel_name
        )
        logger.info(f"WebSocket connected: {self.channel_name} to group {self.match_group_name}")
        await self.accept()

    async def disconnect(self, close_code):
        # Leave match group
        await self.channel_layer.group_discard(
            self.match_group_name,
            self.channel_name
        )
        logger.info(f"WebSocket disconnected: {self.channel_name} from group {self.match_group_name} with code {close_code}")

    async def receive(self, text_data):
        # This consumer is primarily for sending updates from the backend,
        # but if the frontend needs to send messages (e.g., request history),
        # this method would handle it. For now, we'll log it.
        text_data_json = json.loads(text_data)
        message = text_data_json['message']
        logger.debug(f"Received message from WebSocket client ({self.match_group_name}): {message}")

    async def transaction_update(self, event):
        """
        Receive message from match group (sent by background task) and send to WebSocket.
        """
        message = event['message']
        logger.debug(f"Sending transaction_update message to WebSocket client: {message}")
        await self.send(text_data=json.dumps(message))

class BCHRateConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for real-time BCH to USD rate updates.
    """
    async def connect(self):
        self.bch_rate_group_name = 'bch_rate_updates'

        # Join BCH rate group
        await self.channel_layer.group_add(
            self.bch_rate_group_name,
            self.channel_name
        )
        logger.info(f"WebSocket connected: {self.channel_name} to group {self.bch_rate_group_name}")
        await self.accept()

    async def disconnect(self, close_code):
        # Leave BCH rate group
        await self.channel_layer.group_discard(
            self.bch_rate_group_name,
            self.channel_name
        )
        logger.info(f"WebSocket disconnected: {self.channel_name} from group {self.bch_rate_group_name} with code {close_code}")

    async def receive(self, text_data):
        # This consumer is primarily for sending updates from the backend.
        pass

    async def bch_rate_update(self, event):
        """
        Receive message from BCH rate group (sent by background task) and send to WebSocket.
        """
        message = event['message']
        logger.debug(f"Sending bch_rate_update message to WebSocket client: {message}")
        await self.send(text_data=json.dumps(message))

