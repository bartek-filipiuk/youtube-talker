"""
Unit Tests for ChannelVideoRepository
"""

import asyncio
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import User, Channel, Transcript, ChannelVideo
from app.db.repositories.channel_repo import ChannelRepository
from app.db.repositories.channel_video_repo import ChannelVideoRepository
from app.db.repositories.transcript_repo import TranscriptRepository


@pytest_asyncio.fixture
async def test_channel(db_session: AsyncSession, test_user: User) -> Channel:
    """Fixture to create a test channel."""
    repo = ChannelRepository(db_session)
    channel = await repo.create(
        name="test-channel",
        display_title="Test Channel",
        description="Test Description",
        created_by=test_user.id,
        qdrant_collection_name="channel_test_channel"
    )
    await db_session.commit()
    return channel


@pytest_asyncio.fixture
async def test_transcript(db_session: AsyncSession, test_user: User) -> Transcript:
    """Fixture to create a test transcript."""
    repo = TranscriptRepository(db_session)
    transcript = await repo.create(
        user_id=test_user.id,
        youtube_video_id="test_video_123",
        title="Test Video",
        channel_name="Test Channel",
        duration=300,
        transcript_text="Test transcript content"
    )
    await db_session.commit()
    return transcript


@pytest.mark.asyncio
async def test_add_video_to_channel(
    db_session: AsyncSession,
    test_user: User,
    test_channel: Channel,
    test_transcript: Transcript
):
    """Test adding a video to a channel."""
    repo = ChannelVideoRepository(db_session)
    channel_video = await repo.add_video(
        channel_id=test_channel.id,
        transcript_id=test_transcript.id,
        added_by=test_user.id
    )

    assert channel_video.id is not None
    assert channel_video.channel_id == test_channel.id
    assert channel_video.transcript_id == test_transcript.id
    assert channel_video.added_by == test_user.id
    assert channel_video.added_at is not None


@pytest.mark.asyncio
async def test_add_video_without_added_by(
    db_session: AsyncSession,
    test_channel: Channel,
    test_transcript: Transcript
):
    """Test adding video without specifying added_by."""
    repo = ChannelVideoRepository(db_session)
    channel_video = await repo.add_video(
        channel_id=test_channel.id,
        transcript_id=test_transcript.id,
        added_by=None
    )

    assert channel_video.id is not None
    assert channel_video.added_by is None


@pytest.mark.asyncio
async def test_remove_video_from_channel(
    db_session: AsyncSession,
    test_user: User,
    test_channel: Channel,
    test_transcript: Transcript
):
    """Test removing a video from a channel."""
    repo = ChannelVideoRepository(db_session)

    # Add video first
    await repo.add_video(
        channel_id=test_channel.id,
        transcript_id=test_transcript.id,
        added_by=test_user.id
    )

    # Remove video
    result = await repo.remove_video(
        channel_id=test_channel.id,
        transcript_id=test_transcript.id
    )

    assert result is True

    # Verify removed
    videos, _ = await repo.list_by_channel(test_channel.id)
    assert len(videos) == 0


@pytest.mark.asyncio
async def test_remove_nonexistent_video(
    db_session: AsyncSession,
    test_channel: Channel,
    test_transcript: Transcript
):
    """Test removing video that isn't in channel returns False."""
    repo = ChannelVideoRepository(db_session)
    result = await repo.remove_video(
        channel_id=test_channel.id,
        transcript_id=test_transcript.id
    )
    assert result is False


@pytest.mark.asyncio
async def test_list_videos_by_channel(
    db_session: AsyncSession,
    test_user: User,
    test_channel: Channel
):
    """Test listing all videos in a channel."""
    repo = ChannelVideoRepository(db_session)
    transcript_repo = TranscriptRepository(db_session)

    # Create multiple transcripts and add to channel
    transcript1 = await transcript_repo.create(
        user_id=test_user.id,
        youtube_video_id="video_1",
        title="Video 1",
        channel_name="Channel 1",
        duration=300,
        transcript_text="Content 1"
    )
    transcript2 = await transcript_repo.create(
        user_id=test_user.id,
        youtube_video_id="video_2",
        title="Video 2",
        channel_name="Channel 2",
        duration=300,
        transcript_text="Content 2"
    )

    await repo.add_video(test_channel.id, transcript1.id, test_user.id)
    await repo.add_video(test_channel.id, transcript2.id, test_user.id)

    # List videos
    videos, total = await repo.list_by_channel(test_channel.id, limit=10, offset=0)

    assert total == 2
    assert len(videos) == 2


