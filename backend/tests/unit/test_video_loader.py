"""
Unit Tests for Video Loader Module

Tests video loading confirmation flow, quota checking, and background ingestion.
"""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from app.api.websocket.video_loader import (
    PendingVideoLoad,
    check_user_quota,
    handle_video_load_intent,
    handle_confirmation_response,
    trigger_background_load,
    load_video_background,
    pending_loads,
)
from app.db.models import User, Transcript


@pytest.fixture
def mock_db():
    """Mock database session."""
    return AsyncMock()


@pytest.fixture
def mock_websocket():
    """Mock WebSocket connection."""
    ws = AsyncMock()
    ws.send_json = AsyncMock()
    return ws


@pytest.fixture
def admin_user():
    """Create mock admin user."""
    return User(
        id=uuid4(),
        email="admin@example.com",
        password_hash="hashed",
        role="admin",
        transcript_count=100,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )


@pytest.fixture
def regular_user():
    """Create mock regular user."""
    return User(
        id=uuid4(),
        email="user@example.com",
        password_hash="hashed",
        role="user",
        transcript_count=5,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )


@pytest.fixture
def user_at_quota():
    """Create mock user at quota limit."""
    return User(
        id=uuid4(),
        email="maxed@example.com",
        password_hash="hashed",
        role="user",
        transcript_count=10,  # At limit
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )


@pytest.fixture(autouse=True)
def clear_pending_loads():
    """Clear pending_loads dict before each test."""
    pending_loads.clear()
    yield
    pending_loads.clear()


