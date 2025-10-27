"""
Database Models

SQLAlchemy ORM models for all database tables.
Uses SQLAlchemy 2.0 declarative mapping style with Mapped and mapped_column.
"""

from datetime import datetime
from typing import List, Optional
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
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
    created_at: Mapped[datetime] = mapped_column(server_default=text("NOW()"))
    updated_at: Mapped[datetime] = mapped_column(server_default=text("NOW()"))
    role: Mapped[str] = mapped_column(String(50), nullable=False, server_default=text("user"), index=True)
    transcript_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))

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
    expires_at: Mapped[datetime] = mapped_column(nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(server_default=text("NOW()"))

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
    created_at: Mapped[datetime] = mapped_column(server_default=text("NOW()"))
    updated_at: Mapped[datetime] = mapped_column(server_default=text("NOW()"))

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

    Messages belong to conversations and include metadata for RAG sources.
    """

    __tablename__ = "messages"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    conversation_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role: Mapped[str] = mapped_column(String(50), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    meta_data: Mapped[dict] = mapped_column(
        "metadata", JSONB, nullable=False, server_default=text("'{}'")
    )
    created_at: Mapped[datetime] = mapped_column(server_default=text("NOW()"), index=True)

    # Relationships
    conversation: Mapped["Conversation"] = relationship("Conversation", back_populates="messages")

    __table_args__ = (
        CheckConstraint(
            "role IN ('user', 'assistant', 'system')",
            name="check_role",
        ),
    )

    def __repr__(self) -> str:
        return f"<Message(id={self.id}, conversation_id={self.conversation_id}, role={self.role})>"


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
    created_at: Mapped[datetime] = mapped_column(server_default=text("NOW()"))

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

    Chunks are created from transcripts and stored with embeddings in Qdrant.
    user_id is denormalized for faster lookups.
    """

    __tablename__ = "chunks"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    transcript_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("transcripts.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    chunk_text: Mapped[str] = mapped_column(Text, nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    token_count: Mapped[int] = mapped_column(Integer, nullable=False)
    meta_data: Mapped[dict] = mapped_column(
        "metadata", JSONB, nullable=False, server_default=text("'{}'")
    )
    created_at: Mapped[datetime] = mapped_column(server_default=text("NOW()"))

    # Relationships
    transcript: Mapped["Transcript"] = relationship("Transcript", back_populates="chunks")
    user: Mapped["User"] = relationship("User", back_populates="chunks")

    __table_args__ = (
        Index("unique_chunk_index", "transcript_id", "chunk_index", unique=True),
        Index("idx_chunks_transcript_id", "transcript_id"),
        Index("idx_chunks_metadata", "metadata", postgresql_using="gin"),
    )

    def __repr__(self) -> str:
        return f"<Chunk(id={self.id}, transcript_id={self.transcript_id}, chunk_index={self.chunk_index})>"


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
    created_at: Mapped[datetime] = mapped_column(server_default=text("NOW()"))
    updated_at: Mapped[datetime] = mapped_column(server_default=text("NOW()"))

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
    updated_at: Mapped[datetime] = mapped_column(server_default=text("NOW()"))

    def __repr__(self) -> str:
        return f"<Config(key={self.key}, value={self.value})>"
