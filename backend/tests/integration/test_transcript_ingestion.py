"""
Integration Tests for Transcript Ingestion Pipeline

Tests the full ingestion flow with real database and mocked external APIs.
External APIs (SUPADATA, OpenAI) are mocked to avoid costs and flakiness.
"""

import pytest
import pytest_asyncio
import uuid
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import User, Transcript, Chunk
from app.services.transcript_service import TranscriptService
from app.services.qdrant_service import QdrantService


# Mock data for SUPADATA API
MOCK_TRANSCRIPT_DATA = {
    "youtube_video_id": "dQw4w9WgXcQ",
    "transcript_text": "This is a test transcript. " * 100,  # ~500 chars
    "metadata": {
        "title": "Test Video",
        "duration": 213,
        "language": "en",
    },
}

# Mock embedding (1024-dim vector)
MOCK_EMBEDDING = [0.1] * 1024


@pytest_asyncio.fixture
async def mock_supadata():
    """Mock SUPADATA API responses."""
    with patch.object(
        TranscriptService, "fetch_transcript", new_callable=AsyncMock
    ) as mock:
        mock.return_value = MOCK_TRANSCRIPT_DATA
        yield mock


@pytest_asyncio.fixture
async def mock_openai_embeddings():
    """Mock OpenAI Embeddings API responses."""
    # Create mock response object
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "data": [{"embedding": MOCK_EMBEDDING, "index": i} for i in range(3)]
    }
    mock_response.raise_for_status = MagicMock()

    # Create mock client
    mock_client = AsyncMock()
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = None
    mock_client.post = AsyncMock(return_value=mock_response)

    with patch("httpx.AsyncClient", return_value=mock_client):
        yield mock_client


@pytest_asyncio.fixture
async def qdrant_service():
    """Create QdrantService and ensure collection exists."""
    service = QdrantService()
    await service.create_collection()
    return service


