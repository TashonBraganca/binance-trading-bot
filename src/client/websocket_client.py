import websocket
import json
import threading
import time
from typing import Dict, Any, Callable, Optional

from src.config.constants import BINANCE_FUTURES_TESTNET_WEBSOCKET_URL
from src.utils.logger import main_logger, errors_logger

class WebSocketClient:
    def __init__(self, streams: Dict[str, Callable[[Dict[str, Any]], None]]):
        self.base_url = BINANCE_FUTURES_TESTNET_WEBSOCKET_URL
        self.streams = streams  # {stream_name: callback_function}
        self.ws: Optional[websocket.WebSocketApp] = None
        self.is_running = False
        self.reconnect_interval = 5  # seconds
        self.last_ping_time = time.time()
        self.ping_interval = 30  # Send a ping every 30 seconds

    def _on_open(self, ws):
        main_logger.info("WebSocket connection opened.")
        self._subscribe_to_streams()

    def _on_message(self, ws, message):
        data = json.loads(message)
        stream_name = data.get("stream")
        if stream_name and stream_name in self.streams:
            self.streams[stream_name](data.get("data"))
        else:
            main_logger.debug(f"Received unhandled WebSocket message: {data}")
        self.last_ping_time = time.time() # Reset ping time on any message

    def _on_error(self, ws, error):
        errors_logger.error(f"WebSocket error: {error}")

    def _on_close(self, ws, close_status_code, close_msg):
        main_logger.warning(f"WebSocket connection closed. Status: {close_status_code}, Message: {close_msg}")
        if self.is_running:
            main_logger.info(f"Attempting to reconnect in {self.reconnect_interval} seconds...")
            time.sleep(self.reconnect_interval)
            self._connect_websocket()

    def _subscribe_to_streams(self):
        if not self.ws:
            return

        # Binance WebSocket API uses a single connection for multiple streams
        # The stream names are part of the URL path, e.g., /ws/btcusdt@kline_1m/ethusdt@depth
        # For simplicity, we'll assume each stream is a separate connection for now
        # or that the user provides a combined stream URL.
        # A more robust solution would combine streams into one connection.
        
        # For this implementation, we expect the 'streams' dict keys to be the full stream path
        # e.g., {'btcusdt@kline_1m': callback_func}
        # The actual connection URL will be constructed based on these.
        
        # If multiple streams are provided, we need to combine them into a single URL
        # Example: wss://stream.binancefuture.com/stream?streams=btcusdt@kline_1m/ethusdt@depth
        
        # This current setup assumes individual stream connections or a pre-combined URL.
        # Let's refine this to support multiple streams on a single connection.
        
        stream_paths = list(self.streams.keys())
        if not stream_paths:
            main_logger.warning("No streams provided to subscribe.")
            return

        # Construct the combined stream URL
        combined_stream_url = f"{self.base_url}/stream?streams={'/'.join(stream_paths)}"
        main_logger.info(f"Subscribing to combined WebSocket stream: {combined_stream_url}")
        
        # Re-initialize WebSocketApp with the combined URL
        self.ws = websocket.WebSocketApp(
            combined_stream_url,
            on_open=self._on_open,
            on_message=self._on_message,
            on_error=self._on_error,
            on_close=self._on_close
        )
        # Note: _on_open will be called again, which will re-subscribe. This is fine.
        # The actual subscription happens implicitly by connecting to the stream URL.

    def _connect_websocket(self):
        stream_paths = list(self.streams.keys())
        if not stream_paths:
            errors_logger.error("Cannot connect WebSocket: No streams provided.")
            return

        combined_stream_url = f"{self.base_url}/stream?streams={'/'.join(stream_paths)}"
        main_logger.info(f"Connecting to WebSocket: {combined_stream_url}")

        self.ws = websocket.WebSocketApp(
            combined_stream_url,
            on_open=self._on_open,
            on_message=self._on_message,
            on_error=self._on_error,
            on_close=self._on_close
        )
        # Run in a separate thread to not block the main thread
        self.wst = threading.Thread(target=self.ws.run_forever, kwargs={'ping_interval': self.ping_interval, 'ping_timeout': 10})
        self.wst.daemon = True
        self.wst.start()

    def is_connected(self) -> bool:
        """Returns True if WebSocket is actively connected and running."""
        return (self.is_running and
                self.ws is not None and
                self.ws.keep_running and
                self.wst is not None and
                self.wst.is_alive())

    def start(self):
        main_logger.info("Starting WebSocket client...")
        self.is_running = True
        self._connect_websocket()

    def stop(self):
        main_logger.info("Stopping WebSocket client...")
        self.is_running = False
        if self.ws:
            self.ws.close()
        if self.wst and self.wst.is_alive():
            self.wst.join(timeout=5) # Wait for thread to finish

    def add_stream(self, stream_name: str, callback: Callable[[Dict[str, Any]], None]):
        """Adds a new stream to the WebSocket client and reconnects to include it."""
        if stream_name not in self.streams:
            self.streams[stream_name] = callback
            if self.is_running:
                main_logger.info(f"Adding new stream {stream_name}. Reconnecting WebSocket...")
                self.stop() # Close current connection
                self.start() # Reconnect with new stream
        else:
            main_logger.warning(f"Stream {stream_name} already exists.")

    def remove_stream(self, stream_name: str):
        """Removes a stream from the WebSocket client and reconnects."""
        if stream_name in self.streams:
            del self.streams[stream_name]
            if self.is_running:
                main_logger.info(f"Removing stream {stream_name}. Reconnecting WebSocket...")
                self.stop()
                self.start()
        else:
            main_logger.warning(f"Stream {stream_name} not found.")