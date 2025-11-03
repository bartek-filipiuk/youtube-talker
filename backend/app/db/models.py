"""
Database Models

SQLAlchemy ORM models for all database tables.
Uses SQLAlchemy 2.0 declarative mapping style with Mapped and mapped_column.
"""

from datetime import datetime
from decimal import Decimal
from typing import List, Optional
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """
    Base class for all database models.

    All models inherit from this class to be tracked by SQLAlchemy
    and included in Alembic migrations.
    """

    pass


class User(Base):
    """
    User accounts with authentication credentials.

    Users own conversations, transcripts, templates, and chunks.
    """

    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("NOW()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("NOW()"))
    role: Mapped[str] = mapped_column(String(50), nullable=False, server_default="user", index=True)
    transcript_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")

    # Relationships
    sessions: Mapped[List["Session"]] = relationship(
        "Session", back_populates="user", cascade="all, delete-orphan"
    )
    conversations: Mapped[List["Conversation"]] = relationship(
        "Conversation", back_populates="user", cascade="all, delete-orphan"
    )
    transcripts: Mapped[List["Transcript"]] = relationship(
        "Transcript", back_populates="user", cascade="all, delete-orphan"
    )
    chunks: Mapped[List["Chunk"]] = relationship(
        "Chunk", back_populates="user", cascade="all, delete-orphan"
    )
    templates: Mapped[List["Template"]] = relationship(
        "Template", back_populates="user", cascade="all, delete-orphan"
    )

    __table_args__ = (
        CheckConstraint(
            "email ~* '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.[A-Za-z]{2,}$'",
            name="check_email_format",
        ),
        CheckConstraint(
            "role IN ('user', 'admin')",
            name="check_user_role",
        ),
    )

    def __repr__(self) -> str:
        return f"<User(id={self.id}, email={self.email})>"


class Session(Base):
    """
    Server-side session management with 7-day expiry.

    Stores hashed session tokens for user authentication.
    """

    __tablename__ = "sessions"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    token_hash: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("NOW()"))

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="sessions")

    def __repr__(self) -> str:
        return f"<Session(id={self.id}, user_id={self.user_id}, expires_at={self.expires_at})>"


# Add index on user_id for sessions
Index("idx_sessions_user_id", Session.user_id)


class Conversation(Base):
    """
    Organize chat messages into separate conversation threads.

    Each conversation belongs to a user and contains multiple messages.
    """

    __tablename__ = "conversations"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("NOW()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("NOW()"))

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="conversations")
    messages: Mapped[List["Message"]] = relationship(
        "Message", back_populates="conversation", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Conversation(id={self.id}, user_id={self.user_id}, title={self.title})>"


# Add indexes on conversations
Index("idx_conversations_user_id", Conversation.user_id)
Index("idx_conversations_updated_at", Conversation.updated_at.desc())


class Message(Base):
    """
    Store complete chat history (user + assistant messages).

    Messages can belong to either personal conversations OR channel conversations,
    enforced by CHECK constraint ensuring exactly one is set.
    Includes metadata for RAG sources.
    """

    __tablename__ = "messages"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    conversation_id: Mapped[Optional[UUID]] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    channel_conversation_id: Mapped[Optional[UUID]] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("channel_conversations.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    role: Mapped[str] = mapped_column(String(50), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    meta_data: Mapped[dict] = mapped_column(
        "metadata", JSONB, nullable=False, server_default=text("'{}'")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("NOW()"), index=True)

    # Relationships
    conversation: Mapped[Optional["Conversation"]] = relationship("Conversation", back_populates="messages")
    channel_conversation: Mapped[Optional["ChannelConversation"]] = relationship(
        "ChannelConversation", back_populates="messages"
    )

    __table_args__ = (
        CheckConstraint(
            "role IN ('user', 'assistant', 'system')",
            name="check_role",
        ),
        CheckConstraint(
            "(conversation_id IS NOT NULL AND channel_conversation_id IS NULL) OR "
            "(conversation_id IS NULL AND channel_conversation_id IS NOT NULL)",
            name="check_message_conversation_type",
        ),
    )

    def __repr__(self) -> str:
        conv_id = self.conversation_id or self.channel_conversation_id
        conv_type = "personal" if self.conversation_id else "channel"
        return f"<Message(id={self.id}, {conv_type}_conversation_id={conv_id}, role={self.role})>"


# Add GIN index on metadata JSONB column
Index("idx_messages_metadata", Message.meta_data, postgresql_using="gin")


class Transcript(Base):
    """
    Store full YouTube video transcriptions with metadata.

    Transcripts are chunked for RAG retrieval and belong to users.
    """

    __tablename__ = "transcripts"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    youtube_video_id: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True
    )
    title: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    channel_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    duration: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    transcript_text: Mapped[str] = mapped_column(Text, nullable=False)
    meta_data: Mapped[dict] = mapped_column(
        "metadata", JSONB, nullable=False, server_default=text("'{}'")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("NOW()"))

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="transcripts")
    chunks: Mapped[List["Chunk"]] = relationship(
        "Chunk", back_populates="transcript", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("unique_user_video", "user_id", "youtube_video_id", unique=True),
        Index("idx_transcripts_user_id", "user_id"),
        Index("idx_transcripts_metadata", "metadata", postgresql_using="gin"),
    )

    def __repr__(self) -> str:
        return f"<Transcript(id={self.id}, youtube_video_id={self.youtube_video_id}, title={self.title})>"


