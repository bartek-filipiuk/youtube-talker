"""
Conversation API Schemas

Pydantic models for conversation CRUD operations.
"""

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, ConfigDict


class ConversationCreateRequest(BaseModel):
    """
    Request schema for creating a new conversation.

    Attributes:
        title: Optional conversation title (max 200 chars)
               If not provided, auto-generated title will be used
    """

    title: Optional[str] = Field(
        None,
        max_length=200,
        description="Conversation title (auto-generated if not provided)"
    )


class ConversationResponse(BaseModel):
    """
    Response schema for conversation data (without messages).

    Used in list views and after create/update operations.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(description="Conversation UUID")
    user_id: UUID = Field(description="Owner user UUID")
    title: str = Field(description="Conversation title")
    created_at: datetime = Field(description="Creation timestamp")
    updated_at: datetime = Field(description="Last update timestamp")


class MessageResponse(BaseModel):
    """
    Response schema for message data.

    Used within conversation detail views.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(description="Message UUID")
    conversation_id: UUID = Field(description="Parent conversation UUID")
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
