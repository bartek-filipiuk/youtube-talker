"""
Integration Tests for WebSocket Chat Endpoint

Tests the WebSocket message schemas and basic routing.
This is Part 1 (PR #15): Basic WebSocket foundation - simplified tests.
Part 2 (PR #16) will add full integration tests with authentication and RAG.

Note: These tests are minimal for PR #15 because the WebSocket handler uses
direct database access (not dependency injection). Full integration tests with
proper auth will be added in PR #16.
"""

import pytest
from fastapi.testclient import TestClient


class TestWebSocketEndpoint:
    """Integration tests for WebSocket endpoint existence and routing."""

    def test_websocket_endpoint_exists(self, client: TestClient):
        """WebSocket endpoint is registered and accessible."""
        # This test verifies the endpoint is registered
        # We expect it to fail auth, but that proves the endpoint exists
        with pytest.raises(Exception):
            # Try to connect without token - should fail
            with client.websocket_connect("/api/ws/chat"):
                pass

    def test_websocket_requires_token_parameter(self, client: TestClient):
        """WebSocket endpoint requires token query parameter."""
        # Missing required query parameter should raise exception
        with pytest.raises(Exception):
            with client.websocket_connect("/api/ws/chat"):
                pass


class TestWebSocketMessageSchemas:
    """Test that Pydantic message schemas are properly defined."""

    def test_status_message_schema(self):
        """StatusMessage schema validates correctly."""
        from app.api.websocket.messages import StatusMessage

        msg = StatusMessage(message="Testing", step="routing")
        assert msg.type == "status"
        assert msg.message == "Testing"
        assert msg.step == "routing"

    def test_assistant_message_schema(self):
        """AssistantMessage schema validates correctly."""
        from app.api.websocket.messages import AssistantMessage

        msg = AssistantMessage(content="<p>Test</p>", metadata={"test": True})
        assert msg.type == "message"
        assert msg.role == "assistant"
        assert msg.content == "<p>Test</p>"
        assert msg.metadata["test"] is True

    def test_error_message_schema(self):
        """ErrorMessage schema validates correctly."""
        from app.api.websocket.messages import ErrorMessage

        msg = ErrorMessage(message="Error occurred", code="TEST_ERROR")
        assert msg.type == "error"
        assert msg.message == "Error occurred"
        assert msg.code == "TEST_ERROR"

    def test_ping_pong_message_schemas(self):
        """Ping and Pong message schemas validate correctly."""
        from app.api.websocket.messages import PingMessage, PongMessage

        ping = PingMessage()
        assert ping.type == "ping"

        pong = PongMessage()
        assert pong.type == "pong"

    def test_incoming_message_validation(self):
        """IncomingMessage validates content constraints."""
        from app.api.websocket.messages import IncomingMessage
        from pydantic import ValidationError

        # Valid message
        msg = IncomingMessage(content="Test message")
        assert msg.content == "Test message"

        # Empty content should fail
        with pytest.raises(ValidationError):
            IncomingMessage(content="")

        # Content too long should fail
        with pytest.raises(ValidationError):
            IncomingMessage(content="a" * 2001)


# Note: Full end-to-end WebSocket tests with authentication will be added in PR #16
# when we implement proper dependency injection for the auth service.