class Chunk(Base):
    """
    Store chunked transcript segments for RAG retrieval.

    Chunks can belong to either a user OR a channel, enforced by CHECK constraint.
    Chunks are created from transcripts and stored with embeddings in Qdrant.
    user_id/channel_id is denormalized for faster lookups.
    """

    __tablename__ = "chunks"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    transcript_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("transcripts.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[Optional[UUID]] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
        comment="Denormalized for fast lookups. RESTRICT prevents multi-cascade path conflict with transcript FK.",
    )
    channel_id: Mapped[Optional[UUID]] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("channels.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
        comment="Denormalized for fast channel chunk lookups.",
    )
    chunk_text: Mapped[str] = mapped_column(Text, nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    token_count: Mapped[int] = mapped_column(Integer, nullable=False)
    meta_data: Mapped[dict] = mapped_column(
        "metadata", JSONB, nullable=False, server_default=text("'{}'")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("NOW()"))

    # Relationships
    transcript: Mapped["Transcript"] = relationship("Transcript", back_populates="chunks")
    user: Mapped[Optional["User"]] = relationship("User", back_populates="chunks")
    channel: Mapped[Optional["Channel"]] = relationship("Channel", back_populates="chunks")

    __table_args__ = (
        Index("unique_chunk_index", "transcript_id", "chunk_index", unique=True),
        Index("idx_chunks_transcript_id", "transcript_id"),
        Index("idx_chunks_metadata", "metadata", postgresql_using="gin"),
        CheckConstraint(
            "(user_id IS NOT NULL AND channel_id IS NULL) OR "
            "(user_id IS NULL AND channel_id IS NOT NULL)",
            name="check_chunk_ownership",
        ),
    )

    def __repr__(self) -> str:
        owner_id = self.user_id or self.channel_id
        owner_type = "user" if self.user_id else "channel"
        return f"<Chunk(id={self.id}, {owner_type}_id={owner_id}, transcript_id={self.transcript_id}, chunk_index={self.chunk_index})>"


class Template(Base):
    """
    Store content generation templates (LinkedIn, Twitter, etc.).

    Templates can be user-specific or system defaults (user_id=NULL).

    MVP Note: template_type validation is handled in application layer (Pydantic).
    This allows flexible addition of new content types post-MVP without database migrations.
    """

    __tablename__ = "templates"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[Optional[UUID]] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=True
    )
    template_type: Mapped[str] = mapped_column(String(50), nullable=False)
    template_name: Mapped[str] = mapped_column(String(255), nullable=False)
    template_content: Mapped[str] = mapped_column(Text, nullable=False)
    variables: Mapped[list] = mapped_column(JSONB, nullable=False, server_default=text("'[]'"))
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("FALSE"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("NOW()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("NOW()"))

    # Relationships
    user: Mapped[Optional["User"]] = relationship("User", back_populates="templates")

    __table_args__ = (
        Index("unique_user_template", "user_id", "template_type", "template_name", unique=True),
        Index("idx_templates_type_default", "template_type", "is_default"),
        # Note: No CHECK constraint on template_type for MVP extensibility
        # Validation is performed in Pydantic schemas
    )

    def __repr__(self) -> str:
        return f"<Template(id={self.id}, template_type={self.template_type}, template_name={self.template_name})>"


# Add index on user_id for templates (nullable)
Index("idx_templates_user_id", Template.user_id)


class Config(Base):
    """
    System-wide configuration settings.

    Stores configuration values as JSONB for flexibility.
    """

    __tablename__ = "config"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[dict] = mapped_column(JSONB, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("NOW()"))

    def __repr__(self) -> str:
        return f"<Config(key={self.key}, value={self.value})>"


class ModelPricing(Base):
    """
    Store pricing configuration for AI models and external APIs.

    Supports multiple pricing models:
    - per_token: LLM models (OpenRouter, OpenAI)
    - per_request: API calls (SUPADATA)

    Pricing is versioned using effective_from/effective_until for historical tracking.
    """

    __tablename__ = "model_pricing"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    provider: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    model_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    pricing_type: Mapped[str] = mapped_column(
        String(20), nullable=False, comment="per_token, per_request, credit_based"
    )
    input_price_per_1m: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 6), nullable=True, comment="For per_token models: cost per 1M input tokens"
    )
    output_price_per_1m: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 6), nullable=True, comment="For per_token models: cost per 1M output tokens"
    )
    cost_per_request: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 6), nullable=True, comment="For per_request models: fixed cost per API call"
    )
    cache_discount: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 4), nullable=True, comment="Multiplier for cached tokens (e.g., 0.25 for 75% discount)"
    )
    effective_from: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("NOW()")
    )
    effective_until: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("TRUE"))
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("NOW()"))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("NOW()"), onupdate=text("NOW()")
    )

    __table_args__ = (
        Index(
            "unique_model_pricing",
            "provider",
            "model_name",
            "effective_from",
            unique=True,
        ),
        Index("idx_model_pricing_lookup", "provider", "model_name", "is_active"),
        CheckConstraint(
            "pricing_type IN ('per_token', 'per_request', 'credit_based')",
            name="check_pricing_type",
        ),
    )

    def __repr__(self) -> str:
        return f"<ModelPricing(id={self.id}, provider={self.provider}, model_name={self.model_name}, pricing_type={self.pricing_type})>"