class TestTranscriptIngestionService:
    """Integration tests for TranscriptService.ingest_transcript()."""

    @pytest.mark.asyncio
    async def test_full_ingestion_pipeline_success(
        self,
        db_session: AsyncSession,
        test_user: User,
        mock_supadata,
        mock_openai_embeddings,
        qdrant_service,
    ):
        """Full ingestion pipeline creates transcript, chunks, and vectors."""
        service = TranscriptService()

        result = await service.ingest_transcript(
            youtube_url="https://youtube.com/watch?v=dQw4w9WgXcQ",
            user_id=test_user.id,
            db_session=db_session,
        )

        # Verify result structure
        assert "transcript_id" in result
        assert result["youtube_video_id"] == "dQw4w9WgXcQ"
        assert result["chunk_count"] > 0
        assert "metadata" in result

        # Verify transcript in database
        from app.db.repositories.transcript_repo import TranscriptRepository

        transcript_repo = TranscriptRepository(db_session)
        transcript = await transcript_repo.get_by_id(result["transcript_id"])
        assert transcript is not None
        assert transcript.youtube_video_id == "dQw4w9WgXcQ"
        assert transcript.user_id == test_user.id

        # Verify chunks in database
        from app.db.repositories.chunk_repo import ChunkRepository

        chunk_repo = ChunkRepository(db_session)
        chunks = await chunk_repo.list_by_transcript(result["transcript_id"])
        assert len(chunks) == result["chunk_count"]
        assert all(chunk.transcript_id == result["transcript_id"] for chunk in chunks)

        # Verify vectors in Qdrant
        query_vector = MOCK_EMBEDDING
        search_results = await qdrant_service.search(
            query_vector=query_vector,
            user_id=test_user.id,
            top_k=10,
        )
        assert len(search_results) == result["chunk_count"]

    @pytest.mark.asyncio
    async def test_ingestion_duplicate_video_raises_error(
        self,
        db_session: AsyncSession,
        test_user: User,
        mock_supadata,
        mock_openai_embeddings,
    ):
        """Ingesting same video twice raises ValueError."""
        service = TranscriptService()

        # First ingestion (should succeed)
        await service.ingest_transcript(
            youtube_url="https://youtube.com/watch?v=dQw4w9WgXcQ",
            user_id=test_user.id,
            db_session=db_session,
        )

        # Second ingestion (should fail with duplicate error)
        with pytest.raises(ValueError, match="already exists"):
            await service.ingest_transcript(
                youtube_url="https://youtube.com/watch?v=dQw4w9WgXcQ",
                user_id=test_user.id,
                db_session=db_session,
            )

    @pytest.mark.asyncio
    async def test_ingestion_different_users_same_video(
        self,
        db_session: AsyncSession,
        test_user: User,
        mock_supadata,
        mock_openai_embeddings,
    ):
        """Different users can ingest the same video."""
        # Create second user
        from app.db.repositories.user_repo import UserRepository
        from app.core.security import hash_password

        user_repo = UserRepository(db_session)
        second_user = await user_repo.create(
            {
                "email": "second@example.com",
                "password_hash": hash_password("password123"),
            }
        )
        await db_session.commit()

        service = TranscriptService()

        # First user ingests video
        result1 = await service.ingest_transcript(
            youtube_url="https://youtube.com/watch?v=dQw4w9WgXcQ",
            user_id=test_user.id,
            db_session=db_session,
        )

        # Second user ingests same video (should succeed)
        result2 = await service.ingest_transcript(
            youtube_url="https://youtube.com/watch?v=dQw4w9WgXcQ",
            user_id=second_user.id,
            db_session=db_session,
        )

        assert result1["transcript_id"] != result2["transcript_id"]
        assert result1["youtube_video_id"] == result2["youtube_video_id"]

    @pytest.mark.asyncio
    async def test_ingestion_invalid_youtube_url(
        self, db_session: AsyncSession, test_user: User
    ):
        """Invalid YouTube URL raises ValueError."""
        service = TranscriptService()

        with pytest.raises(ValueError, match="Invalid YouTube URL"):
            await service.ingest_transcript(
                youtube_url="https://invalid.com/video",
                user_id=test_user.id,
                db_session=db_session,
            )

    @pytest.mark.asyncio
    async def test_ingestion_rollback_on_error(
        self,
        db_session: AsyncSession,
        test_user: User,
        mock_supadata,
    ):
        """Failed ingestion rolls back database changes."""
        service = TranscriptService()

        # Mock OpenAI to raise error
        with patch(
            "app.services.embedding_service.EmbeddingService.generate_embeddings",
            side_effect=Exception("OpenAI API error"),
        ):
            with pytest.raises(Exception):
                await service.ingest_transcript(
                    youtube_url="https://youtube.com/watch?v=dQw4w9WgXcQ",
                    user_id=test_user.id,
                    db_session=db_session,
                )

        # Verify no data was saved
        from app.db.repositories.transcript_repo import TranscriptRepository

        transcript_repo = TranscriptRepository(db_session)
        transcripts = await transcript_repo.list_by_user(test_user.id)
        assert len(transcripts) == 0


