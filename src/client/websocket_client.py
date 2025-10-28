
import asyncio
import json
import websockets
from src.config.settings import settings
from src.utils.logger import app_log, errors_log

class WebsocketClient:
    """Handles real-time data streams from Binance Futures via WebSockets."""

    def __init__(self, message_handler):
        self.ws_url = settings.websocket_url
        self.message_handler = message_handler
        self.ws = None
        self.is_running = False
        self.reconnect_attempts = 0

    async def _connect(self):
        """Establishes a connection to the WebSocket server."""
        app_log.info("Connecting to WebSocket...")
        try:
            self.ws = await websockets.connect(self.ws_url + '/ws/!bookTicker') # Example stream
            app_log.info("WebSocket connection established.")
            self.reconnect_attempts = 0
            return True
        except Exception as e:
            errors_log.error(f"WebSocket connection failed: {e}")
            return False

    async def start(self):
        """Starts the WebSocket client and handles reconnection."""
        self.is_running = True
        while self.is_running:
            if await self._connect():
                await self._listen()
            
            if not self.is_running: # Check if stop was called during listen
                break

            self.reconnect_attempts += 1
            delay = min(self.reconnect_attempts * 5, 60) # Exponential backoff with a max delay
            app_log.warning(f"WebSocket disconnected. Attempting to reconnect in {delay} seconds...")
            await asyncio.sleep(delay)

    async def _listen(self):
        """Listens for incoming messages from the WebSocket."""
        try:
            while self.is_running:
                message = await self.ws.recv()
                data = json.loads(message)
                await self.message_handler(data)
        except websockets.exceptions.ConnectionClosed as e:
            errors_log.warning(f"WebSocket connection closed unexpectedly: {e}")
        except Exception as e:
            errors_log.error(f"An error occurred in the WebSocket listener: {e}")

    async def stop(self):
        """Stops the WebSocket client."""
        app_log.info("Stopping WebSocket client...")
        self.is_running = False
        if self.ws:
            await self.ws.close()
            app_log.info("WebSocket connection closed by user.")

    async def subscribe_to_streams(self, streams: list):
        """Subscribes to a list of WebSocket streams."""
        if not self.ws:
            app_log.warning("WebSocket not connected. Cannot subscribe to streams.")
            return

        request = {
            "method": "SUBSCRIBE",
            "params": streams,
            "id": 1
        }
        await self.ws.send(json.dumps(request))
        app_log.info(f"Subscribed to streams: {streams}")

# Example message handler
async def handle_message(data):
    # In a real application, this would update market data, trigger strategies, etc.
    # For now, we just log the message.
    app_log.debug(f"Received WebSocket message: {data}")

if __name__ == '__main__':
    # Example usage
    async def main():
        ws_client = WebsocketClient(handle_message)
        # Start the client in the background
        asyncio.create_task(ws_client.start())
        
        # Subscribe to streams after a short delay to ensure connection
        await asyncio.sleep(2)
        await ws_client.subscribe_to_streams(["btcusdt@kline_1m", "ethusdt@depth"])

        # Keep the main task running
        try:
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            await ws_client.stop()

    asyncio.run(main())
