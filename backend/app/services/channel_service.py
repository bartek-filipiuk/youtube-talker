"""
Channel Service

Business logic for channel management including CRUD operations,
video ingestion, and Qdrant collection management.
"""

import uuid
from typing import Dict, List, Optional, Tuple, Any
from uuid import UUID

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import (
    ChannelAlreadyExistsError,
    ChannelNotFoundError,
    VideoAlreadyInChannelError,
    VideoNotInChannelError,
)
from app.db.repositories.channel_repo import ChannelRepository
from app.db.repositories.channel_video_repo import ChannelVideoRepository
from app.db.repositories.channel_conversation_repo import ChannelConversationRepository
from app.db.repositories.transcript_repo import TranscriptRepository
from app.db.repositories.chunk_repo import ChunkRepository
from app.db.models import Channel, ChannelVideo, ChannelConversation
from app.services.qdrant_service import QdrantService
from app.services.transcript_service import TranscriptService
from app.services.chunking_service import ChunkingService
from app.services.embedding_service import EmbeddingService
from app.services.config_service import ConfigService
from app.config import settings


class ChannelService:
    """
    Business logic for channel management.

    Orchestrates repositories, Qdrant, and external services for
    channel CRUD operations and video ingestion.
    """

    def __init__(self, db: AsyncSession):
        """
        Initialize ChannelService with database session.

        Args:
            db: AsyncSession for database operations
        """
        self.db = db
        self.channel_repo = ChannelRepository(db)
        self.channel_video_repo = ChannelVideoRepository(db)
        self.channel_conversation_repo = ChannelConversationRepository(db)
        self.transcript_repo = TranscriptRepository(db)
        self.chunk_repo = ChunkRepository(db)
        self.qdrant_service = QdrantService()

    async def create_channel(
        self,
        name: str,
        display_title: str,
        description: Optional[str],
        created_by: UUID,
    ) -> Channel:
        """
        Create new channel with Qdrant collection.

        Steps:
            1. Sanitize name for Qdrant collection
            2. Check if channel name already exists
            3. Create Qdrant collection (eager)
            4. Create channel in PostgreSQL
            5. Commit transaction

        Args:
            name: URL-safe channel name (lowercase, numbers, hyphens)
            display_title: Human-readable channel title
            description: Optional channel description
            created_by: UUID of admin user creating the channel

        Returns:
            Channel: Created channel instance

        Raises:
            ValueError: Channel name already exists
            Exception: Qdrant collection creation failed
        """
        # Sanitize collection name
        collection_name = QdrantService.sanitize_collection_name(f"channel_{name}")
        logger.info(f"Creating channel '{name}' with collection '{collection_name}'")

        # Check if channel name already exists
        existing = await self.channel_repo.get_by_name(name)
        if existing:
            raise ChannelAlreadyExistsError(f"Channel with name '{name}' already exists")

        # Create Qdrant collection (eager)
        try:
            await self.qdrant_service.create_channel_collection(collection_name)
            logger.info(f"✓ Created Qdrant collection: {collection_name}")
        except Exception as e:
            logger.error(f"Failed to create Qdrant collection: {e}")
            raise

        # Create channel in DB
        try:
            channel = await self.channel_repo.create(
                name=name,
                display_title=display_title,
                description=description,
                created_by=created_by,
                qdrant_collection_name=collection_name,
            )
            await self.db.commit()
            logger.info(f"✓ Created channel: {channel.id}")
            return channel
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Failed to create channel in database: {e}")
            # TODO: Consider cleanup of Qdrant collection on failure
            raise

    async def update_channel(
        self,
        channel_id: UUID,
        display_title: Optional[str] = None,
        description: Optional[str] = None,
    ) -> Channel:
        """
        Update channel metadata.

        Note: Channel name cannot be changed (immutable for Qdrant collection consistency).

        Args:
            channel_id: UUID of channel to update
            display_title: Optional new display title
            description: Optional new description

        Returns:
            Channel: Updated channel instance

        Raises:
            ValueError: No fields to update or channel not found
        """
        updates = {}
        if display_title is not None:
            updates["display_title"] = display_title
        if description is not None:
            updates["description"] = description

        if not updates:
            raise ValueError("No fields to update")

        channel = await self.channel_repo.update(channel_id, **updates)
        await self.db.commit()
        logger.info(f"✓ Updated channel: {channel_id}")
        return channel

    async def soft_delete_channel(self, channel_id: UUID) -> None:
        """
        Soft delete channel (preserve data, mark as deleted).

        Args:
            channel_id: UUID of channel to soft delete

        Raises:
            ValueError: Channel not found
        """
        await self.channel_repo.soft_delete(channel_id)
        await self.db.commit()
        logger.info(f"✓ Soft deleted channel: {channel_id}")

    async def reactivate_channel(self, channel_id: UUID) -> Channel:
        """
        Reactivate soft-deleted channel.

        Args:
            channel_id: UUID of channel to reactivate

        Returns:
            Channel: Reactivated channel instance

        Raises:
            ValueError: Channel not found or not deleted
        """
        channel = await self.channel_repo.reactivate(channel_id)
        await self.db.commit()
        logger.info(f"✓ Reactivated channel: {channel_id}")
        return channel

    async def get_channel(self, channel_id: UUID) -> Channel:
        """
        Get channel by ID.

        Args:
            channel_id: UUID of channel

        Returns:
            Channel: Channel instance

        Raises:
            ValueError: Channel not found
        """
        channel = await self.channel_repo.get_by_id(channel_id)
        if not channel:
            raise ChannelNotFoundError(f"Channel {channel_id} not found")
        return channel

    async def get_channel_by_name(self, name: str) -> Channel:
        """
        Get channel by URL-safe name.

        Args:
            name: URL-safe channel name

        Returns:
            Channel: Channel instance

        Raises:
            ValueError: Channel not found
        """
        channel = await self.channel_repo.get_by_name(name)
        if not channel:
            raise ChannelNotFoundError(f"Channel '{name}' not found")
        return channel

    async def list_channels(
        self,
        limit: int = 50,
        offset: int = 0,
        include_deleted: bool = False,
    ) -> Tuple[List[Channel], int]:
        """
        List channels with pagination.

        Args:
            limit: Maximum number of channels to return
            offset: Number of channels to skip
            include_deleted: Include soft-deleted channels

        Returns:
            Tuple[List[Channel], int]: (channels, total_count)
        """
        if include_deleted:
            return await self.channel_repo.list_all(limit=limit, offset=offset)
        else:
            return await self.channel_repo.list_active(limit=limit, offset=offset)

    async def get_channel_video_count(self, channel_id: UUID) -> int:
        """
        Get total video count for channel.

        Args:
            channel_id: UUID of channel

        Returns:
            int: Total number of videos in channel
        """
        return await self.channel_video_repo.count_by_channel(channel_id)

    async def list_channel_videos(
        self,
        channel_id: UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[ChannelVideo], int]:
        """
        List videos in channel with pagination.

        Args:
            channel_id: UUID of channel
            limit: Maximum number of videos to return
            offset: Number of videos to skip

        Returns:
            Tuple[List[ChannelVideo], int]: (videos, total_count)
        """
        return await self.channel_video_repo.list_by_channel(
            channel_id=channel_id,
            limit=limit,
            offset=offset,
        )

    async def add_video_to_channel(
        self,
        channel_id: UUID,
        youtube_url: str,
        admin_user_id: UUID,
    ) -> Dict[str, Any]:
        """
        Ingest YouTube video into channel collection.

        Full pipeline:
            1. Get channel and validate
            2. Extract video ID from URL
            3. Check if video already in channel
            4. Fetch transcript from SUPADATA API
            5. Create Transcript record (owned by admin)
            6. Chunk transcript text
            7. Generate embeddings
            8. Save chunks to PostgreSQL (with channel_id)
            9. Upsert vectors to channel's Qdrant collection
            10. Create ChannelVideo association
            11. Commit transaction

        Args:
            channel_id: Target channel UUID
            youtube_url: YouTube video URL
            admin_user_id: Admin user adding the video

        Returns:
            Dict with transcript_id, youtube_video_id, chunk_count, metadata

        Raises:
            ValueError: Channel not found, video already in channel
            Exception: SUPADATA API error, ingestion failure
        """
        logger.info(f"Adding video to channel {channel_id}: {youtube_url}")

        try:
            # Step 1: Get channel
            channel = await self.get_channel(channel_id)
            logger.info(f"✓ Channel found: {channel.name}")

            # Step 2: Extract video ID
            transcript_service = TranscriptService()
            youtube_video_id = transcript_service._extract_video_id(youtube_url)
            logger.info(f"✓ Extracted video ID: {youtube_video_id}")

            # Step 3: Check if video already in channel
            existing_transcript = await self.transcript_repo.get_by_youtube_video_id(
                youtube_video_id
            )
            if existing_transcript:
                video_exists = await self.channel_video_repo.video_exists(
                    channel_id, existing_transcript.id
                )
                if video_exists:
                    raise VideoAlreadyInChannelError(
                        f"Video {youtube_video_id} already exists in channel"
                    )

            # Step 4: Fetch transcript from SUPADATA
            logger.info("Fetching transcript from SUPADATA...")
            transcript_data = await transcript_service.fetch_transcript(
                youtube_url,
                user_id=str(admin_user_id)
            )
            transcript_text = transcript_data["transcript_text"]
            metadata = transcript_data["metadata"]
            logger.info(f"✓ Fetched transcript ({len(transcript_text)} chars)")

            # Step 5: Create Transcript record
            logger.info("Creating transcript record...")
            transcript = await self.transcript_repo.create(
                user_id=str(admin_user_id),  # Owned by admin
                youtube_video_id=youtube_video_id,
                title=metadata.get("title"),
                channel_name=metadata.get("channel", metadata.get("channel_name")),
                duration=metadata.get("duration"),
                transcript_text=transcript_text,
                meta_data=metadata,
            )
            transcript_id = str(transcript.id)
            logger.info(f"✓ Created transcript: {transcript_id}")

            # Step 6: Load chunking config and chunk text
            logger.info("Chunking transcript...")
            config_service = ConfigService(self.db)
            chunk_size = await config_service.get_config(
                "rag.chunk_size",
                default=settings.CHUNK_SIZE
            )
            overlap_percent = await config_service.get_config(
                "rag.chunk_overlap_percent",
                default=settings.CHUNK_OVERLAP_PERCENT
            )

            chunking_service = ChunkingService(
                chunk_size=chunk_size,
                overlap_percent=overlap_percent,
            )
            chunks = chunking_service.chunk_text(transcript_text)
            logger.info(f"✓ Created {len(chunks)} chunks")

            # Step 7: Generate embeddings
            logger.info("Generating embeddings...")
            embedding_service = EmbeddingService()
            chunk_texts = [chunk["text"] for chunk in chunks]
            embeddings = await embedding_service.generate_embeddings(
                chunk_texts,
                user_id=str(admin_user_id),
            )
            logger.info(f"✓ Generated {len(embeddings)} embeddings")

            # Step 8: Save chunks to PostgreSQL with channel_id
            logger.info("Saving chunks to PostgreSQL...")
            chunks_data = [
                {
                    "id": str(uuid.uuid4()),
                    "transcript_id": transcript_id,
                    "user_id": None,  # Channel chunks have no user_id (constraint enforcement)
                    "chunk_index": chunk["index"],
                    "chunk_text": chunk["text"],
                    "token_count": chunk["token_count"],
                    "channel_id": str(channel_id),  # Associate with channel
                }
                for chunk in chunks
            ]
            saved_chunks = await self.chunk_repo.create_many(chunks_data)
            logger.info(f"✓ Saved {len(saved_chunks)} chunks")

            # Step 9: Upsert to channel's Qdrant collection
            logger.info("Upserting to Qdrant...")
            try:
                chunk_ids = [chunk["id"] for chunk in chunks_data]
                chunk_indices = [chunk["chunk_index"] for chunk in chunks_data]

                await self.qdrant_service.upsert_chunks(
                    chunk_ids=chunk_ids,
                    vectors=embeddings,
                    user_id=str(admin_user_id),  # Not used for channel collections
                    youtube_video_id=youtube_video_id,
                    chunk_indices=chunk_indices,
                    chunk_texts=chunk_texts,
                    collection_name=channel.qdrant_collection_name,  # Channel collection
                    channel_id=str(channel_id),  # Add channel_id to payload
                )
                logger.info(f"✓ Upserted {len(chunk_ids)} vectors to Qdrant")
            except Exception as e:
                logger.exception(f"⚠ Qdrant upsert failed: {e}")
                # Continue - Qdrant is best-effort

            # Step 10: Create ChannelVideo association
            logger.info("Creating channel-video association...")
            await self.channel_video_repo.add_video(
                channel_id=channel_id,
                transcript_id=UUID(transcript_id),
                added_by=admin_user_id,
            )
            logger.info("✓ Created channel-video association")

            # Step 11: Commit
            await self.db.commit()
            logger.info("✓ Transaction committed")

            logger.info(
                f"✓✓✓ Video added to channel: {youtube_video_id} → {channel.name}"
            )

            return {
                "transcript_id": transcript_id,
                "youtube_video_id": youtube_video_id,
                "chunk_count": len(chunks),
                "metadata": metadata,
            }

        except ValueError as e:
            await self.db.rollback()
            logger.warning(f"Validation error: {e}")
            raise
        except Exception as e:
            await self.db.rollback()
            logger.exception(f"✗ Failed to add video to channel: {e}")
            raise

    async def remove_video_from_channel(
        self,
        channel_id: UUID,
        transcript_id: UUID,
    ) -> None:
        """
        Remove video from channel.

        Steps:
            1. Verify video is in channel
            2. Get channel for collection name
            3. Get all chunk IDs for this transcript + channel
            4. Delete chunks from Qdrant (channel collection)
            5. Delete chunks from PostgreSQL (where channel_id matches)
            6. Remove ChannelVideo association
            7. Commit

        Note: Transcript record remains if used elsewhere.

        Args:
            channel_id: UUID of channel
            transcript_id: UUID of transcript to remove

        Raises:
            ValueError: Video not in channel
        """
        logger.info(f"Removing video {transcript_id} from channel {channel_id}")

        try:
            # Verify video exists in channel
            if not await self.channel_video_repo.video_exists(channel_id, transcript_id):
                raise VideoNotInChannelError(
                    f"Video {transcript_id} not found in channel {channel_id}"
                )

            # Get channel for collection name
            channel = await self.get_channel(channel_id)

            # Get chunk IDs for this transcript + channel
            chunks = await self.chunk_repo.list_by_transcript_and_channel(
                transcript_id=transcript_id,
                channel_id=channel_id,
            )
            chunk_ids = [str(chunk.id) for chunk in chunks]
            logger.info(f"Found {len(chunk_ids)} chunks to delete")

            # Delete from Qdrant
            if chunk_ids:
                try:
                    await self.qdrant_service.delete_chunks(
                        chunk_ids=chunk_ids,
                        collection_name=channel.qdrant_collection_name,
                    )
                    logger.info(f"✓ Deleted {len(chunk_ids)} vectors from Qdrant")
                except Exception as e:
                    logger.exception(f"⚠ Qdrant deletion failed: {e}")
                    # Continue - best-effort

            # Delete chunks from PostgreSQL
            deleted_count = await self.chunk_repo.delete_by_channel(
                transcript_id=transcript_id,
                channel_id=channel_id,
            )
            logger.info(f"✓ Deleted {deleted_count} chunks from PostgreSQL")

            # Remove ChannelVideo association
            await self.channel_video_repo.remove_video(channel_id, transcript_id)
            logger.info("✓ Removed channel-video association")

            # Commit
            await self.db.commit()
            logger.info("✓ Transaction committed")

            logger.info(f"✓✓✓ Video removed from channel: {transcript_id}")

        except ValueError as e:
            await self.db.rollback()
            logger.warning(f"Validation error: {e}")
            raise
        except Exception as e:
            await self.db.rollback()
            logger.exception(f"✗ Failed to remove video from channel: {e}")
            raise

    # ===== Public User-Facing Methods =====

    async def list_public_channels(
        self,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[Channel], int]:
        """
        List active channels for authenticated user discovery.

        Returns only non-deleted channels with pagination support.

        Args:
            limit: Maximum number of channels to return (default: 50)
            offset: Number of channels to skip (default: 0)

        Returns:
            Tuple[List[Channel], int]: (channels, total_count)
        """
        return await self.channel_repo.list_active(limit=limit, offset=offset)

    async def get_public_channel(self, channel_id: UUID) -> Channel:
        """
        Get channel by ID for authenticated user viewing.

        Returns 404 if channel not found or soft-deleted.

        Args:
            channel_id: UUID of channel

        Returns:
            Channel: Channel instance

        Raises:
            ChannelNotFoundError: Channel not found or deleted
        """
        channel = await self.channel_repo.get_by_id(channel_id)
        if not channel or channel.deleted_at is not None:
            raise ChannelNotFoundError(f"Channel {channel_id} not found")
        return channel

    async def get_public_channel_by_name(self, name: str) -> Channel:
        """
        Get channel by URL-safe name for authenticated user viewing.

        Returns 404 if channel not found or soft-deleted.

        Args:
            name: URL-safe channel name

        Returns:
            Channel: Channel instance

        Raises:
            ChannelNotFoundError: Channel not found or deleted
        """
        channel = await self.channel_repo.get_by_name(name)
        if not channel or channel.deleted_at is not None:
            raise ChannelNotFoundError(f"Channel '{name}' not found")
        return channel

    async def get_or_create_channel_conversation(
        self,
        channel_id: UUID,
        user_id: UUID,
    ) -> ChannelConversation:
        """
        Get or create user's conversation with a channel.

        Verifies channel exists and is active before creating conversation.
        This is idempotent - always returns a conversation.

        Args:
            channel_id: Target channel UUID
            user_id: Authenticated user UUID

        Returns:
            ChannelConversation: User's conversation with the channel

        Raises:
            ChannelNotFoundError: Channel not found or deleted
        """
        # Verify channel exists and is active
        await self.get_public_channel(channel_id)

        # Get or create conversation
        conversation = await self.channel_conversation_repo.get_or_create(
            channel_id=channel_id,
            user_id=user_id,
        )
        await self.db.flush()
        logger.info(f"Got/created conversation {conversation.id} for user {user_id} and channel {channel_id}")
        return conversation

    async def list_user_channel_conversations(
        self,
        user_id: UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[ChannelConversation], int]:
        """
        List authenticated user's channel conversations with pagination.

        Returns conversations ordered by updated_at DESC (most recent first).

        Args:
            user_id: Authenticated user UUID
            limit: Maximum number of conversations to return (default: 50)
            offset: Number of conversations to skip (default: 0)

        Returns:
            Tuple[List[ChannelConversation], int]: (conversations, total_count)
        """
        return await self.channel_conversation_repo.list_by_user(
            user_id=user_id,
            limit=limit,
            offset=offset,
        )

    async def get_channel_conversation(
        self,
        conversation_id: UUID,
        user_id: UUID,
    ) -> ChannelConversation:
        """
        Get channel conversation by ID with ownership verification.

        Verifies the authenticated user owns this conversation.

        Args:
            conversation_id: UUID of channel conversation
            user_id: Authenticated user UUID

        Returns:
            ChannelConversation: Channel conversation instance

        Raises:
            ConversationNotFoundError: Conversation not found
            ConversationAccessDeniedError: User doesn't own conversation
        """
        from app.core.errors import ConversationAccessDeniedError, ConversationNotFoundError

        conversation = await self.channel_conversation_repo.get_by_id(conversation_id)

        if not conversation:
            raise ConversationNotFoundError(f"Conversation {conversation_id} not found")

        if conversation.user_id != user_id:
            logger.warning(
                f"User {user_id} attempted to access conversation {conversation_id} "
                f"owned by user {conversation.user_id}"
            )
            raise ConversationAccessDeniedError(
                f"User {user_id} does not own conversation {conversation_id}"
            )

        return conversation

    async def delete_channel_conversation(
        self,
        conversation_id: UUID,
        user_id: UUID,
    ) -> None:
        """
        Delete channel conversation with ownership verification.

        Verifies user owns the conversation before deletion.
        Cascade deletes all messages via database constraint.

        Args:
            conversation_id: UUID of conversation to delete
            user_id: Authenticated user UUID

        Raises:
            ConversationNotFoundError: Conversation not found
            ConversationAccessDeniedError: User doesn't own conversation
        """
        # Verify ownership
        await self.get_channel_conversation(conversation_id, user_id)

        # Delete conversation (messages cascade via DB constraint)
        await self.channel_conversation_repo.delete(conversation_id)
        logger.info(f"Deleted channel conversation {conversation_id} for user {user_id}")
