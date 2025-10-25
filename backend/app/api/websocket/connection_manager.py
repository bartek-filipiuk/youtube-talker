"""
WebSocket Connection Manager

Manages active WebSocket connections and handles heartbeat mechanism.
"""

from loguru import logger
from typing import Dict, Set
from uuid import UUID

from fastapi import WebSocket



class ConnectionManager:
    """
    Manage WebSocket connections for real-time chat.

    Tracks active connections per user and provides methods for
    sending messages and handling heartbeats.
    """

    def __init__(self):
        """Initialize connection manager with empty connection tracking."""
        # Map of user_id -> set of websockets
        self.active_connections: Dict[UUID, Set[WebSocket]] = {}
        logger.info("ConnectionManager initialized")

    async def connect(self, websocket: WebSocket, user_id: UUID) -> None:
        """
        Register a new WebSocket connection for a user.

        Args:
            websocket: FastAPI WebSocket instance
            user_id: User's UUID

        Example:
            await manager.connect(websocket, user.id)
        """
        await websocket.accept()

        if user_id not in self.active_connections:
            self.active_connections[user_id] = set()

        self.active_connections[user_id].add(websocket)
        logger.info(f"User {user_id} connected. Total connections: {len(self.active_connections[user_id])}")

    async def disconnect(self, websocket: WebSocket, user_id: UUID) -> None:
        """
        Remove a WebSocket connection for a user.

        Args:
            websocket: FastAPI WebSocket instance
            user_id: User's UUID

        Example:
            await manager.disconnect(websocket, user.id)
        """
        if user_id in self.active_connections:
            self.active_connections[user_id].discard(websocket)

            # Clean up empty sets
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]

            logger.info(f"User {user_id} disconnected. Remaining connections: {len(self.active_connections.get(user_id, []))}")

    async def send_json(self, websocket: WebSocket, data: dict) -> None:
        """
        Send JSON data to a specific WebSocket connection.

        Args:
            websocket: FastAPI WebSocket instance
            data: Dictionary to send as JSON

        Raises:
            Exception: If send fails (connection closed)

        Example:
            await manager.send_json(websocket, {"type": "status", "message": "Processing..."})
        """
        try:
            await websocket.send_json(data)
            logger.debug(f"Sent message: {data.get('type', 'unknown')}")
        except Exception as e:
            logger.error(f"Failed to send message: {e}")
            raise

    def get_user_connections(self, user_id: UUID) -> Set[WebSocket]:
        """
        Get all active WebSocket connections for a user.

        Args:
            user_id: User's UUID

        Returns:
            Set of WebSocket instances (empty set if no connections)

        Example:
            connections = manager.get_user_connections(user.id)
        """
        return self.active_connections.get(user_id, set())

    def get_total_connections(self) -> int:
        """
        Get total number of active WebSocket connections across all users.

        Returns:
            Total connection count

        Example:
            total = manager.get_total_connections()
        """
        return sum(len(connections) for connections in self.active_connections.values())


# Global singleton instance
connection_manager = ConnectionManager()
