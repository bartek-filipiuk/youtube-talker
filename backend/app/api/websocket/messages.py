"""
WebSocket Message Schemas

Pydantic models for WebSocket message validation and serialization.
"""

from typing import Dict, List, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class IncomingMessage(BaseModel):
    """
    Message from client to server.

    User sends query and specifies which conversation to use.
    conversation_id of "new" or null triggers auto-creation.
    """

    conversation_id: Optional[str] = Field(
        None,
        description="Conversation UUID or 'new' to create new conversation"
    )
    content: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="User message content (max 2000 chars)"
    )
    model: Optional[str] = Field(
        None,
        description="LLM model to use (claude-haiku-4.5 or gemini-2.5-flash). If not provided, uses conversation's saved model."
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "conversation_id": "123e4567-e89b-12d3-a456-426614174000",
                "content": "What is FastAPI?"
            }
        }
    )


class StatusMessage(BaseModel):
    """
    Progress update message from server to client.

    Sent during RAG flow execution to show processing steps.
    """

    type: Literal["status"] = "status"
    message: str = Field(..., description="Human-readable status message")
    step: Literal["routing", "retrieving", "grading", "generating", "checking"] = Field(
        ...,
        description="Current processing step"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "type": "status",
                "message": "Searching knowledge base...",
                "step": "retrieving"
            }
        }
    )


class AssistantMessage(BaseModel):
    """
    Complete response message from server to client.

    Sent when RAG flow completes successfully.
    """

    type: Literal["message"] = "message"
    role: Literal["assistant"] = "assistant"
    content: str = Field(..., description="HTML-formatted response content")
    metadata: Dict = Field(
        default_factory=dict,
        description="Response metadata (intent, chunks_used, sources, etc.)"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "type": "message",
                "role": "assistant",
                "content": "<p>FastAPI is a modern web framework for Python...</p>",
                "metadata": {
                    "intent": "qa",
                    "chunks_used": 5,
                    "source_chunks": ["chunk-id-1", "chunk-id-2"],
                    "conversation_id": "123e4567-e89b-12d3-a456-426614174000"
                }
            }
        }
    )


class ErrorMessage(BaseModel):
    """
    Error message from server to client.

    Sent when request fails or validation error occurs.
    """

    type: Literal["error"] = "error"
    message: str = Field(..., description="User-friendly error message")
    code: str = Field(..., description="Error code for client handling")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "type": "error",
                "message": "Something went wrong. Please try again.",
                "code": "LLM_ERROR"
            }
        }
    )


class PingMessage(BaseModel):
    """
    Heartbeat ping message (bidirectional).

    Used to keep connection alive and detect dead connections.
    """

    type: Literal["ping"] = "ping"

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "type": "ping"
            }
        }
    )


class PongMessage(BaseModel):
    """
    Heartbeat pong response (server to client).

    Response to ping message to confirm connection is alive.
    """

    type: Literal["pong"] = "pong"

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "type": "pong"
            }
        }
    )


class LoadVideoConfirmationMessage(BaseModel):
    """
    Video load confirmation request (server to client).

    Server asks user to confirm whether to load a detected YouTube video.
    """

    type: Literal["video_load_confirmation"] = "video_load_confirmation"
    youtube_url: str = Field(..., description="Full YouTube URL detected")
    video_id: str = Field(..., description="Extracted video ID (11 chars)")
    video_title: Optional[str] = Field(
        None,
        description="Video title from YouTube (if available)"
    )
    message: str = Field(
        ...,
        description="Confirmation prompt message for user"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "type": "video_load_confirmation",
                "youtube_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                "video_id": "dQw4w9WgXcQ",
                "video_title": "Rick Astley - Never Gonna Give You Up",
                "message": "Load this video to your knowledge base? Reply 'yes' or 'no'."
            }
        }
    )


class LoadVideoResponseMessage(BaseModel):
    """
    Video load confirmation response (client to server).

    Client confirms or rejects video loading request.
    """

    type: Literal["video_load_response"] = "video_load_response"
    confirmed: bool = Field(..., description="True for yes, False for no")
    conversation_id: str = Field(..., description="Conversation UUID")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "type": "video_load_response",
                "confirmed": True,
                "conversation_id": "123e4567-e89b-12d3-a456-426614174000"
            }
        }
    )


class VideoLoadStatusMessage(BaseModel):
    """
    Video load status update (server to client).

    Server notifies about video loading progress or completion.
    """

    type: Literal["video_load_status"] = "video_load_status"
    status: Literal["started", "completed", "failed"] = Field(
        ...,
        description="Current status of video loading"
    )
    message: str = Field(..., description="Status message for user")
    video_title: Optional[str] = Field(
        None,
        description="Video title (if available)"
    )
    error: Optional[str] = Field(
        None,
        description="Error code (only present when status=failed). Possible values: "
                    "INVALID_URL, DUPLICATE_VIDEO, QUOTA_EXCEEDED, DURATION_EXCEEDED, "
                    "DURATION_UNAVAILABLE, DURATION_CHECK_FAILED, USER_CANCELLED"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "type": "video_load_status",
                "status": "completed",
                "message": "Video loaded successfully to your knowledge base!",
                "video_title": "Rick Astley - Never Gonna Give You Up",
                "error": None
            }
        }
    )
