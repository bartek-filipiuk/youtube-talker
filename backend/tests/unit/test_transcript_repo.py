"""
Unit Tests for TranscriptRepository
"""

from datetime import datetime, timezone

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

    # List transcripts (now returns tuple of transcripts and total count)
    transcripts, total = await repo.list_by_user(test_user.id)

    assert len(transcripts) == 2
    assert total == 2
    # Check that both transcripts are present (order may vary since created at same time)
    transcript_ids = {t.id for t in transcripts}
    assert t1.id in transcript_ids
    assert t2.id in transcript_ids


@pytest.mark.asyncio
async def test_list_transcripts_with_pagination_limit(
    db_session: AsyncSession, test_user: User
):
    """Test listing transcripts with limit pagination."""
    repo = TranscriptRepository(db_session)

    # Create 5 transcripts
    for i in range(5):
        await repo.create(
            user_id=test_user.id,
            youtube_video_id=f"video{i}",
            title=f"Video {i}",
            channel_name="Channel",
            duration=100,
            transcript_text=f"Text {i}",
        )

    # Get first 3 transcripts
    transcripts, total = await repo.list_by_user(test_user.id, limit=3)

    assert len(transcripts) == 3
    assert total == 5


@pytest.mark.asyncio
async def test_list_transcripts_with_pagination_offset(
    db_session: AsyncSession, test_user: User
):
    """Test listing transcripts with offset pagination."""
    repo = TranscriptRepository(db_session)

    # Create 5 transcripts
    for i in range(5):
        await repo.create(
            user_id=test_user.id,
            youtube_video_id=f"video{i}",
            title=f"Video {i}",
            channel_name="Channel",
            duration=100,
            transcript_text=f"Text {i}",
        )

    # Skip first 2, get rest
    transcripts, total = await repo.list_by_user(test_user.id, offset=2)

    assert len(transcripts) == 3
    assert total == 5


@pytest.mark.asyncio
async def test_list_transcripts_with_limit_and_offset(
    db_session: AsyncSession, test_user: User
):
    """Test listing transcripts with both limit and offset."""
    repo = TranscriptRepository(db_session)

    # Create 10 transcripts
    for i in range(10):
        await repo.create(
            user_id=test_user.id,
            youtube_video_id=f"video{i}",
            title=f"Video {i}",
            channel_name="Channel",
            duration=100,
            transcript_text=f"Text {i}",
        )

    # Get second page (skip first 5, get next 5)
    transcripts, total = await repo.list_by_user(test_user.id, limit=5, offset=5)

    assert len(transcripts) == 5
    assert total == 10


@pytest.mark.asyncio
async def test_list_transcripts_pagination_beyond_total(
    db_session: AsyncSession, test_user: User
):
    """Test pagination with offset beyond total returns empty list."""
    repo = TranscriptRepository(db_session)

    # Create 3 transcripts
    for i in range(3):
        await repo.create(
            user_id=test_user.id,
            youtube_video_id=f"video{i}",
            title=f"Video {i}",
            channel_name="Channel",
            duration=100,
            transcript_text=f"Text {i}",
        )

    # Try to get transcripts beyond what exists
    transcripts, total = await repo.list_by_user(test_user.id, limit=10, offset=10)

    assert len(transcripts) == 0
    assert total == 3  # Total count should still be accurate


@pytest.mark.asyncio
async def test_list_transcripts_ordered_by_created_at_desc(
    db_session: AsyncSession, test_user: User
):
    """Test that transcripts are ordered by created_at descending (newest first)."""
    repo = TranscriptRepository(db_session)

    # Create multiple transcripts
    for i in range(3):
        await repo.create(
            user_id=test_user.id,
            youtube_video_id=f"video_{i}",
            title=f"Video {i}",
            channel_name="Channel",
            duration=100,
            transcript_text=f"Text {i}",
        )

    # Get all transcripts
    transcripts, total = await repo.list_by_user(test_user.id)

    assert len(transcripts) == 3
    assert total == 3

    # Verify that transcripts are ordered by created_at descending
    # (each transcript should have created_at >= the next one)
    for i in range(len(transcripts) - 1):
        assert transcripts[i].created_at >= transcripts[i + 1].created_at


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


@pytest.mark.asyncio
async def test_delete_by_user_success(db_session: AsyncSession, test_user: User):
    """Test successfully deleting a transcript owned by the user."""
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

    # Delete transcript with ownership verification
    result = await repo.delete_by_user(transcript.id, test_user.id)
    assert result is True

    # Verify deleted
    deleted_transcript = await repo.get_by_id(transcript.id)
    assert deleted_transcript is None


@pytest.mark.asyncio
async def test_delete_by_user_not_found(db_session: AsyncSession, test_user: User):
    """Test deleting a non-existent transcript returns False."""
    from uuid import uuid4

    repo = TranscriptRepository(db_session)

    # Try to delete a transcript that doesn't exist
    fake_id = uuid4()
    result = await repo.delete_by_user(fake_id, test_user.id)
    assert result is False


@pytest.mark.asyncio
async def test_delete_by_user_wrong_owner(db_session: AsyncSession, test_user: User):
    """Test that a user cannot delete another user's transcript."""
    from uuid import uuid4
    from app.db.repositories.user_repo import UserRepository

    repo = TranscriptRepository(db_session)
    user_repo = UserRepository(db_session)

    # Create another user
    other_user = await user_repo.create(
        email="other@example.com", password_hash="hashed_password"
    )

    # Create transcript owned by test_user
    transcript = await repo.create(
        user_id=test_user.id,
        youtube_video_id="protected",
        title="Test",
        channel_name="Channel",
        duration=100,
        transcript_text="Text",
    )

    # Try to delete using other_user's ID
    result = await repo.delete_by_user(transcript.id, other_user.id)
    assert result is False

    # Verify transcript still exists
    existing_transcript = await repo.get_by_id(transcript.id)
    assert existing_transcript is not None
    assert existing_transcript.user_id == test_user.id
