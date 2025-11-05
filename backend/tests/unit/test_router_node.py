"""Unit tests for Router node (intent classification)."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.rag.nodes.router_node import classify_intent
from app.rag.utils.state import GraphState
from app.schemas.llm_responses import IntentClassification


class TestRouterNode:
    """Unit tests for classify_intent() node."""

    @pytest.mark.asyncio
    async def test_classify_intent_content(self):
        """Router correctly classifies content intent (V2 - general queries/chitchat)."""
        state: GraphState = {
            "user_query": "Hello! How are you today?",
            "user_id": "user123",
            "conversation_history": []
        }

        # Mock LLM client to return content classification (V2: chitchat is now "content")
        mock_llm_client = MagicMock()
        mock_llm_client.ainvoke_claude_structured = AsyncMock(
            return_value=IntentClassification(
                intent="content",
                confidence=0.95,
                reasoning="User is greeting, no specific question or request"
            )
        )

        with patch("app.rag.nodes.router_node.LLMClient", return_value=mock_llm_client):
            result_state = await classify_intent(state)

        # Verify intent classification
        assert result_state["intent"] == "content"
        assert result_state["metadata"]["intent_confidence"] == 0.95
        assert "greeting" in result_state["metadata"]["intent_reasoning"].lower()

        # Verify LLM called correctly with Claude structured output
        mock_llm_client.ainvoke_claude_structured.assert_called_once()
        call_args = mock_llm_client.ainvoke_claude_structured.call_args
        assert call_args.kwargs["schema"] == IntentClassification
        assert call_args.kwargs["temperature"] == 0.3

    @pytest.mark.asyncio
    async def test_classify_intent_content_question(self):
        """Router correctly classifies content intent for questions (V2 - Q&A is now "content")."""
        state: GraphState = {
            "user_query": "What is dependency injection in FastAPI?",
            "user_id": "user123",
            "conversation_history": []
        }

        mock_llm_client = MagicMock()
        mock_llm_client.ainvoke_claude_structured = AsyncMock(
            return_value=IntentClassification(
                intent="content",
                confidence=0.92,
                reasoning="User asks a specific factual question requiring knowledge retrieval"
            )
        )

        with patch("app.rag.nodes.router_node.LLMClient", return_value=mock_llm_client):
            result_state = await classify_intent(state)

        assert result_state["intent"] == "content"
        assert result_state["metadata"]["intent_confidence"] == 0.92
        assert "knowledge retrieval" in result_state["metadata"]["intent_reasoning"]

    @pytest.mark.asyncio
    async def test_classify_intent_linkedin(self):
        """Router correctly classifies LinkedIn post generation intent (V2 - unchanged)."""
        state: GraphState = {
            "user_query": "Write a LinkedIn post about async programming in Python",
            "user_id": "user123",
            "conversation_history": []
        }

        mock_llm_client = MagicMock()
        mock_llm_client.ainvoke_claude_structured = AsyncMock(
            return_value=IntentClassification(
                intent="linkedin",
                confidence=0.98,
                reasoning="User explicitly requests LinkedIn post creation"
            )
        )

        with patch("app.rag.nodes.router_node.LLMClient", return_value=mock_llm_client):
            result_state = await classify_intent(state)

        assert result_state["intent"] == "linkedin"
        assert result_state["metadata"]["intent_confidence"] == 0.98
        assert "linkedin" in result_state["metadata"]["intent_reasoning"].lower()

    @pytest.mark.asyncio
    async def test_classify_intent_with_conversation_history(self):
        """Router uses conversation history for context (V2)."""
        state: GraphState = {
            "user_query": "Tell me more about that",
            "user_id": "user123",
            "conversation_history": [
                {"role": "user", "content": "What is FastAPI?"},
                {"role": "assistant", "content": "FastAPI is a modern web framework..."}
            ]
        }

        mock_llm_client = MagicMock()
        mock_llm_client.ainvoke_claude_structured = AsyncMock(
            return_value=IntentClassification(
                intent="content",
                confidence=0.88,
                reasoning="Follow-up question from previous context about FastAPI"
            )
        )

        with patch("app.rag.nodes.router_node.LLMClient", return_value=mock_llm_client):
            with patch("app.rag.nodes.router_node.render_prompt") as mock_render:
                mock_render.return_value = "Mocked prompt"
                result_state = await classify_intent(state)

                # Verify conversation history passed to template (V2 uses query_router_v2.jinja2)
                mock_render.assert_called_once()
                call_args = mock_render.call_args
                assert call_args.args[0] == "query_router_v2.jinja2"
                assert call_args.kwargs["conversation_history"] == state["conversation_history"]
                assert call_args.kwargs["user_query"] == "Tell me more about that"

        assert result_state["intent"] == "content"

    @pytest.mark.asyncio
    async def test_classify_intent_empty_query(self):
        """Router handles empty user query gracefully (V2)."""
        state: GraphState = {
            "user_query": "",
            "user_id": "user123",
            "conversation_history": []
        }

        mock_llm_client = MagicMock()
        mock_llm_client.ainvoke_claude_structured = AsyncMock(
            return_value=IntentClassification(
                intent="content",
                confidence=0.5,
                reasoning="Empty query, treating as content"
            )
        )

        with patch("app.rag.nodes.router_node.LLMClient", return_value=mock_llm_client):
            result_state = await classify_intent(state)

        assert result_state["intent"] == "content"
        assert result_state["metadata"]["intent_confidence"] == 0.5

    @pytest.mark.asyncio
    async def test_classify_intent_missing_user_query(self):
        """Router handles missing user_query field (V2)."""
        state: GraphState = {
            "user_id": "user123",
            "conversation_history": []
        }  # No user_query

        mock_llm_client = MagicMock()
        mock_llm_client.ainvoke_claude_structured = AsyncMock(
            return_value=IntentClassification(
                intent="content",
                confidence=0.3,
                reasoning="No query provided"
            )
        )

        with patch("app.rag.nodes.router_node.LLMClient", return_value=mock_llm_client):
            result_state = await classify_intent(state)

        # Should handle gracefully (empty string default)
        assert "intent" in result_state
        assert result_state["intent"] == "content"

    @pytest.mark.asyncio
    async def test_classify_intent_preserves_existing_state(self):
        """Router preserves all existing state fields (V2)."""
        state: GraphState = {
            "user_query": "What is FastAPI?",
            "user_id": "user123",
            "conversation_history": [],
            "retrieved_chunks": [{"chunk_id": "chunk1"}],  # Existing field
            "metadata": {"existing_key": "existing_value"}  # Existing metadata
        }

        mock_llm_client = MagicMock()
        mock_llm_client.ainvoke_claude_structured = AsyncMock(
            return_value=IntentClassification(
                intent="content",
                confidence=0.9,
                reasoning="Question about FastAPI"
            )
        )

        with patch("app.rag.nodes.router_node.LLMClient", return_value=mock_llm_client):
            result_state = await classify_intent(state)

        # Verify existing fields preserved
        assert result_state["user_query"] == "What is FastAPI?"
        assert result_state["user_id"] == "user123"
        assert result_state["retrieved_chunks"] == [{"chunk_id": "chunk1"}]

        # Verify new fields added
        assert result_state["intent"] == "content"
        assert result_state["metadata"]["existing_key"] == "existing_value"
        assert result_state["metadata"]["intent_confidence"] == 0.9

    @pytest.mark.asyncio
    async def test_classify_intent_llm_error_propagates(self):
        """Router propagates LLM errors without catching (V2)."""
        state: GraphState = {
            "user_query": "Test query",
            "user_id": "user123",
            "conversation_history": []
        }

        mock_llm_client = MagicMock()
        mock_llm_client.ainvoke_claude_structured = AsyncMock(
            side_effect=Exception("LLM API error")
        )

        with patch("app.rag.nodes.router_node.LLMClient", return_value=mock_llm_client):
            with pytest.raises(Exception, match="LLM API error"):
                await classify_intent(state)

    @pytest.mark.asyncio
    async def test_classify_intent_low_confidence(self):
        """Router handles low confidence classifications (V2)."""
        state: GraphState = {
            "user_query": "Hmm not sure what I want",
            "user_id": "user123",
            "conversation_history": []
        }

        mock_llm_client = MagicMock()
        mock_llm_client.ainvoke_claude_structured = AsyncMock(
            return_value=IntentClassification(
                intent="content",
                confidence=0.4,  # Low confidence
                reasoning="Ambiguous query, defaulting to content"
            )
        )

        with patch("app.rag.nodes.router_node.LLMClient", return_value=mock_llm_client):
            result_state = await classify_intent(state)

        # Should still classify even with low confidence
        assert result_state["intent"] == "content"
        assert result_state["metadata"]["intent_confidence"] == 0.4
        assert "ambiguous" in result_state["metadata"]["intent_reasoning"].lower()