@pytest.mark.asyncio
async def test_list_videos_pagination(
    db_session: AsyncSession,
    test_user: User,
    test_channel: Channel
):
    """Test video listing with pagination."""
    repo = ChannelVideoRepository(db_session)
    transcript_repo = TranscriptRepository(db_session)

    # Create 5 transcripts
    for i in range(5):
        transcript = await transcript_repo.create(
            user_id=test_user.id,
            youtube_video_id=f"video_{i}",
            title=f"Video {i}",
            channel_name=f"Channel {i}",
            duration=300,
            transcript_text=f"Content {i}"
        )
        await repo.add_video(test_channel.id, transcript.id, test_user.id)

    # Get first page
    page1, total = await repo.list_by_channel(test_channel.id, limit=2, offset=0)
    assert total == 5
    assert len(page1) == 2

    # Get second page
    page2, total = await repo.list_by_channel(test_channel.id, limit=2, offset=2)
    assert total == 5
    assert len(page2) == 2

    # Ensure different videos
    assert page1[0].id != page2[0].id


@pytest.mark.asyncio
async def test_get_latest_n_videos(
    db_session: AsyncSession,
    test_user: User,
    test_channel: Channel
):
    """Test getting the N most recently added videos."""
    repo = ChannelVideoRepository(db_session)
    transcript_repo = TranscriptRepository(db_session)

    # Create and add 3 videos
    for i in range(3):
        transcript = await transcript_repo.create(
            user_id=test_user.id,
            youtube_video_id=f"recent_{i}",
            title=f"Recent {i}",
            channel_name=f"Recent Channel {i}",
            duration=300,
            transcript_text=f"Content {i}"
        )
        await repo.add_video(test_channel.id, transcript.id, test_user.id)
        await db_session.flush()  # Ensure distinct added_at timestamps
        await asyncio.sleep(0.01)  # Small delay to ensure distinct timestamps

    # Get latest 2
    latest = await repo.get_latest_n(test_channel.id, n=2)

    assert len(latest) == 2
    # Most recent should be first
    assert latest[0].transcript.youtube_video_id == "recent_2"
    assert latest[1].transcript.youtube_video_id == "recent_1"


@pytest.mark.asyncio
async def test_count_videos_by_channel(
    db_session: AsyncSession,
    test_user: User,
    test_channel: Channel
):
    """Test counting videos in a channel."""
    repo = ChannelVideoRepository(db_session)
    transcript_repo = TranscriptRepository(db_session)

    # Initially empty
    count = await repo.count_by_channel(test_channel.id)
    assert count == 0

    # Add 3 videos
    for i in range(3):
        transcript = await transcript_repo.create(
            user_id=test_user.id,
            youtube_video_id=f"count_{i}",
            title=f"Count {i}",
            channel_name=f"Count Channel {i}",
            duration=300,
            transcript_text=f"Content {i}"
        )
        await repo.add_video(test_channel.id, transcript.id, test_user.id)

    # Count should be 3
    count = await repo.count_by_channel(test_channel.id)
    assert count == 3


@pytest.mark.asyncio
async def test_video_exists_in_channel(
    db_session: AsyncSession,
    test_user: User,
    test_channel: Channel,
    test_transcript: Transcript
):
    """Test checking if video exists in channel."""
    repo = ChannelVideoRepository(db_session)

    # Initially doesn't exist
    exists = await repo.video_exists(test_channel.id, test_transcript.id)
    assert exists is False

    # Add video
    await repo.add_video(test_channel.id, test_transcript.id, test_user.id)

    # Now exists
    exists = await repo.video_exists(test_channel.id, test_transcript.id)
    assert exists is True


@pytest.mark.asyncio
async def test_duplicate_video_prevented_by_constraint(
    db_session: AsyncSession,
    test_user: User,
    test_channel: Channel,
    test_transcript: Transcript
):
    """Test that adding same video twice raises integrity error."""
    from sqlalchemy.exc import IntegrityError

    repo = ChannelVideoRepository(db_session)

    # Add video first time
    await repo.add_video(test_channel.id, test_transcript.id, test_user.id)
    await db_session.flush()

    # Try to add same video again - should raise IntegrityError
    with pytest.raises(IntegrityError):
        await repo.add_video(test_channel.id, test_transcript.id, test_user.id)
        await db_session.flush()
