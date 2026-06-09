# backend_client.py - WebSocket client connecting to the backend server
import asyncio
import json
import logging
from typing import Optional

import websockets

import config
from spike_state import SpikeState
import spike_logic

logger = logging.getLogger("backend_client")

RECONNECT_DELAY = 5  # seconds between reconnection attempts


class BackendClient:
    """
    Outbound WebSocket client that maintains a persistent connection
    to the backend game server.

    Inbound (backend → spike):
        round_start     → spike_logic.start_round()
        round_end       → spike_logic.reset_round()
        set_time_scale  → state.update(time_scale=...)

    Outbound (spike → backend):
        spike_planting, spike_planted, defuse_started,
        defenders_win, attackers_win
    """

    def __init__(self, spike_state: SpikeState):
        self._state = spike_state
        self._ws: Optional[websockets.WebSocketClientProtocol] = None
        self._running = False

    # ------------------------------------------------------------------
    # Outbound: send events TO the backend
    # ------------------------------------------------------------------
    async def send_event(self, event: dict):
        """Send an event dict to the backend. Silently drops if not connected."""
        if self._ws is None:
            logger.debug(f"Backend not connected, dropping event: {event}")
            return
        try:
            await self._ws.send(json.dumps(event))
            logger.info(f"Sent to backend: {event}")
        except Exception as e:
            logger.warning(f"Failed to send event to backend: {e}")

    # ------------------------------------------------------------------
    # Inbound: handle commands FROM the backend
    # ------------------------------------------------------------------
    async def _handle_message(self, raw: str):
        """Parse and dispatch a single inbound message from the backend."""
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            logger.warning(f"Received non-JSON from backend: {raw!r}")
            return

        event = data.get("event")
        if not event:
            logger.warning(f"Backend message missing 'event' key: {data}")
            return

        logger.info(f"Received from backend: {event}")

        if event == "round_start":
            await spike_logic.start_round(self._state)

        elif event == "round_end":
            await spike_logic.reset_round(self._state)

        elif event == "set_time_scale":
            scale = data.get("scale", 1.0)
            await self._state.update(time_scale=float(scale))
            logger.info(f"Time scale set to {scale}")

        else:
            logger.warning(f"Unknown backend event: {event}")

    # ------------------------------------------------------------------
    # Connection loop with automatic reconnection
    # ------------------------------------------------------------------
    async def run(self):
        """
        Main loop: connects to the backend WS, listens for messages,
        and automatically reconnects on failure.
        """
        self._running = True
        url = config.BACKEND_WS_URL
        logger.info(f"Backend client targeting: {url}")

        while self._running:
            try:
                async with websockets.connect(url) as ws:
                    self._ws = ws
                    logger.info(f"Connected to backend at {url}")

                    async for message in ws:
                        await self._handle_message(message)

            except (ConnectionRefusedError, OSError) as e:
                logger.warning(
                    f"Backend connection failed ({e}). "
                    f"Retrying in {RECONNECT_DELAY}s..."
                )
            except websockets.ConnectionClosed as e:
                logger.warning(
                    f"Backend connection closed ({e}). "
                    f"Reconnecting in {RECONNECT_DELAY}s..."
                )
            except asyncio.CancelledError:
                logger.info("Backend client cancelled.")
                break
            except Exception as e:
                logger.error(f"Unexpected backend client error: {e}", exc_info=True)
            finally:
                self._ws = None

            if self._running:
                await asyncio.sleep(RECONNECT_DELAY)

        logger.info("Backend client stopped.")

    def stop(self):
        """Signal the client loop to stop."""
        self._running = False


# ──────────────────────────────────────
# Module-level singleton
# ──────────────────────────────────────
backend_client: Optional[BackendClient] = None


def init_backend_client(spike_state: SpikeState) -> BackendClient:
    """Create and return the global BackendClient instance."""
    global backend_client
    backend_client = BackendClient(spike_state)
    return backend_client
