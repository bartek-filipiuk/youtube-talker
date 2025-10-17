"""
Unit Tests for ChunkRepository
"""

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import User, Transcript
from app.db.repositories.chunk_repo import ChunkRepository


@pytest_asyncio.fixture
async def test_transcript(db_session: AsyncSession, test_user: User) -> Transcript:
    """Fixture to create a test transcript for chunk tests."""
    transcript = Transcript(
        user_id=test_user.id,
        youtube_video_id="test_video",
        title="Test Video",
        channel_name="Test Channel",
        duration=300,
        transcript_text="Test transcript text",
    )
    db_session.add(transcript)
    await db_session.flush()
    await db_session.refresh(transcript)
    return transcript


@pytest.mark.asyncio
async def test_create_many_chunks(
    db_session: AsyncSession, test_user: User, test_transcript: Transcript
):
    """Test creating multiple chunks at once."""
    repo = ChunkRepository(db_session)

    chunks_data = [
        {
            "transcript_id": test_transcript.id,
            "user_id": test_user.id,
            "chunk_index": 0,
            "chunk_text": "First chunk text",
            "token_count": 10,
            "meta_data": {"source": "test"},
        },
        {
            "transcript_id": test_transcript.id,
            "user_id": test_user.id,
            "chunk_index": 1,
            "chunk_text": "Second chunk text",
            "token_count": 12,
            "meta_data": {"source": "test"},
        },
    ]

    chunks = await repo.create_many(chunks_data)

    assert len(chunks) == 2
    assert chunks[0].chunk_index == 0
    assert chunks[0].chunk_text == "First chunk text"
    assert chunks[0].token_count == 10
    assert chunks[1].chunk_index == 1
    assert chunks[1].chunk_text == "Second chunk text"
    assert chunks[1].token_count == 12


@pytest.mark.asyncio
async def test_create_chunks_without_metadata(
    db_session: AsyncSession, test_user: User, test_transcript: Transcript
):
    """Test creating chunks without metadata."""
    repo = ChunkRepository(db_session)

    chunks_data = [
        {
            "transcript_id": test_transcript.id,
            "user_id": test_user.id,
            "chunk_index": 0,
            "chunk_text": "Test chunk",
            "token_count": 5,
        }
    ]

    chunks = await repo.create_many(chunks_data)

    assert chunks[0].meta_data == {}


@pytest.mark.asyncio
async def test_get_chunks_by_ids(
    db_session: AsyncSession, test_user: User, test_transcript: Transcript
):
    """Test retrieving chunks by their IDs."""
    repo = ChunkRepository(db_session)

    # Create chunks
    chunks_data = [
        {
            "transcript_id": test_transcript.id,
            "user_id": test_user.id,
            "chunk_index": i,
            "chunk_text": f"Chunk {i}",
            "token_count": 10 + i,
        }
        for i in range(3)
    ]
    created_chunks = await repo.create_many(chunks_data)

    # Get specific chunks by ID
    chunk_ids = [created_chunks[0].id, created_chunks[2].id]
    retrieved_chunks = await repo.get_by_ids(chunk_ids)

    assert len(retrieved_chunks) == 2
    assert retrieved_chunks[0].id == created_chunks[0].id
    assert retrieved_chunks[1].id == created_chunks[2].id


@pytest.mark.asyncio
async def test_list_chunks_by_transcript(
    db_session: AsyncSession, test_user: User, test_transcript: Transcript
):
    """Test listing all chunks for a transcript."""
    repo = ChunkRepository(db_session)

    # Create chunks
    chunks_data = [
        {
            "transcript_id": test_transcript.id,
            "user_id": test_user.id,
            "chunk_index": i,
            "chunk_text": f"Chunk {i}",
            "token_count": 10 + i,
        }
        for i in range(5)
    ]
    await repo.create_many(chunks_data)

    # List all chunks
    chunks = await repo.list_by_transcript(test_transcript.id)

    assert len(chunks) == 5
    # Should be ordered by chunk_index ASC
    for i, chunk in enumerate(chunks):
        assert chunk.chunk_index == i


@pytest.mark.asyncio
async def test_delete_chunks_by_transcript(
    db_session: AsyncSession, test_user: User, test_transcript: Transcript
):
    """Test deleting all chunks for a transcript."""
    repo = ChunkRepository(db_session)

    # Create chunks
    chunks_data = [
        {
            "transcript_id": test_transcript.id,
            "user_id": test_user.id,
            "chunk_index": i,
            "chunk_text": f"Chunk {i}",
            "token_count": 10 + i,
        }
        for i in range(3)
    ]
    await repo.create_many(chunks_data)

    # Delete all chunks for transcript
    deleted_count = await repo.delete_by_transcript(test_transcript.id)

    assert deleted_count == 3

    # Verify all chunks deleted
    remaining_chunks = await repo.list_by_transcript(test_transcript.id)
    assert len(remaining_chunks) == 0


@pytest.mark.asyncio
async def test_chunks_cascade_delete_with_transcript(
    db_session: AsyncSession, test_user: User, test_transcript: Transcript
):
    """Test that chunks are deleted when transcript is deleted."""
    from app.db.repositories.transcript_repo import TranscriptRepository

    chunk_repo = ChunkRepository(db_session)

    # Create chunks
    chunks_data = [
        {
            "transcript_id": test_transcript.id,
            "user_id": test_user.id,
            "chunk_index": 0,
            "chunk_text": "Test chunk",
            "token_count": 10,
        }
    ]
    chunks = await chunk_repo.create_many(chunks_data)

    # Delete transcript
    transcript_repo = TranscriptRepository(db_session)
    await transcript_repo.delete(test_transcript.id)

    # Verify chunks are also deleted
    deleted_chunk = await chunk_repo.get_by_id(chunks[0].id)
    assert deleted_chunk is None
