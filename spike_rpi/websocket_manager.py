# websocket_manager.py - WebSocket server hub for real-time client updates
import logging
from typing import List
from fastapi import WebSocket

logger = logging.getLogger("websocket_manager")

class WebSocketManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket, initial_state: dict):
        """Accepts the connection, registers client, and sends initial state."""
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"Client connected. Active clients count: {len(self.active_connections)}")
        
        # Immediately send full current state to newly connected client
        try:
            await websocket.send_json(initial_state)
        except Exception as e:
            logger.error(f"Error sending initial state to client: {e}")
            self.disconnect(websocket)

    def disconnect(self, websocket: WebSocket):
        """Removes the connection from the tracking register."""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            logger.info(f"Client disconnected. Active clients count: {len(self.active_connections)}")

    async def broadcast(self, message: dict):
        """Sends a JSON state update broadcast to all connected web sockets."""
        if not self.active_connections:
            return
            
        logger.debug(f"Broadcasting message: {message}")
        
        # Gather all tasks to send messages concurrently
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                disconnected.append(connection)
                
        # Clean up stale connections
        for conn in disconnected:
            self.disconnect(conn)


# Global WebSocket Manager
ws_manager = WebSocketManager()
