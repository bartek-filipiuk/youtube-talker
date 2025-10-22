"""
Unit Tests for WebSocket ConnectionManager
"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from app.api.websocket.connection_manager import ConnectionManager


@pytest.fixture
def connection_manager():
    """Fixture to create a fresh ConnectionManager instance for each test."""
    return ConnectionManager()


@pytest.fixture
def mock_websocket():
    """Fixture to create a mock WebSocket instance."""
    websocket = MagicMock()
    websocket.accept = AsyncMock()
    websocket.send_json = AsyncMock()
    return websocket


@pytest.fixture
def user_id():
    """Fixture to create a test user ID."""
    return uuid4()


@pytest.mark.asyncio
async def test_connect_new_user(connection_manager, mock_websocket, user_id):
    """Test connecting a new user's WebSocket."""
    await connection_manager.connect(mock_websocket, user_id)

    # Verify websocket.accept() was called
    mock_websocket.accept.assert_called_once()

    # Verify user is tracked
    assert user_id in connection_manager.active_connections
    assert mock_websocket in connection_manager.active_connections[user_id]
    assert len(connection_manager.active_connections[user_id]) == 1


@pytest.mark.asyncio
async def test_connect_multiple_connections_same_user(connection_manager, user_id):
    """Test connecting multiple WebSocket connections for the same user."""
    # Create two mock websockets
    ws1 = MagicMock()
    ws1.accept = AsyncMock()

    ws2 = MagicMock()
    ws2.accept = AsyncMock()

    # Connect both
    await connection_manager.connect(ws1, user_id)
    await connection_manager.connect(ws2, user_id)

    # Verify both are tracked
    assert len(connection_manager.active_connections[user_id]) == 2
    assert ws1 in connection_manager.active_connections[user_id]
    assert ws2 in connection_manager.active_connections[user_id]


@pytest.mark.asyncio
async def test_connect_multiple_users(connection_manager):
    """Test connecting WebSockets from different users."""
    user1_id = uuid4()
    user2_id = uuid4()

    ws1 = MagicMock()
    ws1.accept = AsyncMock()

    ws2 = MagicMock()
    ws2.accept = AsyncMock()

    await connection_manager.connect(ws1, user1_id)
    await connection_manager.connect(ws2, user2_id)

    # Verify both users are tracked separately
    assert user1_id in connection_manager.active_connections
    assert user2_id in connection_manager.active_connections
    assert len(connection_manager.active_connections) == 2


@pytest.mark.asyncio
async def test_disconnect_existing_connection(connection_manager, mock_websocket, user_id):
    """Test disconnecting an existing WebSocket connection."""
    # First connect
    await connection_manager.connect(mock_websocket, user_id)

    # Then disconnect
    await connection_manager.disconnect(mock_websocket, user_id)

    # Verify user entry is removed (no connections left)
    assert user_id not in connection_manager.active_connections


@pytest.mark.asyncio
async def test_disconnect_one_of_multiple_connections(connection_manager, user_id):
    """Test disconnecting one WebSocket when user has multiple connections."""
    ws1 = MagicMock()
    ws1.accept = AsyncMock()

    ws2 = MagicMock()
    ws2.accept = AsyncMock()

    # Connect both
    await connection_manager.connect(ws1, user_id)
    await connection_manager.connect(ws2, user_id)

    # Disconnect only ws1
    await connection_manager.disconnect(ws1, user_id)

    # Verify ws2 is still tracked
    assert user_id in connection_manager.active_connections
    assert ws1 not in connection_manager.active_connections[user_id]
    assert ws2 in connection_manager.active_connections[user_id]
    assert len(connection_manager.active_connections[user_id]) == 1


@pytest.mark.asyncio
async def test_disconnect_non_existent_connection(connection_manager, mock_websocket, user_id):
    """Test disconnecting a WebSocket that was never connected (should not error)."""
    # Disconnect without connecting first
    await connection_manager.disconnect(mock_websocket, user_id)

    # Should not raise error and should have no effect
    assert user_id not in connection_manager.active_connections


@pytest.mark.asyncio
async def test_send_json_success(connection_manager, mock_websocket, user_id):
    """Test sending JSON data through WebSocket."""
    await connection_manager.connect(mock_websocket, user_id)

    test_data = {"type": "message", "content": "Hello"}
    await connection_manager.send_json(mock_websocket, test_data)

    # Verify send_json was called with correct data
    mock_websocket.send_json.assert_called_once_with(test_data)


@pytest.mark.asyncio
async def test_send_json_failure(connection_manager, mock_websocket, user_id):
    """Test sending JSON when WebSocket send fails."""
    await connection_manager.connect(mock_websocket, user_id)

    # Make send_json raise an exception
    mock_websocket.send_json.side_effect = Exception("Connection closed")

    test_data = {"type": "message", "content": "Hello"}

    # Should raise the exception
    with pytest.raises(Exception, match="Connection closed"):
        await connection_manager.send_json(mock_websocket, test_data)


@pytest.mark.asyncio
async def test_get_user_connections_existing_user(connection_manager, user_id):
    """Test getting connections for a user who has active connections."""
    ws1 = MagicMock()
    ws1.accept = AsyncMock()

    ws2 = MagicMock()
    ws2.accept = AsyncMock()

    await connection_manager.connect(ws1, user_id)
    await connection_manager.connect(ws2, user_id)

    connections = connection_manager.get_user_connections(user_id)

    assert len(connections) == 2
    assert ws1 in connections
    assert ws2 in connections


@pytest.mark.asyncio
async def test_get_user_connections_non_existent_user(connection_manager):
    """Test getting connections for a user who has no active connections."""
    non_existent_user_id = uuid4()

    connections = connection_manager.get_user_connections(non_existent_user_id)

    # Should return empty set
    assert connections == set()
    assert len(connections) == 0


@pytest.mark.asyncio
async def test_get_total_connections_empty(connection_manager):
    """Test getting total connection count when no connections exist."""
    total = connection_manager.get_total_connections()
    assert total == 0


@pytest.mark.asyncio
async def test_get_total_connections_with_multiple_users(connection_manager):
    """Test getting total connection count across multiple users."""
    user1_id = uuid4()
    user2_id = uuid4()

    # User 1 has 2 connections
    ws1 = MagicMock()
    ws1.accept = AsyncMock()
    ws2 = MagicMock()
    ws2.accept = AsyncMock()

    # User 2 has 1 connection
    ws3 = MagicMock()
    ws3.accept = AsyncMock()

    await connection_manager.connect(ws1, user1_id)
    await connection_manager.connect(ws2, user1_id)
    await connection_manager.connect(ws3, user2_id)

    total = connection_manager.get_total_connections()
    assert total == 3


@pytest.mark.asyncio
async def test_disconnect_cleans_up_empty_user_entry(connection_manager, mock_websocket, user_id):
    """Test that disconnecting the last connection removes the user entry."""
    await connection_manager.connect(mock_websocket, user_id)

    # Verify user exists
    assert user_id in connection_manager.active_connections

    # Disconnect
    await connection_manager.disconnect(mock_websocket, user_id)

    # Verify user entry is completely removed (not just empty set)
    assert user_id not in connection_manager.active_connections
