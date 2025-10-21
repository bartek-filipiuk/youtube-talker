"""Integration tests for QdrantService.

Requires running Qdrant instance (docker compose up -d qdrant).
"""

import pytest
import uuid
from typing import List

from app.services.qdrant_service import QdrantService


@pytest.fixture
async def qdrant_service():
    """Create QdrantService instance and ensure collection exists."""
    service = QdrantService()
    await service.create_collection()
    return service


@pytest.fixture
async def cleanup_test_data(qdrant_service):
    """Cleanup test data after each test."""
    test_chunk_ids = []

    yield test_chunk_ids

    # Cleanup: delete all test chunks
    if test_chunk_ids:
        try:
            await qdrant_service.delete_chunks(test_chunk_ids)
        except Exception:
            pass  # Best effort cleanup


class TestQdrantService:
    """Integration tests for QdrantService."""

    @pytest.mark.asyncio
    async def test_create_collection_idempotent(self, qdrant_service):
        """Collection creation is idempotent (no error on re-creation)."""
        # First call creates collection
        await qdrant_service.create_collection()

        # Second call should not raise error
        await qdrant_service.create_collection()

    @pytest.mark.asyncio
    async def test_upsert_and_search_single_chunk(
        self, qdrant_service, cleanup_test_data
    ):
        """Upsert single chunk and verify search retrieval."""
        # Prepare test data
        chunk_id = str(uuid.uuid4())
        user_id = str(uuid.uuid4())
        video_id = "TEST_VIDEO_001"
        vector = [0.1] * 1536

        cleanup_test_data.append(chunk_id)

        # Upsert chunk
        chunk_text = "This is test chunk text for video TEST_VIDEO_001."
        await qdrant_service.upsert_chunks(
            chunk_ids=[chunk_id],
            vectors=[vector],
            user_id=user_id,
            youtube_video_id=video_id,
            chunk_indices=[0],
            chunk_texts=[chunk_text],
        )

        # Search for chunk
        results = await qdrant_service.search(
            query_vector=vector,
            user_id=user_id,
            top_k=5,
        )

        # Verify results
        assert len(results) == 1
        assert results[0]["chunk_id"] == chunk_id
        assert results[0]["payload"]["user_id"] == user_id
        assert results[0]["payload"]["youtube_video_id"] == video_id
        assert results[0]["payload"]["chunk_index"] == 0
        assert results[0]["payload"]["chunk_text"] == chunk_text
        assert results[0]["score"] > 0.99  # Exact match should score ~1.0

    @pytest.mark.asyncio
    async def test_upsert_and_search_multiple_chunks(
        self, qdrant_service, cleanup_test_data
    ):
        """Upsert multiple chunks and verify search returns top-k."""
        # Prepare test data
        user_id = str(uuid.uuid4())
        video_id = "TEST_VIDEO_002"
        num_chunks = 5

        chunk_ids = [str(uuid.uuid4()) for _ in range(num_chunks)]
        # Create varied vectors (not constant vectors)
        vectors = [
            [0.1 if j % (i + 1) == 0 else 0.5 for j in range(1536)]
            for i in range(num_chunks)
        ]
        chunk_indices = list(range(num_chunks))

        cleanup_test_data.extend(chunk_ids)

        # Upsert chunks
        chunk_texts = [f"Chunk {i} text for video TEST_VIDEO_002" for i in range(num_chunks)]
        await qdrant_service.upsert_chunks(
            chunk_ids=chunk_ids,
            vectors=vectors,
            user_id=user_id,
            youtube_video_id=video_id,
            chunk_indices=chunk_indices,
            chunk_texts=chunk_texts,
        )

        # Search for chunks (query = first chunk vector)
        results = await qdrant_service.search(
            query_vector=vectors[0],
            user_id=user_id,
            top_k=3,
        )

        # Verify top-k results returned
        assert len(results) == 3
        assert results[0]["chunk_id"] == chunk_ids[0]  # Exact match first

        # Verify all results belong to same user
        for result in results:
            assert result["payload"]["user_id"] == user_id

    @pytest.mark.asyncio
    async def test_search_user_id_filtering(self, qdrant_service, cleanup_test_data):
        """Search only returns chunks for specified user (data isolation)."""
        # Prepare test data for two users
        user_1_id = str(uuid.uuid4())
        user_2_id = str(uuid.uuid4())
        video_id = "TEST_VIDEO_003"
        vector = [0.5] * 1536

        chunk_1_id = str(uuid.uuid4())
        chunk_2_id = str(uuid.uuid4())

        cleanup_test_data.extend([chunk_1_id, chunk_2_id])

        # Upsert chunk for user 1
        chunk_text_1 = "User 1 chunk text for video TEST_VIDEO_003"
        await qdrant_service.upsert_chunks(
            chunk_ids=[chunk_1_id],
            vectors=[vector],
            user_id=user_1_id,
            youtube_video_id=video_id,
            chunk_indices=[0],
            chunk_texts=[chunk_text_1],
        )

        # Upsert chunk for user 2
        chunk_text_2 = "User 2 chunk text for video TEST_VIDEO_003"
        await qdrant_service.upsert_chunks(
            chunk_ids=[chunk_2_id],
            vectors=[vector],
            user_id=user_2_id,
            youtube_video_id=video_id,
            chunk_indices=[0],
            chunk_texts=[chunk_text_2],
        )

        # Search as user 1
        results_user_1 = await qdrant_service.search(
            query_vector=vector,
            user_id=user_1_id,
            top_k=10,
        )

        # Verify only user 1's chunks returned
        assert len(results_user_1) == 1
        assert results_user_1[0]["chunk_id"] == chunk_1_id
        assert results_user_1[0]["payload"]["user_id"] == user_1_id
        assert results_user_1[0]["payload"]["chunk_text"] == chunk_text_1

        # Search as user 2
        results_user_2 = await qdrant_service.search(
            query_vector=vector,
            user_id=user_2_id,
            top_k=10,
        )

        # Verify only user 2's chunks returned
        assert len(results_user_2) == 1
        assert results_user_2[0]["chunk_id"] == chunk_2_id
        assert results_user_2[0]["payload"]["user_id"] == user_2_id
        assert results_user_2[0]["payload"]["chunk_text"] == chunk_text_2

    @pytest.mark.asyncio
    async def test_search_video_id_filtering(self, qdrant_service, cleanup_test_data):
        """Search with video_id filter returns only chunks from that video."""
        # Prepare test data for same user, different videos
        user_id = str(uuid.uuid4())
        video_1_id = "TEST_VIDEO_004"
        video_2_id = "TEST_VIDEO_005"
        vector = [0.7] * 1536

        chunk_1_id = str(uuid.uuid4())
        chunk_2_id = str(uuid.uuid4())

        cleanup_test_data.extend([chunk_1_id, chunk_2_id])

        # Upsert chunk for video 1
        chunk_text_1 = "Chunk text for video TEST_VIDEO_004"
        await qdrant_service.upsert_chunks(
            chunk_ids=[chunk_1_id],
            vectors=[vector],
            user_id=user_id,
            youtube_video_id=video_1_id,
            chunk_indices=[0],
            chunk_texts=[chunk_text_1],
        )

        # Upsert chunk for video 2
        chunk_text_2 = "Chunk text for video TEST_VIDEO_005"
        await qdrant_service.upsert_chunks(
            chunk_ids=[chunk_2_id],
            vectors=[vector],
            user_id=user_id,
            youtube_video_id=video_2_id,
            chunk_indices=[0],
            chunk_texts=[chunk_text_2],
        )

        # Search without video filter (should return both)
        results_all = await qdrant_service.search(
            query_vector=vector,
            user_id=user_id,
            top_k=10,
        )
        assert len(results_all) == 2

        # Search with video_1 filter
        results_video_1 = await qdrant_service.search(
            query_vector=vector,
            user_id=user_id,
            youtube_video_id=video_1_id,
            top_k=10,
        )

        # Verify only video 1's chunks returned
        assert len(results_video_1) == 1
        assert results_video_1[0]["chunk_id"] == chunk_1_id
        assert results_video_1[0]["payload"]["youtube_video_id"] == video_1_id
        assert results_video_1[0]["payload"]["chunk_text"] == chunk_text_1

        # Search with video_2 filter
        results_video_2 = await qdrant_service.search(
            query_vector=vector,
            user_id=user_id,
            youtube_video_id=video_2_id,
            top_k=10,
        )

        # Verify only video 2's chunks returned
        assert len(results_video_2) == 1
        assert results_video_2[0]["chunk_id"] == chunk_2_id
        assert results_video_2[0]["payload"]["youtube_video_id"] == video_2_id
        assert results_video_2[0]["payload"]["chunk_text"] == chunk_text_2

    @pytest.mark.asyncio
    async def test_delete_chunks(self, qdrant_service, cleanup_test_data):
        """Delete chunks removes them from search results."""
        # Prepare test data
        user_id = str(uuid.uuid4())
        video_id = "TEST_VIDEO_006"
        vector = [0.9] * 1536

        chunk_1_id = str(uuid.uuid4())
        chunk_2_id = str(uuid.uuid4())

        # Upsert two chunks
        chunk_texts = ["Chunk 0 text for TEST_VIDEO_006", "Chunk 1 text for TEST_VIDEO_006"]
        await qdrant_service.upsert_chunks(
            chunk_ids=[chunk_1_id, chunk_2_id],
            vectors=[vector, vector],
            user_id=user_id,
            youtube_video_id=video_id,
            chunk_indices=[0, 1],
            chunk_texts=chunk_texts,
        )

        # Verify both chunks exist
        results_before = await qdrant_service.search(
            query_vector=vector,
            user_id=user_id,
            top_k=10,
        )
        assert len(results_before) == 2

        # Delete first chunk
        await qdrant_service.delete_chunks([chunk_1_id])

        # Verify only second chunk remains
        results_after = await qdrant_service.search(
            query_vector=vector,
            user_id=user_id,
            top_k=10,
        )
        assert len(results_after) == 1
        assert results_after[0]["chunk_id"] == chunk_2_id

        # Cleanup remaining chunk
        cleanup_test_data.append(chunk_2_id)

    @pytest.mark.asyncio
    async def test_upsert_is_idempotent(self, qdrant_service, cleanup_test_data):
        """Upserting same chunk_id updates the vector."""
        # Prepare test data
        chunk_id = str(uuid.uuid4())
        user_id = str(uuid.uuid4())
        video_id = "TEST_VIDEO_007"

        # Create vectors with different directions (not just different magnitudes)
        vector_v1 = [1.0 if i % 2 == 0 else 0.0 for i in range(1536)]
        vector_v2 = [1.0 if i % 2 == 1 else 0.0 for i in range(1536)]

        cleanup_test_data.append(chunk_id)

        # First upsert
        chunk_text = "Test chunk for idempotency test VIDEO_007"
        await qdrant_service.upsert_chunks(
            chunk_ids=[chunk_id],
            vectors=[vector_v1],
            user_id=user_id,
            youtube_video_id=video_id,
            chunk_indices=[0],
            chunk_texts=[chunk_text],
        )

        # Search with v1 vector (should match perfectly)
        results_v1 = await qdrant_service.search(
            query_vector=vector_v1,
            user_id=user_id,
            top_k=5,
        )
        assert len(results_v1) == 1
        assert results_v1[0]["score"] > 0.99

        # Update same chunk_id with v2 vector (orthogonal to v1)
        updated_chunk_text = "Updated chunk text for idempotency test VIDEO_007"
        await qdrant_service.upsert_chunks(
            chunk_ids=[chunk_id],
            vectors=[vector_v2],
            user_id=user_id,
            youtube_video_id=video_id,
            chunk_indices=[0],
            chunk_texts=[updated_chunk_text],
        )

        # Search with v2 vector (should match perfectly now)
        results_v2 = await qdrant_service.search(
            query_vector=vector_v2,
            user_id=user_id,
            top_k=5,
        )
        assert len(results_v2) == 1
        assert results_v2[0]["score"] > 0.99

        # Search with v1 vector (should match poorly now - vectors are orthogonal)
        results_v1_after = await qdrant_service.search(
            query_vector=vector_v1,
            user_id=user_id,
            top_k=5,
        )
        assert len(results_v1_after) == 1
        assert results_v1_after[0]["score"] < 0.1  # Very low similarity (orthogonal)

    @pytest.mark.asyncio
    async def test_health_check(self, qdrant_service):
        """Health check returns True when Qdrant is accessible."""
        healthy = await qdrant_service.health_check()
        assert healthy is True

    @pytest.mark.asyncio
    async def test_search_returns_empty_for_nonexistent_user(
        self, qdrant_service, cleanup_test_data
    ):
        """Search returns empty list if no chunks for user exist."""
        # Create chunk for user 1
        user_1_id = str(uuid.uuid4())
        user_2_id = str(uuid.uuid4())
        video_id = "TEST_VIDEO_008"
        vector = [0.3] * 1536

        chunk_id = str(uuid.uuid4())
        cleanup_test_data.append(chunk_id)

        chunk_text = "Chunk text for nonexistent user test VIDEO_008"
        await qdrant_service.upsert_chunks(
            chunk_ids=[chunk_id],
            vectors=[vector],
            user_id=user_1_id,
            youtube_video_id=video_id,
            chunk_indices=[0],
            chunk_texts=[chunk_text],
        )

        # Search as different user (should return empty)
        results = await qdrant_service.search(
            query_vector=vector,
            user_id=user_2_id,
            top_k=10,
        )

        assert results == []

    @pytest.mark.asyncio
    async def test_chunk_text_storage_and_retrieval(
        self, qdrant_service, cleanup_test_data
    ):
        """Verify chunk_text is stored in payload and retrieved correctly."""
        # Prepare test data with realistic chunk text
        user_id = str(uuid.uuid4())
        video_id = "TEST_VIDEO_CHUNK_TEXT"
        chunk_id = str(uuid.uuid4())
        vector = [0.5] * 1536
        chunk_text = (
            "This is a realistic test chunk with specific content to verify storage. "
            "The chunk should be stored in Qdrant payload and retrieved during search. "
            "This enables RAG retrieval without needing to fetch from PostgreSQL."
        )

        cleanup_test_data.append(chunk_id)

        # Upsert chunk with text
        await qdrant_service.upsert_chunks(
            chunk_ids=[chunk_id],
            vectors=[vector],
            user_id=user_id,
            youtube_video_id=video_id,
            chunk_indices=[0],
            chunk_texts=[chunk_text],
        )

        # Search and verify chunk_text in payload
        results = await qdrant_service.search(
            query_vector=vector,
            user_id=user_id,
            top_k=5,
        )

        # Verify chunk_text was stored and retrieved
        assert len(results) == 1
        assert "chunk_text" in results[0]["payload"]
        assert results[0]["payload"]["chunk_text"] == chunk_text
        assert len(results[0]["payload"]["chunk_text"]) > 100  # Verify not truncated
        assert "specific content" in results[0]["payload"]["chunk_text"]  # Verify content

    @pytest.mark.asyncio
    async def test_chunk_text_with_special_characters(
        self, qdrant_service, cleanup_test_data
    ):
        """Verify chunk_text with special characters and encoding is stored correctly."""
        user_id = str(uuid.uuid4())
        video_id = "TEST_VIDEO_SPECIAL_CHARS"
        chunk_id = str(uuid.uuid4())
        vector = [0.7] * 1536

        # Test with various special characters
        chunk_text = (
            "Testing special chars: <html>, \"quotes\", 'apostrophes', "
            "newlines\n\ttabs, emojis 🚀🔥, unicode: café, résumé, "
            "symbols: @#$%^&*(), code: if x == 10: return True"
        )

        cleanup_test_data.append(chunk_id)

        await qdrant_service.upsert_chunks(
            chunk_ids=[chunk_id],
            vectors=[vector],
            user_id=user_id,
            youtube_video_id=video_id,
            chunk_indices=[0],
            chunk_texts=[chunk_text],
        )

        # Search and verify special characters preserved
        results = await qdrant_service.search(
            query_vector=vector,
            user_id=user_id,
            top_k=5,
        )

        assert len(results) == 1
        retrieved_text = results[0]["payload"]["chunk_text"]
        assert retrieved_text == chunk_text
        assert "🚀🔥" in retrieved_text
        assert "café" in retrieved_text
        assert '"quotes"' in retrieved_text
