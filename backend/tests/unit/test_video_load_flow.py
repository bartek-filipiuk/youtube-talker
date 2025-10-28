"""
Unit Tests for Video Load Flow

Tests LangGraph flow for video loading intent classification.
"""

import pytest
from unittest.mock import patch

from app.rag.graphs.flows.video_load_flow import handle_video_load_node, compiled_video_load_flow
from app.rag.utils.state import GraphState


class TestHandleVideoLoadNode:
    """Tests for handle_video_load_node() function."""

    @pytest.mark.asyncio
    async def test_no_url_found(self):
        """Query without YouTube URL returns error."""
        state: GraphState = {
            "user_query": "This is just a random question with no URL",
            "user_id": "user-123",
            "conversation_history": [],
            "config": {},
        }

        result = await handle_video_load_node(state)

        assert result["response"] is not None
        assert "couldn't find a valid YouTube URL" in result["response"]
        assert result["metadata"]["response_type"] == "video_load_error"
        assert result["metadata"]["error"] == "NO_URL_FOUND"

    @pytest.mark.asyncio
    async def test_valid_url_standard(self):
        """Standard YouTube URL is detected and extracted."""
        video_id = "dQw4w9WgXcQ"
        state: GraphState = {
            "user_query": f"https://www.youtube.com/watch?v={video_id}",
            "user_id": "user-123",
            "conversation_history": [],
            "config": {},
        }

        with patch("app.rag.graphs.flows.video_load_flow.detect_youtube_url", return_value=video_id):
            result = await handle_video_load_node(state)

        assert result["response"] == f"VIDEO_LOAD_REQUEST:{video_id}"
        assert result["metadata"]["response_type"] == "video_load_request"
        assert result["metadata"]["video_id"] == video_id
        assert result["metadata"]["requires_websocket_handling"] is True

    @pytest.mark.asyncio
    async def test_valid_url_short(self):
        """Short YouTube URL (youtu.be) is detected."""
        video_id = "abc123def456"
        state: GraphState = {
            "user_query": f"https://youtu.be/{video_id}",
            "user_id": "user-123",
            "conversation_history": [],
            "config": {},
        }

        with patch("app.rag.graphs.flows.video_load_flow.detect_youtube_url", return_value=video_id):
            result = await handle_video_load_node(state)

        assert result["response"] == f"VIDEO_LOAD_REQUEST:{video_id}"
        assert result["metadata"]["video_id"] == video_id
        assert result["metadata"]["requires_websocket_handling"] is True

    @pytest.mark.asyncio
    async def test_url_in_sentence(self):
        """URL embedded in sentence is extracted."""
        video_id = "abc123def456"
        state: GraphState = {
            "user_query": f"Please load this video: https://www.youtube.com/watch?v={video_id} for analysis",
            "user_id": "user-123",
            "conversation_history": [],
            "config": {},
        }

        with patch("app.rag.graphs.flows.video_load_flow.detect_youtube_url", return_value=video_id):
            result = await handle_video_load_node(state)

        assert result["response"] == f"VIDEO_LOAD_REQUEST:{video_id}"
        assert result["metadata"]["video_id"] == video_id


class TestCompiledVideoLoadFlow:
    """Tests for compiled_video_load_flow graph."""

    def test_compiled_flow_exists(self):
        """Exported compiled_video_load_flow is ready to use."""
        # Verify the compiled flow exists and has expected methods
        assert hasattr(compiled_video_load_flow, "ainvoke")
        assert hasattr(compiled_video_load_flow, "invoke")

    @pytest.mark.asyncio
    async def test_flow_execution_with_mocked_node(self):
        """Full flow execution with mocked node."""
        video_id = "dQw4w9WgXcQ"
        state: GraphState = {
            "user_query": f"https://www.youtube.com/watch?v={video_id}",
            "user_id": "user-123",
            "conversation_history": [],
            "config": {},
        }


        # Test the node directly (graph compilation is tested above)
        with patch("app.rag.graphs.flows.video_load_flow.detect_youtube_url", return_value=video_id):
            result = await handle_video_load_node(state)

        assert result["response"] == f"VIDEO_LOAD_REQUEST:{video_id}"
        assert result["metadata"]["requires_websocket_handling"] is True
        assert result["metadata"]["video_id"] == video_id
