"""
WebSocket Chat Handler

Main WebSocket endpoint for real-time chat.
Handles authentication, message validation, RAG integration, and message persistence (PR #16).
"""

import re
from loguru import logger
from datetime import datetime, timezone
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
from app.api.websocket.video_loader import handle_video_load_intent, handle_confirmation_response
from app.utils.url_detector import detect_youtube_url
from app.db.models import User, Conversation
from app.db.repositories.conversation_repo import ConversationRepository
from app.db.repositories.message_repo import MessageRepository
from app.services.auth_service import AuthService
from app.services.config_service import ConfigService
from app.rag.graphs.router import run_graph
from app.config import settings
from app.db.repositories.channel_conversation_repo import ChannelConversationRepository
from app.db.repositories.channel_repo import ChannelRepository
from app.db.models import ChannelConversation, Channel
from app.core.errors import (
    ChannelNotFoundError,
    ConversationNotFoundError,
    ConversationAccessDeniedError,
)


async def detect_conversation_type(
    conversation_id: UUID,
    user_id: UUID,
    db: AsyncSession
) -> tuple[str, Conversation | ChannelConversation, Optional[Channel]]:
    """
    Detect if conversation_id is personal or channel conversation.

    Args:
        conversation_id: UUID of the conversation (personal or channel)
        user_id: UUID of the current user
        db: Database session

    Returns:
        ("personal", conversation_obj, None) for personal conversations
        ("channel", channel_conversation_obj, channel_obj) for channel conversations

    Raises:
        ConversationNotFoundError: Conversation doesn't exist
        ConversationAccessDeniedError: User doesn't own conversation
        ChannelNotFoundError: Channel was soft-deleted

    Example:
        conv_type, conversation, channel = await detect_conversation_type(
            conversation_id=uuid_obj,
            user_id=current_user.id,
            db=db
        )
        if conv_type == "channel":
            # Use channel.qdrant_collection_name
    """
    from app.core.errors import ConversationNotFoundError, ConversationAccessDeniedError

    # Try personal conversation first (most common case)
    conversation_repo = ConversationRepository(db)
    personal_conv = await conversation_repo.get_by_id(conversation_id)

    if personal_conv:
        # Verify ownership
        if personal_conv.user_id != user_id:
            raise ConversationAccessDeniedError(
                f"User {user_id} does not have access to conversation {conversation_id}"
            )
        return ("personal", personal_conv, None)

    # Try channel conversation
    channel_conv_repo = ChannelConversationRepository(db)
    channel_conv = await channel_conv_repo.get_by_id(conversation_id)

    if channel_conv:
        # Verify ownership
        if channel_conv.user_id != user_id:
            raise ConversationAccessDeniedError(
                f"User {user_id} does not have access to channel conversation {conversation_id}"
            )

        # Fetch channel and verify not deleted (is_active=True)
        channel_repo = ChannelRepository(db)
        channel = await channel_repo.get_by_id(channel_conv.channel_id)

        if not channel or not channel.is_active:
            raise ChannelNotFoundError(
                f"Channel {channel_conv.channel_id} is no longer available"
            )

        return ("channel", channel_conv, channel)

    # Not found in either table
    raise ConversationNotFoundError(
        f"Conversation {conversation_id} not found"
    )


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
        ws://localhost:8000/api/ws/chat?token=abc123
    """
    current_user: Optional[User] = None
    auth_service = AuthService(db)

    try:
        # Step 1: Accept the WebSocket connection (MUST be done first)
        await websocket.accept()

        # Step 2: Authenticate user
        current_user = await auth_service.validate_session(token)

        if not current_user:
            # Send error and close connection
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Invalid token")
            logger.warning(f"WebSocket connection rejected: invalid token")
            return

        # Step 3: Register in connection manager (don't call connect() as it tries to accept again)
        if current_user.id not in connection_manager.active_connections:
            connection_manager.active_connections[current_user.id] = set()
        connection_manager.active_connections[current_user.id].add(websocket)
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
                message_repo = MessageRepository(db)

                conversation: Optional[Conversation | ChannelConversation] = None
                conversation_id_str = message.conversation_id
                channel: Optional[Channel] = None
                state_extras = {}  # Extra state fields for channel conversations

                if conversation_id_str == "new" or not conversation_id_str:
                    # Auto-create new personal conversation
                    # Note: Channel conversations must already exist (created via REST API)
                    # Note: Repository already flushes and refreshes, so conversation.id is available
                    # We defer commit until after RAG succeeds to ensure all-or-nothing persistence
                    conversation_repo = ConversationRepository(db)
                    conversation = await conversation_repo.create(
                        user_id=current_user.id,
                        title=f"Chat {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')}"
                    )
                    logger.info(f"Created new personal conversation {conversation.id} for user {current_user.id}")
                else:
                    # Detect conversation type (personal or channel) and verify ownership
                    try:
                        conversation_uuid = UUID(conversation_id_str)
                        conv_type, conversation, channel = await detect_conversation_type(
                            conversation_id=conversation_uuid,
                            user_id=current_user.id,
                            db=db
                        )

                        # If channel conversation, add channel info to state
                        if conv_type == "channel" and channel:
                            state_extras["channel_id"] = str(channel.id)
                            state_extras["collection_name"] = channel.qdrant_collection_name
                            logger.info(
                                f"User {current_user.id} chatting with channel {channel.name} "
                                f"(conversation {conversation.id})"
                            )
                        else:
                            logger.info(
                                f"User {current_user.id} using personal conversation {conversation.id}"
                            )

                    except ValueError:
                        await connection_manager.send_json(
                            websocket,
                            ErrorMessage(
                                message="Invalid conversation ID format.",
                                code="VALIDATION_ERROR"
                            ).model_dump()
                        )
                        continue
                    except (ConversationNotFoundError, ConversationAccessDeniedError, ChannelNotFoundError) as e:
                        # All three errors map to appropriate HTTP-like status codes
                        error_code = "NOT_FOUND" if isinstance(e, (ConversationNotFoundError, ChannelNotFoundError)) else "FORBIDDEN"
                        await connection_manager.send_json(
                            websocket,
                            ErrorMessage(
                                message=str(e),
                                code=error_code
                            ).model_dump()
                        )
                        logger.warning(f"Conversation access error for user {current_user.id}: {e}")
                        continue

                # Step 2b: Check if this is a confirmation response (yes/no)
                # CRITICAL: We must save user's message BEFORE triggering background task
                # Otherwise background task may save success message before user's "yes"
                if conversation_id_str and conversation_id_str != "new":
                    # First, just check if this matches a confirmation pattern (don't trigger yet)
                    from app.api.websocket.video_loader import pending_loads

                    pending = pending_loads.get(conversation_id_str)
                    is_confirmation = False

                    if pending and pending.user_id == current_user.id:
                        response_lower = message.content.strip().lower()
                        yes_pattern = r'\b(yes|y|yeah|sure|ok(ay)?|yep|yup|load\s+it)\b'
                        no_pattern = r'\b(no|n|nope|cancel|don\'?t|stop)\b'

                        if re.search(yes_pattern, response_lower) or re.search(no_pattern, response_lower):
                            is_confirmation = True

                    if is_confirmation:
                        # Save user's confirmation message FIRST (before triggering background task)
                        # Note: Confirmation is only for personal conversations (channels block video_load)
                        if isinstance(conversation, ChannelConversation):
                            await message_repo.create(
                                channel_conversation_id=conversation.id,
                                role="user",
                                content=message.content,
                                meta_data={"intent": "video_load_confirmation"}
                            )
                        else:
                            await message_repo.create(
                                conversation_id=conversation.id,
                                role="user",
                                content=message.content,
                                meta_data={"intent": "video_load_confirmation"}
                            )

                        # Commit BEFORE triggering background task
                        conversation.updated_at = datetime.now(timezone.utc)
                        await db.commit()

                        # NOW trigger the confirmation handler (which starts background task)
                        await handle_confirmation_response(
                            response=message.content,
                            conversation_id=conversation_id_str,
                            user_id=current_user.id,
                            db=db,
                            websocket=websocket,
                        )

                        # Confirmation was handled - skip normal message processing
                        continue

                # Step 2c: Update conversation model if provided in message
                if message.model and message.model != conversation.model:
                    logger.info(
                        f"Updating conversation {conversation.id} model from "
                        f"{conversation.model} to {message.model}"
                    )
                    conversation.model = message.model
                    # Note: Will be committed after successful RAG execution (Step 10)

                # Step 3: Load config values from database (via ConfigService)
                config_service = ConfigService(db)
                rag_config = {
                    "top_k": await config_service.get_config("rag.top_k", default=settings.RAG_TOP_K),
                    "context_messages": await config_service.get_config("rag.context_messages", default=settings.RAG_CONTEXT_MESSAGES),
                    "model": conversation.model,  # Per-conversation model selection (may have just been updated above)
                    **state_extras  # Add channel_id + collection_name if channel conversation
                }

                # Step 4: Send status update - classifying
                await connection_manager.send_json(
                    websocket,
                    StatusMessage(
                        message="Classifying your query...",
                        step="routing"
                    ).model_dump()
                )

                # Step 5: Fetch conversation history (last N messages from config)
                # Returns list of dicts: [{"role": str, "content": str}, ...]
                if isinstance(conversation, ChannelConversation):
                    conversation_history = await message_repo.get_last_n(
                        n=rag_config["context_messages"],
                        channel_conversation_id=conversation.id
                    )
                else:
                    conversation_history = await message_repo.get_last_n(
                        n=rag_config["context_messages"],
                        conversation_id=conversation.id
                    )

                # Step 6: Send status update - retrieving
                await connection_manager.send_json(
                    websocket,
                    StatusMessage(
                        message="Searching knowledge base...",
                        step="retrieving"
                    ).model_dump()
                )

                # Step 7: Call run_graph (RAG flow) with config
                result = await run_graph(
                    user_query=message.content,
                    user_id=str(current_user.id),
                    conversation_history=conversation_history,
                    config=rag_config
                )

                # Step 7a: Check if response requires WebSocket handling (video_load)
                if result.get("metadata", {}).get("requires_websocket_handling"):
                    # Block video_load for channel conversations (admin-only feature)
                    if state_extras.get("channel_id"):
                        # Save user's blocked video load attempt
                        if isinstance(conversation, ChannelConversation):
                            await message_repo.create(
                                channel_conversation_id=conversation.id,
                                role="user",
                                content=message.content,
                                meta_data={"intent": "video_load_blocked"}
                            )

                        await connection_manager.send_json(
                            websocket,
                            ErrorMessage(
                                message="Videos can only be added to channels by administrators. "
                                        "Please contact an admin to add this video to the channel.",
                                code="CHANNEL_VIDEO_ADMIN_ONLY"
                            ).model_dump()
                        )

                        conversation.updated_at = datetime.now(timezone.utc)
                        await db.commit()

                        logger.info(
                            f"Blocked video_load for channel conversation {conversation.id} "
                            f"(user {current_user.id})"
                        )
                        continue  # Skip video load handler

                    # Personal conversation - allow video loading
                    # Extract URL and handle it
                    youtube_url = message.content
                    # Extract full URL if it's embedded in text
                    for word in message.content.split():
                        if "youtube.com" in word or "youtu.be" in word:
                            youtube_url = word.strip()
                            break

                    # Save user's video load request to database (for conversation persistence)
                    await message_repo.create(
                        conversation_id=conversation.id,
                        role="user",
                        content=message.content,
                        meta_data={"intent": "video_load", "youtube_url": youtube_url}
                    )

                    await handle_video_load_intent(
                        youtube_url=youtube_url,
                        user=current_user,
                        conversation_id=str(conversation.id),
                        db=db,
                        websocket=websocket,
                    )

                    # Commit user message and conversation timestamp
                    conversation.updated_at = datetime.now(timezone.utc)
                    await db.commit()

                    # Don't send normal response - video_loader handles WebSocket messages
                    continue

                # Step 8: Send status update - generating
                await connection_manager.send_json(
                    websocket,
                    StatusMessage(
                        message="Generating response...",
                        step="generating"
                    ).model_dump()
                )

                # Step 9: Send complete response
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

                # Step 10: Save messages to database
                # Save user and assistant messages (support both personal and channel conversations)
                if isinstance(conversation, ChannelConversation):
                    # Channel conversation
                    await message_repo.create(
                        channel_conversation_id=conversation.id,
                        role="user",
                        content=message.content,
                        meta_data={}
                    )
                    await message_repo.create(
                        channel_conversation_id=conversation.id,
                        role="assistant",
                        content=result.get("response", ""),
                        meta_data=response_metadata
                    )
                else:
                    # Personal conversation
                    await message_repo.create(
                        conversation_id=conversation.id,
                        role="user",
                        content=message.content,
                        meta_data={}
                    )
                    await message_repo.create(
                        conversation_id=conversation.id,
                        role="assistant",
                        content=result.get("response", ""),
                        meta_data=response_metadata
                    )

                # Update conversation timestamp
                conversation.updated_at = datetime.now(timezone.utc)
                await db.commit()

                logger.info(
                    f"Processed message for user {current_user.id}, "
                    f"conversation {conversation.id}, intent: {result.get('intent')}"
                )

            except Exception as e:
                # Error handling: don't save anything, just log and send error
                logger.exception(
                    f"Error processing message for user {current_user.id}: {e}"
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
        logger.exception(f"WebSocket error for user {current_user.id if current_user else 'unknown'}: {e}")

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