class TestCheckUserQuota:
    """Tests for check_user_quota() function."""

    @pytest.mark.asyncio
    async def test_admin_always_allowed(self, admin_user, mock_db):
        """Admin users have unlimited quota."""
        allowed, message = await check_user_quota(admin_user, mock_db)

        assert allowed is True
        assert message == ""

    @pytest.mark.asyncio
    async def test_admin_with_high_count_allowed(self, mock_db):
        """Admin with 1000 videos still allowed."""
        admin = User(
            id=uuid4(),
            email="admin@example.com",
            password_hash="hashed",
            role="admin",
            transcript_count=1000,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        allowed, message = await check_user_quota(admin, mock_db)

        assert allowed is True
        assert message == ""

    @pytest.mark.asyncio
    async def test_regular_user_below_quota(self, regular_user, mock_db):
        """Regular user with 5 videos (below 10) is allowed."""
        allowed, message = await check_user_quota(regular_user, mock_db)

        assert allowed is True
        assert message == ""

    @pytest.mark.asyncio
    async def test_regular_user_at_quota(self, user_at_quota, mock_db):
        """Regular user with 10 videos (at limit) is blocked."""
        allowed, message = await check_user_quota(user_at_quota, mock_db)

        assert allowed is False
        assert "reached your video limit (10 videos)" in message
        assert "Delete some videos" in message

    @pytest.mark.asyncio
    async def test_regular_user_over_quota(self, mock_db):
        """Regular user with 15 videos (over limit) is blocked."""
        user = User(
            id=uuid4(),
            email="over@example.com",
            password_hash="hashed",
            role="user",
            transcript_count=15,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        allowed, message = await check_user_quota(user, mock_db)

        assert allowed is False
        assert "reached your video limit (10 videos)" in message


class TestHandleVideoLoadIntent:
    """Tests for handle_video_load_intent() function."""

    @pytest.mark.asyncio
    async def test_invalid_url(self, regular_user, mock_db, mock_websocket):
        """Invalid YouTube URL sends error message."""
        with patch("app.api.websocket.video_loader.detect_youtube_url", return_value=None):
            await handle_video_load_intent(
                youtube_url="not-a-youtube-url",
                user=regular_user,
                conversation_id="conv-123",
                db=mock_db,
                websocket=mock_websocket,
            )

        mock_websocket.send_json.assert_called_once()
        call_args = mock_websocket.send_json.call_args[0][0]
        assert call_args["type"] == "video_load_status"
        assert call_args["status"] == "failed"
        assert call_args["error"] == "INVALID_URL"

    @pytest.mark.asyncio
    async def test_duplicate_video(self, regular_user, mock_db, mock_websocket):
        """Duplicate video sends error message."""
        video_id = "abc123def456"

        # Mock: video ID extraction
        with patch("app.api.websocket.video_loader.detect_youtube_url", return_value=video_id):
            # Mock: existing transcript found
            existing_transcript = Transcript(
                id=uuid4(),
                user_id=regular_user.id,
                youtube_video_id=video_id,
                title="Existing Video",
                transcript_text="...",
                created_at=datetime(2025, 1, 15),
            )

            mock_transcript_repo = AsyncMock()
            mock_transcript_repo.get_by_video_id.return_value = existing_transcript

            with patch(
                "app.api.websocket.video_loader.TranscriptRepository",
                return_value=mock_transcript_repo,
            ):
                await handle_video_load_intent(
                    youtube_url=f"https://youtube.com/watch?v={video_id}",
                    user=regular_user,
                    conversation_id="conv-123",
                    db=mock_db,
                    websocket=mock_websocket,
                )

        mock_websocket.send_json.assert_called_once()
        call_args = mock_websocket.send_json.call_args[0][0]
        assert call_args["type"] == "video_load_status"
        assert call_args["status"] == "failed"
        assert call_args["error"] == "DUPLICATE_VIDEO"
        assert "already have this video" in call_args["message"]

    @pytest.mark.asyncio
    async def test_quota_exceeded(self, user_at_quota, mock_db, mock_websocket):
        """User at quota limit is blocked."""
        video_id = "abc123def456"

        with patch("app.api.websocket.video_loader.detect_youtube_url", return_value=video_id):
            # Mock: no duplicate
            mock_transcript_repo = AsyncMock()
            mock_transcript_repo.get_by_video_id.return_value = None

            with patch(
                "app.api.websocket.video_loader.TranscriptRepository",
                return_value=mock_transcript_repo,
            ):
                await handle_video_load_intent(
                    youtube_url=f"https://youtube.com/watch?v={video_id}",
                    user=user_at_quota,
                    conversation_id="conv-123",
                    db=mock_db,
                    websocket=mock_websocket,
                )

        mock_websocket.send_json.assert_called_once()
        call_args = mock_websocket.send_json.call_args[0][0]
        assert call_args["type"] == "video_load_status"
        assert call_args["status"] == "failed"
        assert call_args["error"] == "QUOTA_EXCEEDED"

    @pytest.mark.asyncio
    async def test_success_sends_confirmation(self, regular_user, mock_db, mock_websocket):
        """Valid request sends confirmation message and stores pending load."""
        video_id = "abc123def456"
        conversation_id = "conv-123"
        youtube_url = f"https://youtube.com/watch?v={video_id}"

        with patch("app.api.websocket.video_loader.detect_youtube_url", return_value=video_id):
            # Mock: no duplicate
            mock_transcript_repo = AsyncMock()
            mock_transcript_repo.get_by_video_id.return_value = None

            with patch(
                "app.api.websocket.video_loader.TranscriptRepository",
                return_value=mock_transcript_repo,
            ):
                await handle_video_load_intent(
                    youtube_url=youtube_url,
                    user=regular_user,
                    conversation_id=conversation_id,
                    db=mock_db,
                    websocket=mock_websocket,
                )

        # Check confirmation message sent
        mock_websocket.send_json.assert_called_once()
        call_args = mock_websocket.send_json.call_args[0][0]
        assert call_args["type"] == "video_load_confirmation"
        assert call_args["video_id"] == video_id
        assert call_args["youtube_url"] == youtube_url

        # Check pending load stored
        assert conversation_id in pending_loads
        pending = pending_loads[conversation_id]
        assert pending.video_id == video_id
        assert pending.user_id == regular_user.id


class TestHandleConfirmationResponse:
    """Tests for handle_confirmation_response() function."""

    @pytest.mark.asyncio
    async def test_no_pending_load(self, regular_user, mock_db, mock_websocket):
        """No pending load returns False (not handled)."""
        handled = await handle_confirmation_response(
            response="yes",
            conversation_id="conv-999",
            user_id=regular_user.id,
            db=mock_db,
            websocket=mock_websocket,
        )

        assert handled is False
        mock_websocket.send_json.assert_not_called()

    @pytest.mark.asyncio
    async def test_wrong_user(self, regular_user, mock_db, mock_websocket):
        """Wrong user cannot confirm load."""
        conversation_id = "conv-123"
        other_user_id = uuid4()

        # Store pending load for different user
        pending_loads[conversation_id] = PendingVideoLoad(
            conversation_id=conversation_id,
            youtube_url="https://youtube.com/watch?v=abc123",
            video_id="abc123",
            video_title=None,
            user_id=other_user_id,  # Different user
            created_at=datetime.utcnow(),
        )

        handled = await handle_confirmation_response(
            response="yes",
            conversation_id=conversation_id,
            user_id=regular_user.id,  # Wrong user
            db=mock_db,
            websocket=mock_websocket,
        )

        assert handled is False
        assert conversation_id in pending_loads  # Still pending

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "response",
        ["yes", "y", "yeah", "sure", "ok", "okay", "yep", "yup", "load it", "YES", "Yes"],
    )
    async def test_yes_patterns(self, response, regular_user, mock_db, mock_websocket):
        """Various 'yes' patterns trigger background load."""
        conversation_id = "conv-123"

        # Store pending load
        pending_loads[conversation_id] = PendingVideoLoad(
            conversation_id=conversation_id,
            youtube_url="https://youtube.com/watch?v=abc123",
            video_id="abc123",
            video_title=None,
            user_id=regular_user.id,
            created_at=datetime.utcnow(),
        )

        with patch("app.api.websocket.video_loader.trigger_background_load") as mock_trigger:
            handled = await handle_confirmation_response(
                response=response,
                conversation_id=conversation_id,
                user_id=regular_user.id,
                db=mock_db,
                websocket=mock_websocket,
            )

        assert handled is True
        mock_trigger.assert_called_once()
        assert conversation_id not in pending_loads  # Cleared

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "response", ["no", "n", "nope", "cancel", "don't", "stop", "NO", "No"]
    )
    async def test_no_patterns(self, response, regular_user, mock_db, mock_websocket):
        """Various 'no' patterns cancel load."""
        conversation_id = "conv-123"

        # Store pending load
        pending_loads[conversation_id] = PendingVideoLoad(
            conversation_id=conversation_id,
            youtube_url="https://youtube.com/watch?v=abc123",
            video_id="abc123",
            video_title=None,
            user_id=regular_user.id,
            created_at=datetime.utcnow(),
        )

        handled = await handle_confirmation_response(
            response=response,
            conversation_id=conversation_id,
            user_id=regular_user.id,
            db=mock_db,
            websocket=mock_websocket,
        )

        assert handled is True
        mock_websocket.send_json.assert_called_once()
        call_args = mock_websocket.send_json.call_args[0][0]
        assert call_args["type"] == "video_load_status"
        assert call_args["status"] == "failed"
        assert call_args["error"] == "USER_CANCELLED"
        assert conversation_id not in pending_loads  # Cleared

    @pytest.mark.asyncio
    async def test_ambiguous_response(self, regular_user, mock_db, mock_websocket):
        """Ambiguous response not handled as confirmation."""
        conversation_id = "conv-123"

        # Store pending load
        pending_loads[conversation_id] = PendingVideoLoad(
            conversation_id=conversation_id,
            youtube_url="https://youtube.com/watch?v=abc123",
            video_id="abc123",
            video_title=None,
            user_id=regular_user.id,
            created_at=datetime.utcnow(),
        )

        handled = await handle_confirmation_response(
            response="what is this video about?",  # Not yes/no
            conversation_id=conversation_id,
            user_id=regular_user.id,
            db=mock_db,
            websocket=mock_websocket,
        )

        assert handled is False
        assert conversation_id in pending_loads  # Still pending
        mock_websocket.send_json.assert_not_called()


