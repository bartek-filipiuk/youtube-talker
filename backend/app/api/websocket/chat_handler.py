"""
WebSocket Chat Handler

Main WebSocket endpoint for real-time chat.
Handles authentication, message validation, RAG integration, and message persistence (PR #16).
"""

import logging
from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import WebSocket, WebSocketDisconnect, status, Query, Depends
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.websocket.connection_manager import connection_manager
from app.api.websocket.rate_limiter import rate_limiter
from app.db.session import get_db
from app.api.websocket.messages import (
    AssistantMessage,
    ErrorMessage,
    IncomingMessage,
    PingMessage,
    PongMessage,
    StatusMessage,
)
from app.db.models import User, Conversation
from app.db.repositories.conversation_repo import ConversationRepository
from app.db.repositories.message_repo import MessageRepository
from app.services.auth_service import AuthService
from app.rag.graphs.router import run_graph

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

            # PR #16: Full RAG integration
            try:
                # Step 1: Check rate limit
                if not rate_limiter.check_rate_limit(current_user.id):
                    await connection_manager.send_json(
                        websocket,
                        ErrorMessage(
                            message="Rate limit exceeded. Please wait a moment before sending another message.",
                            code="RATE_LIMIT"
                        ).model_dump()
                    )
                    continue

                # Step 2: Handle conversation (auto-create or verify ownership)
                conversation_repo = ConversationRepository(db)
                message_repo = MessageRepository(db)

                conversation: Optional[Conversation] = None
                conversation_id_str = message.conversation_id

                if conversation_id_str == "new" or not conversation_id_str:
                    # Auto-create new conversation
                    conversation = await conversation_repo.create(
                        user_id=current_user.id,
                        title=f"Chat {datetime.utcnow().strftime('%Y-%m-%d %H:%M')}"
                    )
                    await db.commit()
                    await db.refresh(conversation)
                    logger.info(f"Created new conversation {conversation.id} for user {current_user.id}")
                else:
                    # Verify user owns conversation
                    try:
                        conversation_uuid = UUID(conversation_id_str)
                        conversation = await conversation_repo.get_by_id(conversation_uuid)

                        if not conversation:
                            await connection_manager.send_json(
                                websocket,
                                ErrorMessage(
                                    message="Conversation not found.",
                                    code="NOT_FOUND"
                                ).model_dump()
                            )
                            continue

                        if conversation.user_id != current_user.id:
                            await connection_manager.send_json(
                                websocket,
                                ErrorMessage(
                                    message="Access denied to this conversation.",
                                    code="FORBIDDEN"
                                ).model_dump()
                            )
                            continue

                    except ValueError:
                        await connection_manager.send_json(
                            websocket,
                            ErrorMessage(
                                message="Invalid conversation ID format.",
                                code="VALIDATION_ERROR"
                            ).model_dump()
                        )
                        continue

                # Step 3: Send status update - classifying
                await connection_manager.send_json(
                    websocket,
                    StatusMessage(
                        message="Classifying your query...",
                        step="routing"
                    ).model_dump()
                )

                # Step 4: Fetch conversation history (last 10 messages)
                messages = await message_repo.get_last_n(conversation.id, n=10)
                conversation_history = [
                    {"role": msg.role, "content": msg.content}
                    for msg in messages
                ]

                # Step 5: Send status update - retrieving
                await connection_manager.send_json(
                    websocket,
                    StatusMessage(
                        message="Searching knowledge base...",
                        step="retrieving"
                    ).model_dump()
                )

                # Step 6: Call run_graph (RAG flow)
                result = await run_graph(
                    user_query=message.content,
                    user_id=str(current_user.id),
                    conversation_history=conversation_history
                )

                # Step 7: Send status update - generating
                await connection_manager.send_json(
                    websocket,
                    StatusMessage(
                        message="Generating response...",
                        step="generating"
                    ).model_dump()
                )

                # Step 8: Send complete response
                response_metadata = {
                    "intent": result.get("intent", "unknown"),
                    "conversation_id": str(conversation.id),
                    **result.get("metadata", {})
                }

                await connection_manager.send_json(
                    websocket,
                    AssistantMessage(
                        content=result.get("response", "<p>No response generated</p>"),
                        metadata=response_metadata
                    ).model_dump()
                )

                # Step 9: Save messages to database
                # Save user message
                await message_repo.create(
                    conversation_id=conversation.id,
                    role="user",
                    content=message.content,
                    meta_data={}
                )

                # Save assistant message
                await message_repo.create(
                    conversation_id=conversation.id,
                    role="assistant",
                    content=result.get("response", ""),
                    meta_data=response_metadata
                )

                # Update conversation timestamp
                conversation.updated_at = datetime.utcnow()
                await db.commit()

                logger.info(
                    f"Processed message for user {current_user.id}, "
                    f"conversation {conversation.id}, intent: {result.get('intent')}"
                )

            except Exception as e:
                # Error handling: don't save anything, just log and send error
                logger.error(
                    f"Error processing message for user {current_user.id}: {e}",
                    exc_info=True
                )
                await db.rollback()

                await connection_manager.send_json(
                    websocket,
                    ErrorMessage(
                        message="Something went wrong. Please try again.",
                        code="SERVER_ERROR"
                    ).model_dump()
                )

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
