"""Unit tests for Chitchat Flow."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.rag.graphs.flows.chitchat_flow import (
    build_chitchat_flow,
    run_chitchat_flow,
    compiled_chitchat_flow
)
from app.rag.utils.state import GraphState


class TestChitchatFlow:
    """Unit tests for chitchat flow graph."""

    @pytest.mark.asyncio
    async def test_build_chitchat_flow_creates_compiled_graph(self):
        """Build function creates a compiled graph."""
        flow = build_chitchat_flow()

        # Verify it's compiled (has invoke methods)
        assert hasattr(flow, "ainvoke")
        assert hasattr(flow, "invoke")

    @pytest.mark.asyncio
    async def test_chitchat_flow_executes_successfully(self):
        """Chitchat flow executes and generates response."""
        state: GraphState = {
            "user_query": "Hello! How are you?",
            "user_id": "user123",
            "conversation_history": [],
            "intent": "chitchat"
        }

        # Mock generator node
        mock_generator_response = {
            **state,
            "response": "<p>Hi! I'm doing great, thanks for asking!</p>",
            "metadata": {
                "response_type": "chitchat",
                "chunks_used": 0
            }
        }

        with patch("app.rag.graphs.flows.chitchat_flow.generate_response", new=AsyncMock(return_value=mock_generator_response)):
            flow = build_chitchat_flow()
            result = await flow.ainvoke(state)

        # Verify response generated
        assert "response" in result
        assert "Hi!" in result["response"]
        assert result["metadata"]["response_type"] == "chitchat"
        assert result["metadata"]["chunks_used"] == 0

    @pytest.mark.asyncio
    async def test_chitchat_flow_preserves_state_fields(self):
        """Chitchat flow preserves all input state fields."""
        state: GraphState = {
            "user_query": "Test query",
            "user_id": "user123",
            "conversation_history": [
                {"role": "user", "content": "Previous message"}
            ],
            "intent": "chitchat"
        }

        mock_response = {
            **state,
            "response": "<p>Response</p>",
            "metadata": {"response_type": "chitchat", "chunks_used": 0}
        }

        with patch("app.rag.graphs.flows.chitchat_flow.generate_response", new=AsyncMock(return_value=mock_response)):
            flow = build_chitchat_flow()
            result = await flow.ainvoke(state)

        # Verify all original fields preserved
        assert result["user_query"] == "Test query"
        assert result["user_id"] == "user123"
        assert len(result["conversation_history"]) == 1
        assert result["intent"] == "chitchat"

    def test_run_chitchat_flow_exists(self):
        """run_chitchat_flow convenience function exists."""
        # Just verify the function exists and is callable
        assert callable(run_chitchat_flow)
        # Note: Actual invocation tested in build_chitchat_flow tests above

    def test_compiled_chitchat_flow_is_ready(self):
        """Exported compiled_chitchat_flow is ready to use."""
        # Verify the compiled flow exists and has expected methods
        assert hasattr(compiled_chitchat_flow, "ainvoke")
        assert hasattr(compiled_chitchat_flow, "invoke")

    @pytest.mark.asyncio
    async def test_chitchat_flow_generator_error_propagates(self):
        """Generator errors propagate through the flow."""
        state: GraphState = {
            "user_query": "Test",
            "user_id": "user123",
            "conversation_history": [],
            "intent": "chitchat"
        }

        # Mock generator to raise error
        with patch("app.rag.graphs.flows.chitchat_flow.generate_response", new=AsyncMock(side_effect=Exception("LLM error"))):
            flow = build_chitchat_flow()

            with pytest.raises(Exception, match="LLM error"):
                await flow.ainvoke(state)

    @pytest.mark.asyncio
    async def test_run_chitchat_flow_convenience_function_executes(self):
        """run_chitchat_flow convenience function executes successfully."""
        state: GraphState = {
            "user_query": "Hello!",
            "user_id": "user123",
            "conversation_history": [],
            "intent": "chitchat"
        }

        mock_result = {
            **state,
            "response": "<p>Hi there!</p>",
            "metadata": {"response_type": "chitchat", "chunks_used": 0}
        }

        # Mock the compiled flow's ainvoke method
        with patch("app.rag.graphs.flows.chitchat_flow.compiled_chitchat_flow.ainvoke", new=AsyncMock(return_value=mock_result)):
            result = await run_chitchat_flow(state)

        assert result["response"] == "<p>Hi there!</p>"
        assert result["metadata"]["response_type"] == "chitchat"
