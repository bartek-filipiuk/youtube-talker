"""Unit tests for Q&A Flow."""

import pytest
from unittest.mock import AsyncMock, patch

from app.rag.graphs.flows.qa_flow import (
    build_qa_flow,
    run_qa_flow,
    compiled_qa_flow,
    retry_policy
)
from app.rag.utils.state import GraphState


class TestQAFlow:
    """Unit tests for Q&A flow graph."""

    @pytest.mark.asyncio
    async def test_build_qa_flow_creates_compiled_graph(self):
        """Build function creates a compiled graph."""
        flow = build_qa_flow()

        # Verify it's compiled (has invoke methods)
        assert hasattr(flow, "ainvoke")
        assert hasattr(flow, "invoke")

    @pytest.mark.asyncio
    async def test_qa_flow_executes_full_pipeline(self):
        """Q&A flow executes all RAG steps in sequence."""
        state: GraphState = {
            "user_query": "What is FastAPI?",
            "user_id": "user123",
            "conversation_history": [],
            "intent": "qa"
        }

        # Mock each node in sequence
        mock_retrieved_state = {
            **state,
            "retrieved_chunks": [
                {"chunk_id": "chunk1", "chunk_text": "FastAPI is a framework..."}
            ]
        }

        mock_graded_state = {
            **mock_retrieved_state,
            "graded_chunks": [
                {"chunk_id": "chunk1", "chunk_text": "FastAPI is a framework..."}
            ],
            "metadata": {"relevant_count": 1}
        }

        mock_final_state = {
            **mock_graded_state,
            "response": "<p>FastAPI is a modern web framework for Python.</p>",
            "metadata": {
                **mock_graded_state.get("metadata", {}),
                "response_type": "qa",
                "chunks_used": 1,
                "source_chunks": ["chunk1"]
            }
        }

        with patch("app.rag.graphs.flows.qa_flow.retrieve_chunks", new=AsyncMock(return_value=mock_retrieved_state)), \
             patch("app.rag.graphs.flows.qa_flow.grade_chunks", new=AsyncMock(return_value=mock_graded_state)), \
             patch("app.rag.graphs.flows.qa_flow.generate_response", new=AsyncMock(return_value=mock_final_state)):

            flow = build_qa_flow()
            result = await flow.ainvoke(state)

        # Verify all steps completed
        assert "retrieved_chunks" in result
        assert "graded_chunks" in result
        assert "response" in result
        assert result["metadata"]["response_type"] == "qa"
        assert result["metadata"]["chunks_used"] == 1

    def test_run_qa_flow_exists(self):
        """run_qa_flow convenience function exists."""
        # Just verify the function exists and is callable
        assert callable(run_qa_flow)
        # Note: Actual invocation tested in build_qa_flow tests above

    def test_compiled_qa_flow_is_ready(self):
        """Exported compiled_qa_flow is ready to use."""
        # Verify the compiled flow exists and has expected methods
        assert hasattr(compiled_qa_flow, "ainvoke")
        assert hasattr(compiled_qa_flow, "invoke")

    @pytest.mark.asyncio
    async def test_retry_policy_configuration(self):
        """Verify RetryPolicy is configured correctly."""
        assert retry_policy.max_attempts == 3
        assert retry_policy.backoff_factor == 2.0
        assert retry_policy.initial_interval == 1.0
        assert retry_policy.max_interval == 10.0
        assert retry_policy.jitter is True

    @pytest.mark.asyncio
    async def test_qa_flow_retriever_error_propagates(self):
        """Retriever errors propagate through the flow."""
        state: GraphState = {
            "user_query": "Test",
            "user_id": "user123",
            "conversation_history": [],
            "intent": "qa"
        }

        # Mock retriever to raise error
        with patch("app.rag.graphs.flows.qa_flow.retrieve_chunks", new=AsyncMock(side_effect=Exception("Qdrant error"))):
            flow = build_qa_flow()

            with pytest.raises(Exception, match="Qdrant error"):
                await flow.ainvoke(state)

    @pytest.mark.asyncio
    async def test_qa_flow_grader_error_propagates(self):
        """Grader errors propagate through the flow."""
        state: GraphState = {
            "user_query": "Test",
            "user_id": "user123",
            "conversation_history": [],
            "intent": "qa"
        }

        mock_retrieved_state = {**state, "retrieved_chunks": [{"chunk_id": "chunk1"}]}

        with patch("app.rag.graphs.flows.qa_flow.retrieve_chunks", new=AsyncMock(return_value=mock_retrieved_state)), \
             patch("app.rag.graphs.flows.qa_flow.grade_chunks", new=AsyncMock(side_effect=Exception("LLM grading error"))):

            flow = build_qa_flow()

            with pytest.raises(Exception, match="LLM grading error"):
                await flow.ainvoke(state)

    @pytest.mark.asyncio
    async def test_run_qa_flow_convenience_function_executes(self):
        """run_qa_flow convenience function executes successfully."""
        state: GraphState = {
            "user_query": "What is FastAPI?",
            "user_id": "user123",
            "conversation_history": [],
            "intent": "qa"
        }

        mock_result = {
            **state,
            "retrieved_chunks": [{"chunk_id": "chunk1", "chunk_text": "FastAPI is..."}],
            "graded_chunks": [{"chunk_id": "chunk1", "chunk_text": "FastAPI is..."}],
            "response": "<p>FastAPI is a modern web framework.</p>",
            "metadata": {
                "response_type": "qa",
                "chunks_used": 1,
                "source_chunks": ["chunk1"]
            }
        }

        # Mock the compiled flow's ainvoke method
        with patch("app.rag.graphs.flows.qa_flow.compiled_qa_flow.ainvoke", new=AsyncMock(return_value=mock_result)):
            result = await run_qa_flow(state)

        assert result["response"] == "<p>FastAPI is a modern web framework.</p>"
        assert result["metadata"]["response_type"] == "qa"
        assert result["metadata"]["chunks_used"] == 1
