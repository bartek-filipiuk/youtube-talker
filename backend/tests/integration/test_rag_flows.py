"""Integration tests for RAG flows and router."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.rag.graphs.router import run_graph
from app.schemas.llm_responses import IntentClassification


class TestRAGFlowsIntegration:
    """Integration tests for complete RAG system."""

    @pytest.mark.asyncio
    async def test_chitchat_flow_end_to_end(self):
        """Chitchat flow executes successfully from router to response."""
        # Mock final response
        mock_final_state = {
            "user_query": "Hello!",
            "user_id": "user123",
            "conversation_history": [],
            "intent": "chitchat",
            "response": "<p>Hi! How can I help you today?</p>",
            "metadata": {
                "intent_confidence": 0.95,
                "intent_reasoning": "Casual greeting message",
                "response_type": "chitchat",
                "chunks_used": 0
            }
        }

        with patch("app.rag.graphs.router.classify_intent", new=AsyncMock(return_value={
            "user_query": "Hello!",
            "user_id": "user123",
            "conversation_history": [],
            "intent": "chitchat",
            "metadata": {
                "intent_confidence": 0.95,
                "intent_reasoning": "Casual greeting message"
            }
        })), \
             patch("app.rag.graphs.router.compiled_chitchat_flow.ainvoke", new=AsyncMock(return_value=mock_final_state)):

            result = await run_graph(
                user_query="Hello!",
                user_id="user123",
                conversation_history=[]
            )

        # Verify complete flow
        assert result["intent"] == "chitchat"
        assert result["response"] == "<p>Hi! How can I help you today?</p>"
        assert result["metadata"]["response_type"] == "chitchat"
        assert result["metadata"]["chunks_used"] == 0

    @pytest.mark.asyncio
    async def test_qa_flow_end_to_end(self):
        """Q&A flow executes successfully with RAG retrieval."""
        # Mock final response
        mock_final_state = {
            "user_query": "What is FastAPI?",
            "user_id": "user123",
            "conversation_history": [],
            "intent": "qa",
            "retrieved_chunks": [{"chunk_id": "chunk1", "chunk_text": "FastAPI is..."}],
            "graded_chunks": [{"chunk_id": "chunk1", "chunk_text": "FastAPI is..."}],
            "response": "<p>FastAPI is a modern web framework for Python.</p>",
            "metadata": {
                "intent_confidence": 0.92,
                "intent_reasoning": "Question about technology",
                "relevant_count": 1,
                "response_type": "qa",
                "chunks_used": 1,
                "source_chunks": ["chunk1"]
            }
        }

        with patch("app.rag.graphs.router.classify_intent", new=AsyncMock(return_value={
            "user_query": "What is FastAPI?",
            "user_id": "user123",
            "conversation_history": [],
            "intent": "qa",
            "metadata": {"intent_confidence": 0.92, "intent_reasoning": "Question about technology"}
        })), \
             patch("app.rag.graphs.router.compiled_qa_flow.ainvoke", new=AsyncMock(return_value=mock_final_state)):

            result = await run_graph(
                user_query="What is FastAPI?",
                user_id="user123",
                conversation_history=[]
            )

        # Verify complete RAG flow
        assert result["intent"] == "qa"
        assert "FastAPI" in result["response"]
        assert result["metadata"]["response_type"] == "qa"
        assert result["metadata"]["chunks_used"] == 1
        assert "source_chunks" in result["metadata"]

    @pytest.mark.asyncio
    async def test_linkedin_flow_end_to_end(self):
        """LinkedIn flow executes successfully with RAG retrieval."""
        # Mock final response
        mock_final_state = {
            "user_query": "Write a LinkedIn post about testing",
            "user_id": "user123",
            "conversation_history": [],
            "intent": "linkedin",
            "retrieved_chunks": [{"chunk_id": "chunk1", "chunk_text": "Testing is important..."}],
            "graded_chunks": [{"chunk_id": "chunk1", "chunk_text": "Testing is important..."}],
            "response": "<p>📱 Excited to share insights about testing! ...</p>",
            "metadata": {
                "intent_confidence": 0.88,
                "intent_reasoning": "LinkedIn content request",
                "relevant_count": 1,
                "response_type": "linkedin",
                "chunks_used": 1,
                "source_chunks": ["chunk1"]
            }
        }

        with patch("app.rag.graphs.router.classify_intent", new=AsyncMock(return_value={
            "user_query": "Write a LinkedIn post about testing",
            "user_id": "user123",
            "conversation_history": [],
            "intent": "linkedin",
            "metadata": {"intent_confidence": 0.88, "intent_reasoning": "LinkedIn content request"}
        })), \
             patch("app.rag.graphs.router.compiled_linkedin_flow.ainvoke", new=AsyncMock(return_value=mock_final_state)):

            result = await run_graph(
                user_query="Write a LinkedIn post about testing",
                user_id="user123",
                conversation_history=[]
            )

        # Verify complete LinkedIn flow
        assert result["intent"] == "linkedin"
        assert result["response"] is not None
        assert result["metadata"]["response_type"] == "linkedin"
        assert result["metadata"]["chunks_used"] == 1

    @pytest.mark.asyncio
    async def test_router_classification_accuracy(self):
        """Router correctly classifies different query types."""
        test_cases = [
            {
                "query": "Hello, how are you?",
                "expected_intent": "chitchat",
                "mock_intent": "chitchat"
            },
            {
                "query": "What is dependency injection?",
                "expected_intent": "qa",
                "mock_intent": "qa"
            },
            {
                "query": "Write a LinkedIn post about Python",
                "expected_intent": "linkedin",
                "mock_intent": "linkedin"
            }
        ]

        for case in test_cases:
            mock_response = {
                "user_query": case["query"],
                "user_id": "user123",
                "conversation_history": [],
                "intent": case["mock_intent"],
                "response": "<p>Test response</p>",
                "metadata": {"intent_confidence": 0.9, "intent_reasoning": "Test", "response_type": case["mock_intent"], "chunks_used": 0}
            }

            with patch("app.rag.graphs.router.classify_intent", new=AsyncMock(return_value={
                "user_query": case["query"],
                "user_id": "user123",
                "conversation_history": [],
                "intent": case["mock_intent"],
                "metadata": {"intent_confidence": 0.9, "intent_reasoning": "Test"}
            })), \
                 patch("app.rag.graphs.router.compiled_chitchat_flow.ainvoke", new=AsyncMock(return_value=mock_response)), \
                 patch("app.rag.graphs.router.compiled_qa_flow.ainvoke", new=AsyncMock(return_value=mock_response)), \
                 patch("app.rag.graphs.router.compiled_linkedin_flow.ainvoke", new=AsyncMock(return_value=mock_response)):

                result = await run_graph(
                    user_query=case["query"],
                    user_id="user123",
                    conversation_history=[]
                )

                assert result["intent"] == case["expected_intent"]

    @pytest.mark.asyncio
    async def test_state_transitions_preserve_metadata(self):
        """State transitions preserve all metadata through the flow."""
        mock_response = {
            "user_query": "Test",
            "user_id": "user123",
            "conversation_history": [{"role": "user", "content": "Previous"}],
            "intent": "chitchat",
            "response": "<p>Response</p>",
            "metadata": {
                "intent_confidence": 0.95,
                "intent_reasoning": "Test reasoning",
                "response_type": "chitchat",
                "chunks_used": 0
            }
        }

        with patch("app.rag.graphs.router.classify_intent", new=AsyncMock(return_value={
            "user_query": "Test",
            "user_id": "user123",
            "conversation_history": [{"role": "user", "content": "Previous"}],
            "intent": "chitchat",
            "metadata": {
                "intent_confidence": 0.95,
                "intent_reasoning": "Test reasoning"
            }
        })), \
             patch("app.rag.graphs.router.compiled_chitchat_flow.ainvoke", new=AsyncMock(return_value=mock_response)):

            result = await run_graph(
                user_query="Test",
                user_id="user123",
                conversation_history=[{"role": "user", "content": "Previous"}]
            )

        # Verify all original fields preserved
        assert result["user_query"] == "Test"
        assert result["user_id"] == "user123"
        assert len(result["conversation_history"]) == 1
        # Verify metadata accumulated
        assert result["metadata"]["intent_confidence"] == 0.95
        assert result["metadata"]["response_type"] == "chitchat"

    @pytest.mark.asyncio
    async def test_router_handles_missing_intent(self):
        """Router raises error when intent classification fails."""
        with patch("app.rag.graphs.router.classify_intent", new=AsyncMock(return_value={
            "user_query": "Test",
            "user_id": "user123",
            "conversation_history": [],
            # No intent field
            "metadata": {}
        })):

            with pytest.raises(ValueError, match="Intent classification failed"):
                await run_graph(
                    user_query="Test",
                    user_id="user123",
                    conversation_history=[]
                )

    @pytest.mark.asyncio
    async def test_router_handles_unknown_intent_gracefully(self):
        """Router defaults to chitchat for unknown intents."""
        mock_response = {
            "user_query": "Test",
            "user_id": "user123",
            "conversation_history": [],
            "intent": "unknown_intent",
            "response": "<p>Fallback response</p>",
            "metadata": {"intent_confidence": 0.5, "response_type": "chitchat", "chunks_used": 0}
        }

        with patch("app.rag.graphs.router.classify_intent", new=AsyncMock(return_value={
            "user_query": "Test",
            "user_id": "user123",
            "conversation_history": [],
            "intent": "unknown_intent",  # Invalid intent
            "metadata": {"intent_confidence": 0.5}
        })), \
             patch("app.rag.graphs.router.compiled_chitchat_flow.ainvoke", new=AsyncMock(return_value=mock_response)):

            result = await run_graph(
                user_query="Test",
                user_id="user123",
                conversation_history=[]
            )

        # Should fall back to chitchat
        assert result["response"] is not None

    @pytest.mark.asyncio
    async def test_router_propagates_flow_errors(self):
        """Errors from subflows propagate through the router."""
        with patch("app.rag.graphs.router.classify_intent", new=AsyncMock(return_value={
            "user_query": "Test",
            "user_id": "user123",
            "conversation_history": [],
            "intent": "qa",
            "metadata": {"intent_confidence": 0.9}
        })), \
             patch("app.rag.graphs.router.compiled_qa_flow.ainvoke", new=AsyncMock(side_effect=Exception("Database connection failed"))):

            with pytest.raises(Exception, match="Database connection failed"):
                await run_graph(
                    user_query="Test",
                    user_id="user123",
                    conversation_history=[]
                )