class Channel(Base):
    """
    Admin-managed content channels for curated YouTube video collections.

    Each channel has a unique name (URL slug), dedicated Qdrant collection,
    and can contain unlimited videos. Supports soft delete via is_active flag.
    """

    __tablename__ = "channels"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    name: Mapped[str] = mapped_column(
        String(100), nullable=False, unique=True, index=True, comment="Immutable URL slug"
    )
    display_title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    qdrant_collection_name: Mapped[str] = mapped_column(
        String(100), nullable=False, index=True, comment="Sanitized collection name for Qdrant"
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("TRUE"), index=True)
    created_by: Mapped[Optional[UUID]] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("NOW()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("NOW()"))

    # Relationships
    videos: Mapped[List["ChannelVideo"]] = relationship(
        "ChannelVideo", back_populates="channel", cascade="all, delete-orphan"
    )
    conversations: Mapped[List["ChannelConversation"]] = relationship(
        "ChannelConversation", back_populates="channel", cascade="all, delete-orphan"
    )
    chunks: Mapped[List["Chunk"]] = relationship(
        "Chunk", back_populates="channel", cascade="all, delete-orphan"
    )
    creator: Mapped[Optional["User"]] = relationship("User", foreign_keys=[created_by])

    def __repr__(self) -> str:
        return f"<Channel(id={self.id}, name={self.name}, is_active={self.is_active})>"


class ChannelVideo(Base):
    """
    Association table linking channels to transcripts (videos).

    Tracks which videos are loaded into which channels, who added them, and when.
    Prevents duplicate videos per channel via unique constraint.
    """

    __tablename__ = "channel_videos"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    channel_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("channels.id", ondelete="CASCADE"), nullable=False, index=True
    )
    transcript_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("transcripts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    added_by: Mapped[Optional[UUID]] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("NOW()"))

    # Relationships
    channel: Mapped["Channel"] = relationship("Channel", back_populates="videos")
    transcript: Mapped["Transcript"] = relationship("Transcript")
    adder: Mapped[Optional["User"]] = relationship("User", foreign_keys=[added_by])

    __table_args__ = (Index("uq_channel_video", "channel_id", "transcript_id", unique=True),)

    def __repr__(self) -> str:
        return f"<ChannelVideo(id={self.id}, channel_id={self.channel_id}, transcript_id={self.transcript_id})>"


class ChannelConversation(Base):
    """
    Per-user conversation threads within channels.

    Each user has their own separate conversation history per channel.
    Prevents duplicate conversations via unique constraint on (channel_id, user_id).
    """

    __tablename__ = "channel_conversations"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    channel_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("channels.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("NOW()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("NOW()"))

    # Relationships
    channel: Mapped["Channel"] = relationship("Channel", back_populates="conversations")
    user: Mapped["User"] = relationship("User")
    messages: Mapped[List["Message"]] = relationship(
        "Message", back_populates="channel_conversation", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("uq_channel_user", "channel_id", "user_id", unique=True),
        Index("idx_channel_conversations_channel_user", "channel_id", "user_id"),
        Index("idx_channel_conversations_updated_at", "updated_at", postgresql_ops={"updated_at": "DESC"}),
    )

    def __repr__(self) -> str:
        return f"<ChannelConversation(id={self.id}, channel_id={self.channel_id}, user_id={self.user_id})>"
