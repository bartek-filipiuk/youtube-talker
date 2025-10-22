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
    step: Literal["routing", "retrieving", "grading", "generating"] = Field(
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
