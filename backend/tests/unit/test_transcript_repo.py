"""
Unit Tests for TranscriptRepository
"""

from datetime import datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import User
from app.db.repositories.transcript_repo import TranscriptRepository


@pytest.mark.asyncio
async def test_create_transcript(db_session: AsyncSession, test_user: User):
    """Test creating a new transcript."""
    repo = TranscriptRepository(db_session)
    transcript = await repo.create(
        user_id=test_user.id,
        youtube_video_id="dQw4w9WgXcQ",
        title="Test Video",
        channel_name="Test Channel",
        duration=300,
        transcript_text="This is a test transcript.",
        meta_data={"language": "en"},
    )

    assert transcript.id is not None
    assert transcript.user_id == test_user.id
    assert transcript.youtube_video_id == "dQw4w9WgXcQ"
    assert transcript.title == "Test Video"
    assert transcript.channel_name == "Test Channel"
    assert transcript.duration == 300
    assert transcript.transcript_text == "This is a test transcript."
    assert transcript.meta_data == {"language": "en"}


@pytest.mark.asyncio
async def test_create_transcript_without_metadata(
    db_session: AsyncSession, test_user: User
):
    """Test creating transcript without metadata."""
    repo = TranscriptRepository(db_session)
    transcript = await repo.create(
        user_id=test_user.id,
        youtube_video_id="test123",
        title="Test",
        channel_name="Channel",
        duration=100,
        transcript_text="Text",
    )

    assert transcript.meta_data == {}


@pytest.mark.asyncio
async def test_get_transcript_by_video_id(db_session: AsyncSession, test_user: User):
    """Test retrieving transcript by video ID."""
    repo = TranscriptRepository(db_session)

    # Create transcript
    created_transcript = await repo.create(
        user_id=test_user.id,
        youtube_video_id="unique_video_123",
        title="Test",
        channel_name="Channel",
        duration=100,
        transcript_text="Text",
    )

    # Retrieve by youtube_video_id
    transcript = await repo.get_by_video_id(test_user.id, "unique_video_123")

    assert transcript is not None
    assert transcript.id == created_transcript.id
    assert transcript.youtube_video_id == "unique_video_123"


@pytest.mark.asyncio
async def test_get_by_video_id_not_found(db_session: AsyncSession, test_user: User):
    """Test retrieving non-existent video ID returns None."""
    repo = TranscriptRepository(db_session)
    transcript = await repo.get_by_video_id(test_user.id, "nonexistent_video")

    assert transcript is None


@pytest.mark.asyncio
async def test_list_transcripts_by_user(db_session: AsyncSession, test_user: User):
    """Test listing all transcripts for a user."""
    repo = TranscriptRepository(db_session)

    # Create multiple transcripts
    t1 = await repo.create(
        user_id=test_user.id,
        youtube_video_id="video1",
        title="First",
        channel_name="Channel",
        duration=100,
        transcript_text="Text 1",
    )
    t2 = await repo.create(
        user_id=test_user.id,
        youtube_video_id="video2",
        title="Second",
        channel_name="Channel",
        duration=200,
        transcript_text="Text 2",
    )

    # List transcripts
    transcripts = await repo.list_by_user(test_user.id)

    assert len(transcripts) == 2
    # Check that both transcripts are present (order may vary since created at same time)
    transcript_ids = {t.id for t in transcripts}
    assert t1.id in transcript_ids
    assert t2.id in transcript_ids


@pytest.mark.asyncio
async def test_delete_transcript(db_session: AsyncSession, test_user: User):
    """Test deleting a transcript."""
    repo = TranscriptRepository(db_session)

    # Create transcript
    transcript = await repo.create(
        user_id=test_user.id,
        youtube_video_id="delete_me",
        title="Test",
        channel_name="Channel",
        duration=100,
        transcript_text="Text",
    )

    # Delete transcript
    result = await repo.delete(transcript.id)
    assert result is True

    # Verify deleted
    deleted_transcript = await repo.get_by_id(transcript.id)
    assert deleted_transcript is None