class TestTriggerBackgroundLoad:
    """Tests for trigger_background_load() function."""

    @pytest.mark.asyncio
    async def test_sends_started_message(self, regular_user, mock_db, mock_websocket):
        """Sends 'started' status message."""
        with patch("app.api.websocket.video_loader.asyncio.create_task") as mock_create_task:
            await trigger_background_load(
                youtube_url="https://youtube.com/watch?v=abc123",
                user_id=regular_user.id,
                conversation_id="conv-123",
                db=mock_db,
                websocket=mock_websocket,
            )

        # Check status message sent
        mock_websocket.send_json.assert_called_once()
        call_args = mock_websocket.send_json.call_args[0][0]
        assert call_args["type"] == "video_load_status"
        assert call_args["status"] == "started"
        assert "Loading video in background" in call_args["message"]

        # Check background task created
        mock_create_task.assert_called_once()


class TestLoadVideoBackground:
    """Tests for load_video_background() background task."""

    @pytest.mark.asyncio
    async def test_success_flow(self, regular_user, mock_db, mock_websocket):
        """Successful video load increments quota and sends completion."""
        youtube_url = "https://youtube.com/watch?v=abc123"
        video_id = "abc123"

        # Mock TranscriptService
        mock_service = AsyncMock()
        mock_service.ingest_transcript.return_value = {
            "youtube_video_id": video_id,
            "metadata": {"title": "Test Video"},
        }

        # Mock UserRepository
        mock_user_repo = AsyncMock()

        with patch(
            "app.api.websocket.video_loader.TranscriptService", return_value=mock_service
        ), patch("app.api.websocket.video_loader.UserRepository", return_value=mock_user_repo):

            await load_video_background(
                youtube_url=youtube_url,
                user_id=regular_user.id,
                conversation_id="conv-123",
                db=mock_db,
                websocket=mock_websocket,
            )

        # Check ingestion called
        mock_service.ingest_transcript.assert_called_once_with(
            youtube_url=youtube_url, user_id=regular_user.id, db_session=mock_db
        )

        # Check quota incremented
        mock_user_repo.increment_transcript_count.assert_called_once_with(regular_user.id)

        # Check success message sent
        mock_websocket.send_json.assert_called_once()
        call_args = mock_websocket.send_json.call_args[0][0]
        assert call_args["type"] == "video_load_status"
        assert call_args["status"] == "completed"
        assert call_args["video_title"] == "Test Video"

    @pytest.mark.asyncio
    async def test_ingestion_failure(self, regular_user, mock_db, mock_websocket):
        """Failed ingestion sends error message."""
        youtube_url = "https://youtube.com/watch?v=abc123"

        # Mock TranscriptService failure
        mock_service = AsyncMock()
        mock_service.ingest_transcript.side_effect = Exception("Transcript not available")

        with patch(
            "app.api.websocket.video_loader.TranscriptService", return_value=mock_service
        ):

            await load_video_background(
                youtube_url=youtube_url,
                user_id=regular_user.id,
                conversation_id="conv-123",
                db=mock_db,
                websocket=mock_websocket,
            )

        # Check error message sent
        mock_websocket.send_json.assert_called_once()
        call_args = mock_websocket.send_json.call_args[0][0]
        assert call_args["type"] == "video_load_status"
        assert call_args["status"] == "failed"
        assert "Failed to load video" in call_args["message"]
