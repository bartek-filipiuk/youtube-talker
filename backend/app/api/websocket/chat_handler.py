"""
WebSocket Chat Handler

Main WebSocket endpoint for real-time chat.
Handles authentication, message validation, and basic echo (PR #15).
RAG integration will be added in PR #16.
"""

import logging
from typing import Optional
from uuid import UUID

from fastapi import WebSocket, WebSocketDisconnect, status, Query, Depends
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.websocket.connection_manager import connection_manager
from app.db.session import get_db
from app.api.websocket.messages import (
    AssistantMessage,
    ErrorMessage,
    IncomingMessage,
    PingMessage,
    PongMessage,
    StatusMessage,
)
from app.db.models import User
from app.services.auth_service import AuthService

logger = logging.getLogger(__name__)


async def websocket_endpoint(
    websocket: WebSocket,
    token: str = Query(...),
    db: AsyncSession = Depends(get_db)
) -> None:
    """
    Main WebSocket endpoint for real-time chat.

    Handles:
    - Authentication via query param token
    - Message validation
    - Echo responses (PR #15 - testing only)
    - Heartbeat (ping/pong)

    Args:
        websocket: FastAPI WebSocket instance
        token: Session token from query parameter
        db: Database session (injected via Depends)

    Flow:
        1. Validate token → get user
        2. Accept connection
        3. Handle incoming messages
        4. Echo back for testing (will be replaced with RAG in PR #16)

    Example:
        ws://localhost:8000/ws/chat?token=abc123
    """
    current_user: Optional[User] = None
    auth_service = AuthService(db)

    try:
        # Step 1: Authenticate user
        current_user = await auth_service.validate_session(token)

        if not current_user:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Invalid token")
            logger.warning(f"WebSocket connection rejected: invalid token")
            return

        # Step 2: Accept connection and register in manager
        await connection_manager.connect(websocket, current_user.id)
        logger.info(f"User {current_user.id} ({current_user.email}) connected via WebSocket")

        # Send welcome message
        await connection_manager.send_json(
            websocket,
            {
                "type": "status",
                "message": f"Connected as {current_user.email}",
                "step": "routing"
            }
        )

        # Step 3: Message loop
        while True:
            # Receive message from client
            raw_data = await websocket.receive_json()

            # Handle ping/pong (heartbeat)
            if raw_data.get("type") == "ping":
                await connection_manager.send_json(
                    websocket,
                    PongMessage().model_dump()
                )
                logger.debug(f"Heartbeat received from user {current_user.id}")
                continue

            # Validate incoming message
            try:
                message = IncomingMessage(**raw_data)
            except ValidationError as e:
                await connection_manager.send_json(
                    websocket,
                    ErrorMessage(
                        message="Invalid message format. Please check your input.",
                        code="VALIDATION_ERROR"
                    ).model_dump()
                )
                logger.warning(f"Validation error from user {current_user.id}: {e}")
                continue

            # Log received message
            logger.info(
                f"Received message from user {current_user.id}: "
                f"conversation={message.conversation_id}, "
                f"content_length={len(message.content)}"
            )

            # PR #15: Echo back for testing
            # PR #16: Will integrate run_graph() here
            await connection_manager.send_json(
                websocket,
                AssistantMessage(
                    content=f"<p>[Echo] You said: {message.content}</p>",
                    metadata={
                        "intent": "echo",
                        "conversation_id": message.conversation_id or "new",
                        "test_mode": True
                    }
                ).model_dump()
            )
            logger.debug(f"Echo sent to user {current_user.id}")

    except WebSocketDisconnect:
        logger.info(f"User {current_user.id if current_user else 'unknown'} disconnected")

    except Exception as e:
        logger.error(f"WebSocket error for user {current_user.id if current_user else 'unknown'}: {e}", exc_info=True)

        # Try to send error message before closing
        try:
            await connection_manager.send_json(
                websocket,
                ErrorMessage(
                    message="An unexpected error occurred. Please reconnect.",
                    code="SERVER_ERROR"
                ).model_dump()
            )
        except:
            pass  # Connection might already be closed

    finally:
        # Step 4: Cleanup
        if current_user:
            await connection_manager.disconnect(websocket, current_user.id)
            logger.info(f"Cleaned up connection for user {current_user.id}")
