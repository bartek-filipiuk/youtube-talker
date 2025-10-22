"""Unit tests for Generator node (response generation)."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.rag.nodes.generator import generate_response, _extract_chunk_ids
from app.rag.utils.state import GraphState


class TestGeneratorNode:
    """Unit tests for generate_response() node."""

    @pytest.mark.asyncio
    async def test_generate_response_chitchat(self):
        """Generator creates chitchat response without RAG context."""
        state: GraphState = {
            "intent": "chitchat",
            "user_query": "Hello! How are you?",
            "user_id": "user123",
            "conversation_history": []
        }

        # Mock LLM client
        mock_llm_client = MagicMock()
        mock_llm_client.ainvoke_claude = AsyncMock(
            return_value="<p>Hi there! I'm doing great, thanks for asking. I'm here to help you explore YouTube video content!</p>"
        )

        with patch("app.rag.nodes.generator.LLMClient", return_value=mock_llm_client):
            result_state = await generate_response(state)

        # Verify response generated
        assert "response" in result_state
        assert "Hi there" in result_state["response"]

        # Verify metadata
        assert result_state["metadata"]["response_type"] == "chitchat"
        assert result_state["metadata"]["chunks_used"] == 0

        # Verify LLM called with correct params
        mock_llm_client.ainvoke_claude.assert_called_once()
        call_args = mock_llm_client.ainvoke_claude.call_args
        assert call_args.kwargs["max_tokens"] == 500
        assert call_args.kwargs["temperature"] == 0.8

    @pytest.mark.asyncio
    async def test_generate_response_qa_with_chunks(self):
        """Generator creates Q&A response using graded chunks."""
        state: GraphState = {
            "intent": "qa",
            "user_query": "What is FastAPI?",
            "user_id": "user123",
            "conversation_history": [],
            "graded_chunks": [
                {
                    "chunk_id": "chunk1",
                    "chunk_text": "FastAPI is a modern web framework for Python.",
                    "metadata": {"youtube_video_id": "video123"}
                },
                {
                    "chunk_id": "chunk2",
                    "chunk_text": "It supports async operations out of the box.",
                    "metadata": {"youtube_video_id": "video123"}
                }
            ]
        }

        mock_llm_client = MagicMock()
        mock_llm_client.ainvoke_claude = AsyncMock(
            return_value="<p>FastAPI is a modern web framework for Python that supports async operations.</p>"
        )

        with patch("app.rag.nodes.generator.LLMClient", return_value=mock_llm_client):
            result_state = await generate_response(state)

        # Verify response generated
        assert "response" in result_state
        assert "FastAPI" in result_state["response"]

        # Verify metadata
        assert result_state["metadata"]["response_type"] == "qa"
        assert result_state["metadata"]["chunks_used"] == 2
        assert result_state["metadata"]["source_chunks"] == ["chunk1", "chunk2"]

        # Verify LLM called with Q&A params
        call_args = mock_llm_client.ainvoke_claude.call_args
        assert call_args.kwargs["max_tokens"] == 2000
        assert call_args.kwargs["temperature"] == 0.7

    @pytest.mark.asyncio
    async def test_generate_response_qa_without_chunks(self):
        """Generator handles Q&A when no graded chunks available."""
        state: GraphState = {
            "intent": "qa",
            "user_query": "What is machine learning?",
            "user_id": "user123",
            "conversation_history": [],
            "graded_chunks": []  # No chunks
        }

        mock_llm_client = MagicMock()
        mock_llm_client.ainvoke_claude = AsyncMock(
            return_value="<p>I don't have enough information in the knowledge base to answer this question.</p>"
        )

        with patch("app.rag.nodes.generator.LLMClient", return_value=mock_llm_client):
            result_state = await generate_response(state)

        # Should still generate response (LLM will say no information)
        assert "response" in result_state
        assert result_state["metadata"]["chunks_used"] == 0
        assert result_state["metadata"]["source_chunks"] == []

    @pytest.mark.asyncio
    async def test_generate_response_linkedin_with_chunks(self):
        """Generator creates LinkedIn post using graded chunks."""
        state: GraphState = {
            "intent": "linkedin",
            "user_query": "Write a LinkedIn post about async programming",
            "user_id": "user123",
            "conversation_history": [],
            "graded_chunks": [
                {
                    "chunk_id": "chunk1",
                    "chunk_text": "Async programming allows concurrent execution.",
                    "metadata": {"youtube_video_id": "video123"}
                },
                {
                    "chunk_id": "chunk2",
                    "chunk_text": "Python's asyncio library makes it easy.",
                    "metadata": {"youtube_video_id": "video123"}
                }
            ]
        }

        mock_llm_client = MagicMock()
        mock_llm_client.ainvoke_claude = AsyncMock(
            return_value="<p><strong>🚀 Why async programming matters</strong></p><p>Async allows concurrent execution...</p>"
        )

        with patch("app.rag.nodes.generator.LLMClient", return_value=mock_llm_client):
            result_state = await generate_response(state)

        # Verify LinkedIn post generated
        assert "response" in result_state
        assert "async" in result_state["response"].lower()

        # Verify metadata
        assert result_state["metadata"]["response_type"] == "linkedin"
        assert result_state["metadata"]["chunks_used"] == 2
        assert result_state["metadata"]["source_chunks"] == ["chunk1", "chunk2"]
        assert "topic" in result_state["metadata"]

        # Verify LLM params
        call_args = mock_llm_client.ainvoke_claude.call_args
        assert call_args.kwargs["max_tokens"] == 2000
        assert call_args.kwargs["temperature"] == 0.75

    @pytest.mark.asyncio
    async def test_generate_response_linkedin_topic_extraction(self):
        """Generator extracts topic from LinkedIn request."""
        test_cases = [
            ("Write a LinkedIn post about FastAPI", "FastAPI"),
            ("Create a LinkedIn post about machine learning", "machine learning"),
            ("Generate a LinkedIn post about async programming", "async programming"),
        ]

        for user_query, expected_topic in test_cases:
            state: GraphState = {
                "intent": "linkedin",
                "user_query": user_query,
                "user_id": "user123",
                "conversation_history": [],
                "graded_chunks": []
            }

            mock_llm_client = MagicMock()
            mock_llm_client.ainvoke_claude = AsyncMock(return_value="<p>Test post</p>")

            with patch("app.rag.nodes.generator.LLMClient", return_value=mock_llm_client):
                result_state = await generate_response(state)

            # Verify topic extracted
            assert expected_topic.lower() in result_state["metadata"]["topic"].lower()

    @pytest.mark.asyncio
    async def test_generate_response_missing_intent_raises_error(self):
        """Generator raises error when intent is missing."""
        state: GraphState = {
            "user_query": "Test query",
            "user_id": "user123",
            "conversation_history": []
        }  # No intent

        with pytest.raises(ValueError, match="Intent must be set"):
            await generate_response(state)

    @pytest.mark.asyncio
    async def test_generate_response_unknown_intent_raises_error(self):
        """Generator raises error for unknown intent."""
        state: GraphState = {
            "intent": "unknown_intent",
            "user_query": "Test query",
            "user_id": "user123",
            "conversation_history": []
        }

        with pytest.raises(ValueError, match="Unknown intent"):
            await generate_response(state)

    @pytest.mark.asyncio
    async def test_generate_response_with_conversation_history(self):
        """Generator uses conversation history for context."""
        state: GraphState = {
            "intent": "chitchat",
            "user_query": "Tell me more",
            "user_id": "user123",
            "conversation_history": [
                {"role": "user", "content": "What is FastAPI?"},
                {"role": "assistant", "content": "FastAPI is a web framework..."}
            ]
        }

        mock_llm_client = MagicMock()
        mock_llm_client.ainvoke_claude = AsyncMock(
            return_value="<p>Sure! FastAPI also has great documentation.</p>"
        )

        with patch("app.rag.nodes.generator.LLMClient", return_value=mock_llm_client):
            with patch("app.rag.nodes.generator.render_prompt") as mock_render:
                mock_render.return_value = "Mocked prompt"
                result_state = await generate_response(state)

                # Verify conversation history passed to template
                mock_render.assert_called_once()
                call_args = mock_render.call_args
                assert call_args.kwargs["conversation_history"] == state["conversation_history"]

        assert "response" in result_state

    @pytest.mark.asyncio
    async def test_generate_response_preserves_existing_state(self):
        """Generator preserves all existing state fields."""
        state: GraphState = {
            "intent": "chitchat",
            "user_query": "Hello",
            "user_id": "user123",
            "conversation_history": [],
            "retrieved_chunks": [{"chunk_id": "chunk1"}],
            "metadata": {"intent_confidence": 0.95}
        }

        mock_llm_client = MagicMock()
        mock_llm_client.ainvoke_claude = AsyncMock(return_value="<p>Hi!</p>")

        with patch("app.rag.nodes.generator.LLMClient", return_value=mock_llm_client):
            result_state = await generate_response(state)

        # Verify existing fields preserved
        assert result_state["user_query"] == "Hello"
        assert result_state["retrieved_chunks"] == [{"chunk_id": "chunk1"}]
        assert result_state["metadata"]["intent_confidence"] == 0.95

        # Verify new fields added
        assert "response" in result_state
        assert result_state["metadata"]["response_type"] == "chitchat"

    @pytest.mark.asyncio
    async def test_generate_response_llm_error_propagates(self):
        """Generator propagates LLM errors."""
        state: GraphState = {
            "intent": "chitchat",
            "user_query": "Test",
            "user_id": "user123",
            "conversation_history": []
        }

        mock_llm_client = MagicMock()
        mock_llm_client.ainvoke_claude = AsyncMock(
            side_effect=Exception("LLM API error")
        )

        with patch("app.rag.nodes.generator.LLMClient", return_value=mock_llm_client):
            with pytest.raises(Exception, match="LLM API error"):
                await generate_response(state)


class TestExtractChunkIds:
    """Unit tests for _extract_chunk_ids helper function."""

    def test_extract_chunk_ids_from_id_field(self):
        """Extracts chunk IDs from 'id' field."""
        chunks = [
            {"id": "chunk1", "chunk_text": "Text 1"},
            {"id": "chunk2", "chunk_text": "Text 2"}
        ]

        result = _extract_chunk_ids(chunks)

        assert result == ["chunk1", "chunk2"]

    def test_extract_chunk_ids_from_chunk_id_field(self):
        """Extracts chunk IDs from 'chunk_id' field."""
        chunks = [
            {"chunk_id": "chunk1", "chunk_text": "Text 1"},
            {"chunk_id": "chunk2", "chunk_text": "Text 2"}
        ]

        result = _extract_chunk_ids(chunks)

        assert result == ["chunk1", "chunk2"]

    def test_extract_chunk_ids_from_metadata(self):
        """Extracts chunk IDs from metadata.chunk_id."""
        chunks = [
            {"chunk_text": "Text 1", "metadata": {"chunk_id": "chunk1"}},
            {"chunk_text": "Text 2", "metadata": {"chunk_id": "chunk2"}}
        ]

        result = _extract_chunk_ids(chunks)

        assert result == ["chunk1", "chunk2"]

    def test_extract_chunk_ids_empty_list(self):
        """Handles empty chunk list."""
        result = _extract_chunk_ids([])
        assert result == []

    def test_extract_chunk_ids_missing_ids(self):
        """Handles chunks without IDs gracefully."""
        chunks = [
            {"chunk_text": "Text 1"},
            {"chunk_text": "Text 2"}
        ]

        result = _extract_chunk_ids(chunks)

        assert result == []

    def test_extract_chunk_ids_mixed(self):
        """Handles mixed chunks (some with IDs, some without)."""
        chunks = [
            {"id": "chunk1", "chunk_text": "Text 1"},
            {"chunk_text": "Text 2"},  # No ID
            {"chunk_id": "chunk3", "chunk_text": "Text 3"}
        ]

        result = _extract_chunk_ids(chunks)

        assert result == ["chunk1", "chunk3"]

    def test_extract_chunk_ids_converts_to_string(self):
        """Converts non-string chunk IDs to strings."""
        chunks = [
            {"id": 123, "chunk_text": "Text 1"},
            {"id": 456, "chunk_text": "Text 2"}
        ]

        result = _extract_chunk_ids(chunks)

        assert result == ["123", "456"]
        assert all(isinstance(chunk_id, str) for chunk_id in result)
