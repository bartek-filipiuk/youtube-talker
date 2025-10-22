"""Unit tests for LinkedIn Flow."""

import pytest
from unittest.mock import AsyncMock, patch

from app.rag.graphs.flows.linkedin_flow import (
    build_linkedin_flow,
    run_linkedin_flow,
    compiled_linkedin_flow,
    retry_policy
)
from app.rag.utils.state import GraphState


class TestLinkedInFlow:
    """Unit tests for LinkedIn flow graph."""

    @pytest.mark.asyncio
    async def test_build_linkedin_flow_creates_compiled_graph(self):
        """Build function creates a compiled graph."""
        flow = build_linkedin_flow()

        # Verify it's compiled (has invoke methods)
        assert hasattr(flow, "ainvoke")
        assert hasattr(flow, "invoke")

    @pytest.mark.asyncio
    async def test_linkedin_flow_executes_full_pipeline(self):
        """LinkedIn flow executes all RAG steps in sequence."""
        state: GraphState = {
            "user_query": "Write a LinkedIn post about FastAPI",
            "user_id": "user123",
            "conversation_history": [],
            "intent": "linkedin"
        }

        # Mock each node in sequence
        mock_retrieved_state = {
            **state,
            "retrieved_chunks": [
                {"chunk_id": "chunk1", "chunk_text": "FastAPI is a modern web framework..."}
            ]
        }

        mock_graded_state = {
            **mock_retrieved_state,
            "graded_chunks": [
                {"chunk_id": "chunk1", "chunk_text": "FastAPI is a modern web framework..."}
            ],
            "metadata": {"relevant_count": 1}
        }

        mock_final_state = {
            **mock_graded_state,
            "response": "<p>📱 Excited to share insights about FastAPI! A modern web framework...</p>",
            "metadata": {
                **mock_graded_state.get("metadata", {}),
                "response_type": "linkedin",
                "chunks_used": 1,
                "source_chunks": ["chunk1"]
            }
        }

        with patch("app.rag.graphs.flows.linkedin_flow.retrieve_chunks", new=AsyncMock(return_value=mock_retrieved_state)), \
             patch("app.rag.graphs.flows.linkedin_flow.grade_chunks", new=AsyncMock(return_value=mock_graded_state)), \
             patch("app.rag.graphs.flows.linkedin_flow.generate_response", new=AsyncMock(return_value=mock_final_state)):

            flow = build_linkedin_flow()
            result = await flow.ainvoke(state)

        # Verify all steps completed
        assert "retrieved_chunks" in result
        assert "graded_chunks" in result
        assert "response" in result
        assert result["metadata"]["response_type"] == "linkedin"
        assert result["metadata"]["chunks_used"] == 1

    def test_run_linkedin_flow_exists(self):
        """run_linkedin_flow convenience function exists."""
        # Just verify the function exists and is callable
        assert callable(run_linkedin_flow)

    def test_compiled_linkedin_flow_is_ready(self):
        """Exported compiled_linkedin_flow is ready to use."""
        # Verify the compiled flow exists and has expected methods
        assert hasattr(compiled_linkedin_flow, "ainvoke")
        assert hasattr(compiled_linkedin_flow, "invoke")

    @pytest.mark.asyncio
    async def test_retry_policy_configuration(self):
        """Verify RetryPolicy is configured correctly."""
        assert retry_policy.max_attempts == 3
        assert retry_policy.backoff_factor == 2.0
        assert retry_policy.initial_interval == 1.0
        assert retry_policy.max_interval == 10.0
        assert retry_policy.jitter is True

    @pytest.mark.asyncio
    async def test_linkedin_flow_retriever_error_propagates(self):
        """Retriever errors propagate through the flow."""
        state: GraphState = {
            "user_query": "Write a post about testing",
            "user_id": "user123",
            "conversation_history": [],
            "intent": "linkedin"
        }

        # Mock retriever to raise error
        with patch("app.rag.graphs.flows.linkedin_flow.retrieve_chunks", new=AsyncMock(side_effect=Exception("Qdrant error"))):
            flow = build_linkedin_flow()

            with pytest.raises(Exception, match="Qdrant error"):
                await flow.ainvoke(state)

    @pytest.mark.asyncio
    async def test_linkedin_flow_grader_error_propagates(self):
        """Grader errors propagate through the flow."""
        state: GraphState = {
            "user_query": "Write a post",
            "user_id": "user123",
            "conversation_history": [],
            "intent": "linkedin"
        }

        mock_retrieved_state = {**state, "retrieved_chunks": [{"chunk_id": "chunk1"}]}

        with patch("app.rag.graphs.flows.linkedin_flow.retrieve_chunks", new=AsyncMock(return_value=mock_retrieved_state)), \
             patch("app.rag.graphs.flows.linkedin_flow.grade_chunks", new=AsyncMock(side_effect=Exception("LLM grading error"))):

            flow = build_linkedin_flow()

            with pytest.raises(Exception, match="LLM grading error"):
                await flow.ainvoke(state)

    @pytest.mark.asyncio
    async def test_run_linkedin_flow_convenience_function_executes(self):
        """run_linkedin_flow convenience function executes successfully."""
        state: GraphState = {
            "user_query": "Write a LinkedIn post about testing",
            "user_id": "user123",
            "conversation_history": [],
            "intent": "linkedin"
        }

        mock_result = {
            **state,
            "retrieved_chunks": [{"chunk_id": "chunk1", "chunk_text": "Testing is important..."}],
            "graded_chunks": [{"chunk_id": "chunk1", "chunk_text": "Testing is important..."}],
            "response": "<p>📱 Let's talk about testing! It's crucial for...</p>",
            "metadata": {
                "response_type": "linkedin",
                "chunks_used": 1,
                "source_chunks": ["chunk1"]
            }
        }

        # Mock the compiled flow's ainvoke method
        with patch("app.rag.graphs.flows.linkedin_flow.compiled_linkedin_flow.ainvoke", new=AsyncMock(return_value=mock_result)):
            result = await run_linkedin_flow(state)

        assert "LinkedIn" in result["response"] or "📱" in result["response"]
        assert result["metadata"]["response_type"] == "linkedin"
        assert result["metadata"]["chunks_used"] == 1
