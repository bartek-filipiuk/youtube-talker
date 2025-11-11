"""
Conversation API Schemas

Pydantic models for conversation CRUD operations.
"""

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, ConfigDict, field_validator

from app.config import settings


class ConversationCreateRequest(BaseModel):
    """
    Request schema for creating a new conversation.

    Attributes:
        title: Optional conversation title (max 200 chars)
               If not provided, auto-generated title will be used
        model: Optional AI model selection (defaults to "claude-haiku-4.5")
               Must be one of the available models
    """

    title: Optional[str] = Field(
        None,
        max_length=200,
        description="Conversation title (auto-generated if not provided)"
    )
    model: Optional[str] = Field(
        None,
        max_length=50,
        description="AI model to use (defaults to claude-haiku-4.5)"
    )

    @field_validator('model')
    @classmethod
    def validate_model(cls, v: Optional[str]) -> Optional[str]:
        """Validate model against available models."""
        if v is not None and v not in settings.AVAILABLE_MODELS:
            raise ValueError(
                f"Model must be one of {settings.AVAILABLE_MODELS}, got '{v}'"
            )
        return v


class ConversationUpdateRequest(BaseModel):
    """
    Request schema for updating a conversation.

    Attributes:
        title: Conversation title (1-100 chars, optional)
        model: AI model selection (optional, can only change before first message)
    """

    title: Optional[str] = Field(
        None,
        min_length=1,
        max_length=100,
        description="Updated conversation title"
    )
    model: Optional[str] = Field(
        None,
        max_length=50,
        description="AI model (can only change before first message)"
    )

    @field_validator('model')
    @classmethod
    def validate_model(cls, v: Optional[str]) -> Optional[str]:
        """Validate model against available models."""
        if v is not None and v not in settings.AVAILABLE_MODELS:
            raise ValueError(
                f"Model must be one of {settings.AVAILABLE_MODELS}, got '{v}'"
            )
        return v


class ConversationResponse(BaseModel):
    """
    Response schema for conversation data (without messages).

    Used in list views and after create/update operations.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(description="Conversation UUID")
    user_id: UUID = Field(description="Owner user UUID")
    title: str = Field(description="Conversation title")
    model: str = Field(description="AI model used for this conversation")
    created_at: datetime = Field(description="Creation timestamp")
    updated_at: datetime = Field(description="Last update timestamp")


class MessageResponse(BaseModel):
    """
    Response schema for message data.

    Used within conversation detail views (both personal and channel conversations).
    Messages belong to either conversation_id OR channel_conversation_id (exactly one must be set).
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(description="Message UUID")
    conversation_id: Optional[UUID] = Field(None, description="Parent conversation UUID (personal conversations)")
    channel_conversation_id: Optional[UUID] = Field(None, description="Parent channel conversation UUID (channel conversations)")
    role: str = Field(description="Message role: 'user' or 'assistant'")
    content: str = Field(description="Message content")
    meta_data: dict = Field(default_factory=dict, description="Optional metadata (intent, sources, etc.)")
    created_at: datetime = Field(description="Creation timestamp")


class ConversationDetailResponse(BaseModel):
    """
    Response schema for conversation detail with messages.

    Used in GET /api/conversations/{id} endpoint.
    Includes full conversation data plus all associated messages.
    """

    conversation: ConversationResponse = Field(description="Conversation metadata")
    messages: List[MessageResponse] = Field(
        default_factory=list,
        description="List of messages in chronological order"
    )


class ConversationListResponse(BaseModel):
    """
    Response schema for paginated conversation list.

    Used in GET /api/conversations endpoint.
    """

    conversations: List[ConversationResponse] = Field(
        default_factory=list,
        description="List of conversations (most recent first)"
    )
    total: int = Field(description="Total number of conversations returned")
    limit: int = Field(description="Pagination limit used")
    offset: int = Field(description="Pagination offset used")
