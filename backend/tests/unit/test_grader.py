"""Unit tests for Grader node."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from uuid import uuid4

from app.rag.nodes.grader import grade_chunks
from app.rag.utils.state import GraphState
from app.schemas.llm_responses import RelevanceGrade


class TestGraderNode:
    """Unit tests for grade_chunks() node."""

    @pytest.mark.asyncio
    async def test_grade_chunks_all_relevant(self):
        """Grader keeps all chunks when all are relevant."""
        # Prepare state with retrieved chunks
        state: GraphState = {
            "user_query": "What is FastAPI?",
            "retrieved_chunks": [
                {
                    "chunk_id": str(uuid4()),
                    "chunk_text": "FastAPI is a modern web framework.",
                    "chunk_index": 0,
                    "youtube_video_id": "video123",
                    "score": 0.95,
                },
                {
                    "chunk_id": str(uuid4()),
                    "chunk_text": "It supports async operations.",
                    "chunk_index": 1,
                    "youtube_video_id": "video123",
                    "score": 0.88,
                },
            ],
        }

        # Mock LLM client to return all relevant
        mock_llm_client = MagicMock()
        mock_llm_client.ainvoke_gemini_structured = AsyncMock(
            side_effect=[
                RelevanceGrade(
                    is_relevant=True, reasoning="Directly describes FastAPI framework"
                ),
                RelevanceGrade(is_relevant=True, reasoning="Describes FastAPI feature"),
            ]
        )

        with patch("app.rag.nodes.grader.LLMClient", return_value=mock_llm_client):
            result_state = await grade_chunks(state)

        # Verify all chunks kept
        assert len(result_state["graded_chunks"]) == 2
        assert result_state["metadata"]["graded_count"] == 2
        assert result_state["metadata"]["relevant_count"] == 2
        assert result_state["metadata"]["not_relevant_count"] == 0

        # Verify reasoning added
        assert "relevance_reasoning" in result_state["graded_chunks"][0]
        assert result_state["graded_chunks"][0]["relevance_reasoning"] == "Directly describes FastAPI framework"

    @pytest.mark.asyncio
    async def test_grade_chunks_all_not_relevant(self):
        """Grader filters out all chunks when none are relevant."""
        state: GraphState = {
            "user_query": "What is machine learning?",
            "retrieved_chunks": [
                {
                    "chunk_id": str(uuid4()),
                    "chunk_text": "Python is a programming language.",
                    "chunk_index": 0,
                    "youtube_video_id": "video123",
                    "score": 0.7,
                },
                {
                    "chunk_id": str(uuid4()),
                    "chunk_text": "Web development is important.",
                    "chunk_index": 1,
                    "youtube_video_id": "video123",
                    "score": 0.65,
                },
            ],
        }

        # Mock LLM to return all not relevant
        mock_llm_client = MagicMock()
        mock_llm_client.ainvoke_gemini_structured = AsyncMock(
            side_effect=[
                RelevanceGrade(is_relevant=False, reasoning="Does not mention machine learning"),
                RelevanceGrade(is_relevant=False, reasoning="Unrelated to ML topic"),
            ]
        )

        with patch("app.rag.nodes.grader.LLMClient", return_value=mock_llm_client):
            result_state = await grade_chunks(state)

        # Verify all chunks filtered out
        assert result_state["graded_chunks"] == []
        assert result_state["metadata"]["graded_count"] == 2
        assert result_state["metadata"]["relevant_count"] == 0
        assert result_state["metadata"]["not_relevant_count"] == 2
        assert result_state["metadata"]["no_relevant_chunks"] is True

    @pytest.mark.asyncio
    async def test_grade_chunks_mixed_relevance(self):
        """Grader filters mixed relevant/not relevant chunks."""
        state: GraphState = {
            "user_query": "How does async work in Python?",
            "retrieved_chunks": [
                {
                    "chunk_id": "chunk1",
                    "chunk_text": "Async allows concurrent execution in Python.",
                    "chunk_index": 0,
                    "youtube_video_id": "video123",
                    "score": 0.92,
                },
                {
                    "chunk_id": "chunk2",
                    "chunk_text": "JavaScript also has async features.",
                    "chunk_index": 1,
                    "youtube_video_id": "video123",
                    "score": 0.78,
                },
                {
                    "chunk_id": "chunk3",
                    "chunk_text": "Asyncio is a Python library for async programming.",
                    "chunk_index": 2,
                    "youtube_video_id": "video123",
                    "score": 0.88,
                },
            ],
        }

        # Mock LLM: relevant, not relevant, relevant
        mock_llm_client = MagicMock()
        mock_llm_client.ainvoke_gemini_structured = AsyncMock(
            side_effect=[
                RelevanceGrade(is_relevant=True, reasoning="Explains async in Python"),
                RelevanceGrade(is_relevant=False, reasoning="About JavaScript, not Python"),
                RelevanceGrade(is_relevant=True, reasoning="Describes Python async library"),
            ]
        )

        with patch("app.rag.nodes.grader.LLMClient", return_value=mock_llm_client):
            result_state = await grade_chunks(state)

        # Verify only relevant chunks kept
        assert len(result_state["graded_chunks"]) == 2
        assert result_state["graded_chunks"][0]["chunk_id"] == "chunk1"
        assert result_state["graded_chunks"][1]["chunk_id"] == "chunk3"
        assert result_state["metadata"]["relevant_count"] == 2
        assert result_state["metadata"]["not_relevant_count"] == 1

    @pytest.mark.asyncio
    async def test_grade_chunks_empty_retrieved_chunks(self):
        """Grader handles empty retrieved_chunks gracefully."""
        state: GraphState = {
            "user_query": "Test query",
            "retrieved_chunks": [],  # Empty
        }

        result_state = await grade_chunks(state)

        # Verify graceful handling
        assert result_state["graded_chunks"] == []
        assert result_state["metadata"]["graded_count"] == 0
        assert result_state["metadata"]["relevant_count"] == 0
        assert result_state["metadata"]["not_relevant_count"] == 0

    @pytest.mark.asyncio
    async def test_grade_chunks_missing_user_query(self):
        """Grader handles missing user_query gracefully."""
        state: GraphState = {
            "retrieved_chunks": [
                {
                    "chunk_id": str(uuid4()),
                    "chunk_text": "Test chunk",
                    "chunk_index": 0,
                    "youtube_video_id": "video123",
                    "score": 0.9,
                }
            ],
        }  # Missing user_query

        result_state = await grade_chunks(state)

        # Verify graceful handling
        assert result_state["graded_chunks"] == []

    @pytest.mark.asyncio
    async def test_grade_chunks_llm_error_handling(self):
        """Grader skips chunks with LLM errors and continues."""
        state: GraphState = {
            "user_query": "Test query",
            "retrieved_chunks": [
                {
                    "chunk_id": "chunk1",
                    "chunk_text": "Chunk 1",
                    "chunk_index": 0,
                    "youtube_video_id": "video123",
                    "score": 0.9,
                },
                {
                    "chunk_id": "chunk2",
                    "chunk_text": "Chunk 2",
                    "chunk_index": 1,
                    "youtube_video_id": "video123",
                    "score": 0.85,
                },
                {
                    "chunk_id": "chunk3",
                    "chunk_text": "Chunk 3",
                    "chunk_index": 2,
                    "youtube_video_id": "video123",
                    "score": 0.8,
                },
            ],
        }

        # Mock LLM: success, error, success
        mock_llm_client = MagicMock()
        mock_llm_client.ainvoke_gemini_structured = AsyncMock(
            side_effect=[
                RelevanceGrade(is_relevant=True, reasoning="Relevant chunk"),
                Exception("LLM API error"),  # Error on second chunk
                RelevanceGrade(is_relevant=True, reasoning="Another relevant chunk"),
            ]
        )

        with patch("app.rag.nodes.grader.LLMClient", return_value=mock_llm_client):
            result_state = await grade_chunks(state)

        # Verify error handled: chunk 2 skipped, chunks 1 and 3 kept
        assert len(result_state["graded_chunks"]) == 2
        assert result_state["graded_chunks"][0]["chunk_id"] == "chunk1"
        assert result_state["graded_chunks"][1]["chunk_id"] == "chunk3"
        assert result_state["metadata"]["relevant_count"] == 2
        assert result_state["metadata"]["not_relevant_count"] == 1  # Error counted as not relevant

    @pytest.mark.asyncio
    async def test_grade_chunks_preserves_original_chunk_fields(self):
        """Grader preserves all original chunk fields and adds reasoning."""
        state: GraphState = {
            "user_query": "Test query",
            "retrieved_chunks": [
                {
                    "chunk_id": "original_id",
                    "chunk_text": "Original text",
                    "chunk_index": 42,
                    "youtube_video_id": "original_video",
                    "score": 0.999,
                }
            ],
        }

        mock_llm_client = MagicMock()
        mock_llm_client.ainvoke_gemini_structured = AsyncMock(
            return_value=RelevanceGrade(is_relevant=True, reasoning="Test reasoning")
        )

        with patch("app.rag.nodes.grader.LLMClient", return_value=mock_llm_client):
            result_state = await grade_chunks(state)

        # Verify all original fields preserved
        graded_chunk = result_state["graded_chunks"][0]
        assert graded_chunk["chunk_id"] == "original_id"
        assert graded_chunk["chunk_text"] == "Original text"
        assert graded_chunk["chunk_index"] == 42
        assert graded_chunk["youtube_video_id"] == "original_video"
        assert graded_chunk["score"] == 0.999

        # Verify reasoning added
        assert graded_chunk["relevance_reasoning"] == "Test reasoning"

    @pytest.mark.asyncio
    async def test_grade_chunks_calls_llm_for_each_chunk(self):
        """Grader makes individual LLM call for each chunk."""
        state: GraphState = {
            "user_query": "Test query",
            "retrieved_chunks": [
                {
                    "chunk_id": f"chunk{i}",
                    "chunk_text": f"Chunk {i} text",
                    "chunk_index": i,
                    "youtube_video_id": "video123",
                    "score": 0.9 - (i * 0.1),
                }
                for i in range(5)  # 5 chunks
            ],
        }

        mock_llm_client = MagicMock()
        mock_llm_client.ainvoke_gemini_structured = AsyncMock(
            return_value=RelevanceGrade(is_relevant=True, reasoning="Relevant")
        )

        with patch("app.rag.nodes.grader.LLMClient", return_value=mock_llm_client):
            await grade_chunks(state)

        # Verify LLM called 5 times (once per chunk)
        assert mock_llm_client.ainvoke_gemini_structured.call_count == 5
