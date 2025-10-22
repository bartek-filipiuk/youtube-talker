"""Unit tests for Retriever node."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from uuid import uuid4

from app.rag.nodes.retriever import retrieve_chunks
from app.rag.utils.state import GraphState


class TestRetrieverNode:
    """Unit tests for retrieve_chunks() node."""

    @pytest.mark.asyncio
    async def test_retrieve_chunks_success(self):
        """Retriever successfully retrieves and formats chunks."""
        # Prepare state
        state: GraphState = {
            "user_query": "What is FastAPI?",
            "user_id": str(uuid4()),
            "conversation_history": [],
        }

        # Mock embedding service
        mock_embeddings = [[0.1] * 1536]  # 1536-dim vector
        mock_embedding_service = AsyncMock()
        mock_embedding_service.generate_embeddings = AsyncMock(return_value=mock_embeddings)

        # Mock Qdrant search results (with chunk_text in payload)
        mock_qdrant_results = [
            {
                "chunk_id": str(uuid4()),
                "score": 0.95,
                "payload": {
                    "chunk_text": "FastAPI is a modern web framework for Python.",
                    "chunk_index": 0,
                    "youtube_video_id": "video123",
                },
            },
            {
                "chunk_id": str(uuid4()),
                "score": 0.88,
                "payload": {
                    "chunk_text": "It supports async operations out of the box.",
                    "chunk_index": 1,
                    "youtube_video_id": "video123",
                },
            },
        ]

        mock_qdrant_service = MagicMock()
        mock_qdrant_service.search = AsyncMock(return_value=mock_qdrant_results)

        # Patch services
        with patch(
            "app.rag.nodes.retriever.EmbeddingService", return_value=mock_embedding_service
        ), patch("app.rag.nodes.retriever.QdrantService", return_value=mock_qdrant_service):
            # Execute retriever
            result_state = await retrieve_chunks(state)

        # Verify state updates
        assert "retrieved_chunks" in result_state
        assert len(result_state["retrieved_chunks"]) == 2

        # Verify chunk format
        first_chunk = result_state["retrieved_chunks"][0]
        assert "chunk_id" in first_chunk
        assert "chunk_text" in first_chunk
        assert "chunk_index" in first_chunk
        assert "youtube_video_id" in first_chunk
        assert "score" in first_chunk

        # Verify chunk content
        assert first_chunk["chunk_text"] == "FastAPI is a modern web framework for Python."
        assert first_chunk["chunk_index"] == 0
        assert first_chunk["score"] == 0.95

        # Verify metadata
        assert result_state["metadata"]["retrieval_count"] == 2

        # Verify services called correctly
        mock_embedding_service.generate_embeddings.assert_called_once_with(["What is FastAPI?"])
        mock_qdrant_service.search.assert_called_once()

    @pytest.mark.asyncio
    async def test_retrieve_chunks_empty_results(self):
        """Retriever handles empty Qdrant results gracefully."""
        state: GraphState = {
            "user_query": "Nonexistent topic",
            "user_id": str(uuid4()),
            "conversation_history": [],
        }

        mock_embeddings = [[0.1] * 1536]
        mock_embedding_service = AsyncMock()
        mock_embedding_service.generate_embeddings = AsyncMock(return_value=mock_embeddings)

        # Qdrant returns empty results
        mock_qdrant_service = MagicMock()
        mock_qdrant_service.search = AsyncMock(return_value=[])

        with patch(
            "app.rag.nodes.retriever.EmbeddingService", return_value=mock_embedding_service
        ), patch("app.rag.nodes.retriever.QdrantService", return_value=mock_qdrant_service):
            result_state = await retrieve_chunks(state)

        # Verify empty results handled gracefully
        assert result_state["retrieved_chunks"] == []
        assert result_state["metadata"]["retrieval_count"] == 0

    @pytest.mark.asyncio
    async def test_retrieve_chunks_missing_user_query(self):
        """Retriever handles missing user_query gracefully."""
        state: GraphState = {
            "user_id": str(uuid4()),
            "conversation_history": [],
        }  # Missing user_query

        result_state = await retrieve_chunks(state)

        # Verify graceful handling
        assert result_state["retrieved_chunks"] == []
        assert result_state["metadata"]["retrieval_count"] == 0

    @pytest.mark.asyncio
    async def test_retrieve_chunks_missing_user_id(self):
        """Retriever handles missing user_id gracefully."""
        state: GraphState = {
            "user_query": "Test query",
            "conversation_history": [],
        }  # Missing user_id

        result_state = await retrieve_chunks(state)

        # Verify graceful handling
        assert result_state["retrieved_chunks"] == []
        assert result_state["metadata"]["retrieval_count"] == 0

    @pytest.mark.asyncio
    async def test_retrieve_chunks_with_user_id_filtering(self):
        """Retriever passes user_id to Qdrant for filtering."""
        user_id = str(uuid4())
        state: GraphState = {
            "user_query": "Test query",
            "user_id": user_id,
            "conversation_history": [],
        }

        mock_embeddings = [[0.1] * 1536]
        mock_embedding_service = AsyncMock()
        mock_embedding_service.generate_embeddings = AsyncMock(return_value=mock_embeddings)

        mock_qdrant_service = MagicMock()
        mock_qdrant_service.search = AsyncMock(return_value=[])

        with patch(
            "app.rag.nodes.retriever.EmbeddingService", return_value=mock_embedding_service
        ), patch("app.rag.nodes.retriever.QdrantService", return_value=mock_qdrant_service):
            await retrieve_chunks(state)

        # Verify user_id passed to Qdrant
        call_args = mock_qdrant_service.search.call_args
        assert call_args.kwargs["user_id"] == user_id

    @pytest.mark.asyncio
    async def test_retrieve_chunks_top_k_parameter(self):
        """Retriever uses top_k=12 for Qdrant search."""
        state: GraphState = {
            "user_query": "Test query",
            "user_id": str(uuid4()),
            "conversation_history": [],
        }

        mock_embeddings = [[0.1] * 1536]
        mock_embedding_service = AsyncMock()
        mock_embedding_service.generate_embeddings = AsyncMock(return_value=mock_embeddings)

        mock_qdrant_service = MagicMock()
        mock_qdrant_service.search = AsyncMock(return_value=[])

        with patch(
            "app.rag.nodes.retriever.EmbeddingService", return_value=mock_embedding_service
        ), patch("app.rag.nodes.retriever.QdrantService", return_value=mock_qdrant_service):
            await retrieve_chunks(state)

        # Verify top_k=12 used
        call_args = mock_qdrant_service.search.call_args
        assert call_args.kwargs["top_k"] == 12

    @pytest.mark.asyncio
    async def test_retrieve_chunks_preserves_score_ordering(self):
        """Retriever preserves Qdrant score ordering (descending)."""
        state: GraphState = {
            "user_query": "Test query",
            "user_id": str(uuid4()),
            "conversation_history": [],
        }

        mock_embeddings = [[0.1] * 1536]
        mock_embedding_service = AsyncMock()
        mock_embedding_service.generate_embeddings = AsyncMock(return_value=mock_embeddings)

        # Mock Qdrant results with descending scores
        mock_qdrant_results = [
            {
                "chunk_id": "chunk1",
                "score": 0.95,
                "payload": {
                    "chunk_text": "Highest score chunk",
                    "chunk_index": 0,
                    "youtube_video_id": "vid1",
                },
            },
            {
                "chunk_id": "chunk2",
                "score": 0.85,
                "payload": {
                    "chunk_text": "Medium score chunk",
                    "chunk_index": 1,
                    "youtube_video_id": "vid1",
                },
            },
            {
                "chunk_id": "chunk3",
                "score": 0.75,
                "payload": {
                    "chunk_text": "Lower score chunk",
                    "chunk_index": 2,
                    "youtube_video_id": "vid1",
                },
            },
        ]

        mock_qdrant_service = MagicMock()
        mock_qdrant_service.search = AsyncMock(return_value=mock_qdrant_results)

        with patch(
            "app.rag.nodes.retriever.EmbeddingService", return_value=mock_embedding_service
        ), patch("app.rag.nodes.retriever.QdrantService", return_value=mock_qdrant_service):
            result_state = await retrieve_chunks(state)

        # Verify ordering preserved
        chunks = result_state["retrieved_chunks"]
        assert chunks[0]["score"] == 0.95
        assert chunks[1]["score"] == 0.85
        assert chunks[2]["score"] == 0.75

    @pytest.mark.asyncio
    async def test_retrieve_chunks_reads_chunk_text_from_qdrant_payload(self):
        """Retriever reads chunk_text from Qdrant payload (no PostgreSQL fetch)."""
        state: GraphState = {
            "user_query": "Test query",
            "user_id": str(uuid4()),
            "conversation_history": [],
        }

        mock_embeddings = [[0.1] * 1536]
        mock_embedding_service = AsyncMock()
        mock_embedding_service.generate_embeddings = AsyncMock(return_value=mock_embeddings)

        # Mock Qdrant result with chunk_text in payload
        expected_chunk_text = "This text should come from Qdrant payload, not PostgreSQL."
        mock_qdrant_results = [
            {
                "chunk_id": str(uuid4()),
                "score": 0.9,
                "payload": {
                    "chunk_text": expected_chunk_text,
                    "chunk_index": 0,
                    "youtube_video_id": "video123",
                },
            }
        ]

        mock_qdrant_service = MagicMock()
        mock_qdrant_service.search = AsyncMock(return_value=mock_qdrant_results)

        with patch(
            "app.rag.nodes.retriever.EmbeddingService", return_value=mock_embedding_service
        ), patch("app.rag.nodes.retriever.QdrantService", return_value=mock_qdrant_service):
            result_state = await retrieve_chunks(state)

        # Verify chunk_text read from Qdrant payload
        assert result_state["retrieved_chunks"][0]["chunk_text"] == expected_chunk_text

    @pytest.mark.asyncio
    async def test_retrieve_chunks_skips_malformed_payload(self):
        """Retriever gracefully skips chunks with missing required payload fields."""
        state: GraphState = {
            "user_query": "Test query",
            "user_id": str(uuid4()),
            "conversation_history": [],
        }

        mock_embeddings = [[0.1] * 1536]
        mock_embedding_service = AsyncMock()
        mock_embedding_service.generate_embeddings = AsyncMock(return_value=mock_embeddings)

        # Mock Qdrant results: one valid, two malformed (missing fields)
        mock_qdrant_results = [
            {
                "chunk_id": "good_chunk",
                "score": 0.95,
                "payload": {
                    "chunk_text": "Valid chunk with all fields",
                    "chunk_index": 0,
                    "youtube_video_id": "video123",
                },
            },
            {
                "chunk_id": "missing_chunk_text",
                "score": 0.90,
                "payload": {
                    "chunk_index": 1,
                    "youtube_video_id": "video123",
                    # Missing chunk_text
                },
            },
            {
                "chunk_id": "missing_payload",
                "score": 0.85,
                # Missing payload entirely
            },
            {
                "chunk_id": "another_good_chunk",
                "score": 0.80,
                "payload": {
                    "chunk_text": "Another valid chunk",
                    "chunk_index": 2,
                    "youtube_video_id": "video123",
                },
            },
        ]

        mock_qdrant_service = MagicMock()
        mock_qdrant_service.search = AsyncMock(return_value=mock_qdrant_results)

        with patch(
            "app.rag.nodes.retriever.EmbeddingService", return_value=mock_embedding_service
        ), patch("app.rag.nodes.retriever.QdrantService", return_value=mock_qdrant_service):
            result_state = await retrieve_chunks(state)

        # Verify only valid chunks kept (2 out of 4)
        assert len(result_state["retrieved_chunks"]) == 2
        assert result_state["retrieved_chunks"][0]["chunk_id"] == "good_chunk"
        assert result_state["retrieved_chunks"][1]["chunk_id"] == "another_good_chunk"
        assert result_state["metadata"]["retrieval_count"] == 2