class TestTranscriptIngestionEndpoint:
    """Integration tests for POST /api/transcripts/ingest endpoint."""

    def test_ingest_endpoint_success(
        self, client: TestClient, test_user: User, test_session, mock_supadata, mock_openai_embeddings
    ):
        """Successful ingestion returns 201 with transcript data."""
        response = client.post(
            "/api/transcripts/ingest",
            json={"youtube_url": "https://youtube.com/watch?v=dQw4w9WgXcQ"},
            headers={"Authorization": f"Bearer {test_session['token']}"},
        )

        assert response.status_code == 201
        data = response.json()
        assert "id" in data
        assert data["youtube_video_id"] == "dQw4w9WgXcQ"
        assert data["chunk_count"] > 0
        assert "metadata" in data

    def test_ingest_endpoint_duplicate_video(
        self, client: TestClient, test_user: User, test_session, mock_supadata, mock_openai_embeddings
    ):
        """Ingesting duplicate video returns 409."""
        # First ingestion
        client.post(
            "/api/transcripts/ingest",
            json={"youtube_url": "https://youtube.com/watch?v=dQw4w9WgXcQ"},
            headers={"Authorization": f"Bearer {test_session['token']}"},
        )

        # Second ingestion (duplicate)
        response = client.post(
            "/api/transcripts/ingest",
            json={"youtube_url": "https://youtube.com/watch?v=dQw4w9WgXcQ"},
            headers={"Authorization": f"Bearer {test_session['token']}"},
        )

        assert response.status_code == 409
        assert "already exists" in response.json()["detail"].lower()

    def test_ingest_endpoint_invalid_url(
        self, client: TestClient, test_user: User, test_session
    ):
        """Invalid YouTube URL returns 422."""
        response = client.post(
            "/api/transcripts/ingest",
            json={"youtube_url": "https://invalid.com/video"},
            headers={"Authorization": f"Bearer {test_session['token']}"},
        )

        assert response.status_code == 422
        assert "invalid" in response.json()["detail"].lower()

    def test_ingest_endpoint_no_auth(self, client: TestClient):
        """Request without authentication returns 401."""
        response = client.post(
            "/api/transcripts/ingest",
            json={"youtube_url": "https://youtube.com/watch?v=dQw4w9WgXcQ"},
        )

        assert response.status_code == 401

    def test_ingest_endpoint_invalid_token(self, client: TestClient):
        """Request with invalid token returns 401."""
        response = client.post(
            "/api/transcripts/ingest",
            json={"youtube_url": "https://youtube.com/watch?v=dQw4w9WgXcQ"},
            headers={"Authorization": "Bearer invalid_token"},
        )

        assert response.status_code == 401

    def test_ingest_endpoint_rate_limiting(
        self, client: TestClient, test_user: User, test_session, mock_supadata, mock_openai_embeddings
    ):
        """Rate limiting prevents more than 10 requests per minute."""
        # Make 10 requests (should all succeed or fail based on duplicate)
        for i in range(10):
            client.post(
                "/api/transcripts/ingest",
                json={"youtube_url": f"https://youtube.com/watch?v=video{i}"},
                headers={"Authorization": f"Bearer {test_session['token']}"},
            )

        # 11th request should be rate limited
        response = client.post(
            "/api/transcripts/ingest",
            json={"youtube_url": "https://youtube.com/watch?v=video11"},
            headers={"Authorization": f"Bearer {test_session['token']}"},
        )

        assert response.status_code == 429


class TestDataIsolation:
    """Integration tests for user data isolation."""

    @pytest.mark.asyncio
    async def test_users_cannot_see_each_others_transcripts(
        self,
        db_session: AsyncSession,
        test_user: User,
        mock_supadata,
        mock_openai_embeddings,
        qdrant_service,
    ):
        """Users can only search their own transcripts in Qdrant."""
        # Create second user
        from app.db.repositories.user_repo import UserRepository
        from app.core.security import hash_password

        user_repo = UserRepository(db_session)
        second_user = await user_repo.create(
            {
                "email": "second@example.com",
                "password_hash": hash_password("password123"),
            }
        )
        await db_session.commit()

        service = TranscriptService()

        # First user ingests video
        result1 = await service.ingest_transcript(
            youtube_url="https://youtube.com/watch?v=dQw4w9WgXcQ",
            user_id=test_user.id,
            db_session=db_session,
        )

        # Search as first user (should find chunks)
        results_user1 = await qdrant_service.search(
            query_vector=MOCK_EMBEDDING,
            user_id=test_user.id,
            top_k=10,
        )
        assert len(results_user1) == result1["chunk_count"]

        # Search as second user (should find nothing)
        results_user2 = await qdrant_service.search(
            query_vector=MOCK_EMBEDDING,
            user_id=second_user.id,
            top_k=10,
        )
        assert len(results_user2) == 0
