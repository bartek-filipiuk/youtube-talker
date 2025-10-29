"""
Unit Tests for Video Loader Module

Tests video loading confirmation flow, quota checking, and background ingestion.
"""

import pytest
from datetime import datetime, timezone, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from app.api.websocket.video_loader import (
    PendingVideoLoad,
    VideoMetadata,
    check_user_quota,
    handle_video_load_intent,
    handle_confirmation_response,
    trigger_background_load,
    load_video_background,
    pending_loads,
    video_metadata_cache,
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
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
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
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
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
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


@pytest.fixture(autouse=True)
def clear_pending_loads():
    """Clear pending_loads and video_metadata_cache dicts before each test."""
    pending_loads.clear()
    video_metadata_cache.clear()
    yield
    pending_loads.clear()
    video_metadata_cache.clear()


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
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
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
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
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

        # Should send 2 messages: status "Checking video..." then error message
        assert mock_websocket.send_json.call_count == 2

        # Check first call is status message
        first_call = mock_websocket.send_json.call_args_list[0][0][0]
        assert first_call["type"] == "status"
        assert first_call["message"] == "Checking video..."

        # Check second call is error message
        second_call = mock_websocket.send_json.call_args_list[1][0][0]
        assert second_call["type"] == "video_load_status"
        assert second_call["status"] == "failed"
        assert second_call["error"] == "DUPLICATE_VIDEO"
        assert "already have this video" in second_call["message"]

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
            ), patch(
                "app.api.websocket.video_loader.fetch_video_duration",
                new_callable=AsyncMock,
                return_value=(7200, "Test Video")  # 2 hour video
            ):
                await handle_video_load_intent(
                    youtube_url=f"https://youtube.com/watch?v={video_id}",
                    user=user_at_quota,
                    conversation_id="conv-123",
                    db=mock_db,
                    websocket=mock_websocket,
                )

        # Should send 2 messages: status "Checking video..." then error message
        assert mock_websocket.send_json.call_count == 2

        # Check first call is status message
        first_call = mock_websocket.send_json.call_args_list[0][0][0]
        assert first_call["type"] == "status"
        assert first_call["message"] == "Checking video..."

        # Check second call is error message
        second_call = mock_websocket.send_json.call_args_list[1][0][0]
        assert second_call["type"] == "video_load_status"
        assert second_call["status"] == "failed"
        assert second_call["error"] == "QUOTA_EXCEEDED"

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
            ), patch(
                "app.api.websocket.video_loader.fetch_video_duration",
                new_callable=AsyncMock,
                return_value=(7200, "Test Video")  # 2 hour video
            ):
                await handle_video_load_intent(
                    youtube_url=youtube_url,
                    user=regular_user,
                    conversation_id=conversation_id,
                    db=mock_db,
                    websocket=mock_websocket,
                )

        # Should send 2 messages: status "Checking video..." then confirmation
        assert mock_websocket.send_json.call_count == 2

        # Check first call is status message
        first_call = mock_websocket.send_json.call_args_list[0][0][0]
        assert first_call["type"] == "status"
        assert first_call["message"] == "Checking video..."

        # Check second call is confirmation message
        second_call = mock_websocket.send_json.call_args_list[1][0][0]
        assert second_call["type"] == "video_load_confirmation"
        assert second_call["video_id"] == video_id
        assert second_call["youtube_url"] == youtube_url

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
            created_at=datetime.now(timezone.utc),
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
            created_at=datetime.now(timezone.utc),
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
            created_at=datetime.now(timezone.utc),
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
            created_at=datetime.now(timezone.utc),
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

        # Mock AsyncSessionLocal context manager
        mock_session = AsyncMock()
        mock_session_ctx = AsyncMock()
        mock_session_ctx.__aenter__.return_value = mock_session
        mock_session_ctx.__aexit__.return_value = None

        with patch(
            "app.api.websocket.video_loader.TranscriptService", return_value=mock_service
        ), patch(
            "app.api.websocket.video_loader.UserRepository", return_value=mock_user_repo
        ), patch(
            "app.api.websocket.video_loader.AsyncSessionLocal", return_value=mock_session_ctx
        ):

            await load_video_background(
                youtube_url=youtube_url,
                user_id=regular_user.id,
                conversation_id="conv-123",
                websocket=mock_websocket,
            )

        # Check ingestion called with new session
        mock_service.ingest_transcript.assert_called_once_with(
            youtube_url=youtube_url, user_id=regular_user.id, db_session=mock_session
        )

        # Check quota incremented
        mock_user_repo.increment_transcript_count.assert_called_once_with(regular_user.id)

        # Check session committed
        mock_session.commit.assert_called_once()

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

        # Mock AsyncSessionLocal context manager
        mock_session = AsyncMock()
        mock_session_ctx = AsyncMock()
        mock_session_ctx.__aenter__.return_value = mock_session
        mock_session_ctx.__aexit__.return_value = None

        with patch(
            "app.api.websocket.video_loader.TranscriptService", return_value=mock_service
        ), patch(
            "app.api.websocket.video_loader.AsyncSessionLocal", return_value=mock_session_ctx
        ):

            await load_video_background(
                youtube_url=youtube_url,
                user_id=regular_user.id,
                conversation_id="conv-123",
                websocket=mock_websocket,
            )

        # Check session rollback called on error
        mock_session.rollback.assert_called_once()

        # Check error message sent
        mock_websocket.send_json.assert_called_once()
        call_args = mock_websocket.send_json.call_args[0][0]
        assert call_args["type"] == "video_load_status"
        assert call_args["status"] == "failed"
        assert "Failed to load video" in call_args["message"]


class TestCheckDurationLimit:
    """Tests for check_duration_limit() function."""

    @pytest.mark.asyncio
    async def test_admin_unlimited_duration(self, admin_user):
        """Admin users have no duration limit."""
        from app.api.websocket.video_loader import check_duration_limit

        # Test with extremely long video (27+ hours)
        allowed, msg = await check_duration_limit(admin_user, 100000)

        assert allowed is True
        assert msg == ""

    @pytest.mark.asyncio
    async def test_user_within_limit(self, regular_user):
        """Regular user with video under 3h limit passes."""
        from app.api.websocket.video_loader import check_duration_limit

        # Test with 2.5 hour video (9000 seconds)
        allowed, msg = await check_duration_limit(regular_user, 9000)

        assert allowed is True
        assert msg == ""

    @pytest.mark.asyncio
    async def test_user_exceeds_limit(self, regular_user):
        """Regular user with video over 3h limit fails."""
        from app.api.websocket.video_loader import check_duration_limit

        # Test with 4 hour video (14400 seconds)
        allowed, msg = await check_duration_limit(regular_user, 14400)

        assert allowed is False
        assert "4h 0m long" in msg
        assert "3 hours" in msg
        assert "contact support" in msg

    @pytest.mark.asyncio
    async def test_user_exactly_at_limit(self, regular_user):
        """Regular user with video exactly at 3h limit passes."""
        from app.api.websocket.video_loader import check_duration_limit

        # Test with exactly 3 hour video (10800 seconds)
        allowed, msg = await check_duration_limit(regular_user, 10800)

        assert allowed is True
        assert msg == ""

    @pytest.mark.asyncio
    async def test_user_one_second_over_limit(self, regular_user):
        """Regular user with video 1 second over limit fails."""
        from app.api.websocket.video_loader import check_duration_limit

        # Test with 3h 0m 1s video (10801 seconds)
        allowed, msg = await check_duration_limit(regular_user, 10801)

        assert allowed is False
        assert "3h 0m long" in msg
        assert "3 hours" in msg

    @pytest.mark.asyncio
    async def test_duration_formatting_minutes(self, regular_user):
        """Error message correctly formats hours and minutes."""
        from app.api.websocket.video_loader import check_duration_limit

        # Test with 3h 45m video (13500 seconds)
        allowed, msg = await check_duration_limit(regular_user, 13500)

        assert allowed is False
        assert "3h 45m long" in msg


class TestFetchVideoDuration:
    """Tests for fetch_video_duration() function."""

    @pytest.mark.asyncio
    async def test_fetch_success(self):
        """Successfully fetch duration and title from SUPADATA."""
        from app.api.websocket.video_loader import fetch_video_duration

        youtube_url = "https://youtube.com/watch?v=test123"

        # Mock TranscriptService and SUPADATA client
        mock_video = MagicMock()
        mock_video.duration = 7200  # 2 hours
        mock_video.title = "Test Video Title"

        mock_service = MagicMock()
        mock_service.client.youtube.video = MagicMock(return_value=mock_video)

        with patch("app.api.websocket.video_loader.TranscriptService", return_value=mock_service), \
             patch("app.api.websocket.video_loader.detect_youtube_url", return_value="test123"):

            duration, title = await fetch_video_duration(youtube_url)

        assert duration == 7200
        assert title == "Test Video Title"

    @pytest.mark.asyncio
    async def test_fetch_no_title(self):
        """Handle video with duration but no title."""
        from app.api.websocket.video_loader import fetch_video_duration

        youtube_url = "https://youtube.com/watch?v=test123"

        # Mock video without title
        mock_video = MagicMock()
        mock_video.duration = 3600
        del mock_video.title  # Simulate missing title attribute

        mock_service = MagicMock()
        mock_service.client.youtube.video = MagicMock(return_value=mock_video)

        with patch("app.api.websocket.video_loader.TranscriptService", return_value=mock_service), \
             patch("app.api.websocket.video_loader.detect_youtube_url", return_value="test123"):

            duration, title = await fetch_video_duration(youtube_url)

        assert duration == 3600
        assert title is None

    @pytest.mark.asyncio
    async def test_fetch_invalid_url(self):
        """Invalid YouTube URL raises ValueError."""
        from app.api.websocket.video_loader import fetch_video_duration

        with patch("app.api.websocket.video_loader.detect_youtube_url", return_value=None):
            with pytest.raises(ValueError, match="Invalid YouTube URL"):
                await fetch_video_duration("not-a-youtube-url")

    @pytest.mark.asyncio
    async def test_fetch_api_failure(self):
        """SUPADATA API failure raises exception."""
        from app.api.websocket.video_loader import fetch_video_duration

        youtube_url = "https://youtube.com/watch?v=test123"

        # Mock SUPADATA client failure
        mock_service = MagicMock()
        mock_service.client.youtube.video = MagicMock(side_effect=Exception("API Error"))

        with patch("app.api.websocket.video_loader.TranscriptService", return_value=mock_service), \
             patch("app.api.websocket.video_loader.detect_youtube_url", return_value="test123"):

            with pytest.raises(Exception, match="API Error"):
                await fetch_video_duration(youtube_url)


class TestDurationCheckIntegration:
    """Integration tests for duration check in handle_video_load_intent()."""

    @pytest.mark.asyncio
    async def test_user_video_within_duration_limit(self, regular_user, mock_db, mock_websocket):
        """User loading video under 3h passes all checks."""
        from app.api.websocket.video_loader import handle_video_load_intent

        youtube_url = "https://youtube.com/watch?v=short123"
        conversation_id = "conv-123"

        # Mock no existing transcript
        mock_transcript_repo = AsyncMock()
        mock_transcript_repo.get_by_video_id = AsyncMock(return_value=None)

        # Mock duration fetch - 2 hour video
        with patch("app.api.websocket.video_loader.TranscriptRepository", return_value=mock_transcript_repo), \
             patch("app.api.websocket.video_loader.detect_youtube_url", return_value="short123"), \
             patch("app.api.websocket.video_loader.fetch_video_duration", new_callable=AsyncMock, return_value=(7200, "Short Video")):

            await handle_video_load_intent(youtube_url, regular_user, conversation_id, mock_db, mock_websocket)

        # Should send 2 messages: status then confirmation
        assert mock_websocket.send_json.call_count == 2

        # Check second message is confirmation (not error)
        second_call = mock_websocket.send_json.call_args_list[1][0][0]
        assert second_call["type"] == "video_load_confirmation"

    @pytest.mark.asyncio
    async def test_user_video_exceeds_duration_limit(self, regular_user, mock_db, mock_websocket):
        """User loading video over 3h gets rejected."""
        from app.api.websocket.video_loader import handle_video_load_intent

        youtube_url = "https://youtube.com/watch?v=long123"
        conversation_id = "conv-123"

        # Mock no existing transcript
        mock_transcript_repo = AsyncMock()
        mock_transcript_repo.get_by_video_id = AsyncMock(return_value=None)

        # Mock duration fetch - 5 hour video
        with patch("app.api.websocket.video_loader.TranscriptRepository", return_value=mock_transcript_repo), \
             patch("app.api.websocket.video_loader.detect_youtube_url", return_value="long123"), \
             patch("app.api.websocket.video_loader.fetch_video_duration", new_callable=AsyncMock, return_value=(18000, "Long Video")):

            await handle_video_load_intent(youtube_url, regular_user, conversation_id, mock_db, mock_websocket)

        # Should send 2 messages: status then error
        assert mock_websocket.send_json.call_count == 2

        # Check second message is error
        second_call = mock_websocket.send_json.call_args_list[1][0][0]
        assert second_call["type"] == "video_load_status"
        assert second_call["status"] == "failed"
        assert second_call["error"] == "DURATION_EXCEEDED"
        assert "5h 0m long" in second_call["message"]
        assert second_call["video_title"] == "Long Video"

    @pytest.mark.asyncio
    async def test_admin_video_exceeds_user_limit(self, admin_user, mock_db, mock_websocket):
        """Admin can load video over 3h limit."""
        from app.api.websocket.video_loader import handle_video_load_intent

        youtube_url = "https://youtube.com/watch?v=long123"
        conversation_id = "conv-123"

        # Mock no existing transcript
        mock_transcript_repo = AsyncMock()
        mock_transcript_repo.get_by_video_id = AsyncMock(return_value=None)

        # Mock duration fetch - 5 hour video
        with patch("app.api.websocket.video_loader.TranscriptRepository", return_value=mock_transcript_repo), \
             patch("app.api.websocket.video_loader.detect_youtube_url", return_value="long123"), \
             patch("app.api.websocket.video_loader.fetch_video_duration", new_callable=AsyncMock, return_value=(18000, "Long Video")):

            await handle_video_load_intent(youtube_url, admin_user, conversation_id, mock_db, mock_websocket)

        # Should send 2 messages: status then confirmation (not error)
        assert mock_websocket.send_json.call_count == 2

        # Check second message is confirmation
        second_call = mock_websocket.send_json.call_args_list[1][0][0]
        assert second_call["type"] == "video_load_confirmation"

    @pytest.mark.asyncio
    async def test_duration_unavailable(self, regular_user, mock_db, mock_websocket):
        """Video with zero duration gets rejected."""
        from app.api.websocket.video_loader import handle_video_load_intent

        youtube_url = "https://youtube.com/watch?v=noduration"
        conversation_id = "conv-123"

        # Mock no existing transcript
        mock_transcript_repo = AsyncMock()
        mock_transcript_repo.get_by_video_id = AsyncMock(return_value=None)

        # Mock duration fetch - 0 duration
        with patch("app.api.websocket.video_loader.TranscriptRepository", return_value=mock_transcript_repo), \
             patch("app.api.websocket.video_loader.detect_youtube_url", return_value="noduration"), \
             patch("app.api.websocket.video_loader.fetch_video_duration", new_callable=AsyncMock, return_value=(0, "Unknown")):

            await handle_video_load_intent(youtube_url, regular_user, conversation_id, mock_db, mock_websocket)

        # Should send 2 messages: status then error
        assert mock_websocket.send_json.call_count == 2

        # Check second message is error
        second_call = mock_websocket.send_json.call_args_list[1][0][0]
        assert second_call["type"] == "video_load_status"
        assert second_call["status"] == "failed"
        assert second_call["error"] == "DURATION_UNAVAILABLE"

    @pytest.mark.asyncio
    async def test_duration_fetch_failure(self, regular_user, mock_db, mock_websocket):
        """SUPADATA API failure during duration fetch."""
        from app.api.websocket.video_loader import handle_video_load_intent

        youtube_url = "https://youtube.com/watch?v=error123"
        conversation_id = "conv-123"

        # Mock no existing transcript
        mock_transcript_repo = AsyncMock()
        mock_transcript_repo.get_by_video_id = AsyncMock(return_value=None)

        # Mock duration fetch failure
        with patch("app.api.websocket.video_loader.TranscriptRepository", return_value=mock_transcript_repo), \
             patch("app.api.websocket.video_loader.detect_youtube_url", return_value="error123"), \
             patch("app.api.websocket.video_loader.fetch_video_duration", new_callable=AsyncMock, side_effect=Exception("API Error")):

            await handle_video_load_intent(youtube_url, regular_user, conversation_id, mock_db, mock_websocket)

        # Should send 2 messages: status then error
        assert mock_websocket.send_json.call_count == 2

        # Check second message is error
        second_call = mock_websocket.send_json.call_args_list[1][0][0]
        assert second_call["type"] == "video_load_status"
        assert second_call["status"] == "failed"
        assert second_call["error"] == "DURATION_CHECK_FAILED"


class TestVideoMetadataCache:
    """Tests for video metadata caching functionality."""

    @pytest.mark.asyncio
    async def test_cache_miss_fetches_from_api(self):
        """First call to fetch_video_duration fetches from SUPADATA API."""
        from app.api.websocket.video_loader import fetch_video_duration

        youtube_url = "https://youtube.com/watch?v=test123"

        # Mock SUPADATA client
        mock_video = MagicMock()
        mock_video.duration = 7200  # 2 hours
        mock_video.title = "Test Video"

        mock_service = MagicMock()
        mock_service.client.youtube.video = MagicMock(return_value=mock_video)

        with patch("app.api.websocket.video_loader.TranscriptService", return_value=mock_service), \
             patch("app.api.websocket.video_loader.detect_youtube_url", return_value="test123"):

            duration, title = await fetch_video_duration(youtube_url)

        # Check API was called
        mock_service.client.youtube.video.assert_called_once_with(id="test123")

        # Check result
        assert duration == 7200
        assert title == "Test Video"

        # Check cache was populated
        assert "test123" in video_metadata_cache
        assert video_metadata_cache["test123"].duration == 7200
        assert video_metadata_cache["test123"].title == "Test Video"

    @pytest.mark.asyncio
    async def test_cache_hit_skips_api(self):
        """Second call to fetch_video_duration uses cached data."""
        from app.api.websocket.video_loader import fetch_video_duration

        youtube_url = "https://youtube.com/watch?v=cached123"

        # Pre-populate cache
        video_metadata_cache["cached123"] = VideoMetadata(
            video_id="cached123",
            duration=3600,
            title="Cached Video",
            fetched_at=datetime.now(timezone.utc),
        )

        # Mock SUPADATA client (should NOT be called)
        mock_service = MagicMock()
        mock_service.client.youtube.video = MagicMock()

        with patch("app.api.websocket.video_loader.TranscriptService", return_value=mock_service), \
             patch("app.api.websocket.video_loader.detect_youtube_url", return_value="cached123"):

            duration, title = await fetch_video_duration(youtube_url)

        # Check API was NOT called
        mock_service.client.youtube.video.assert_not_called()

        # Check cached result was returned
        assert duration == 3600
        assert title == "Cached Video"

    @pytest.mark.asyncio
    async def test_cache_prevents_repeated_api_calls_for_same_video(self):
        """Multiple calls for same video only hit API once."""
        from app.api.websocket.video_loader import fetch_video_duration

        youtube_url = "https://youtube.com/watch?v=repeat123"

        # Mock SUPADATA client
        mock_video = MagicMock()
        mock_video.duration = 5400
        mock_video.title = "Repeat Test"

        mock_service = MagicMock()
        mock_service.client.youtube.video = MagicMock(return_value=mock_video)

        with patch("app.api.websocket.video_loader.TranscriptService", return_value=mock_service), \
             patch("app.api.websocket.video_loader.detect_youtube_url", return_value="repeat123"):

            # First call - cache miss
            duration1, title1 = await fetch_video_duration(youtube_url)

            # Second call - cache hit
            duration2, title2 = await fetch_video_duration(youtube_url)

            # Third call - cache hit
            duration3, title3 = await fetch_video_duration(youtube_url)

        # Check API was called only ONCE
        assert mock_service.client.youtube.video.call_count == 1

        # Check all calls returned same cached data
        assert duration1 == duration2 == duration3 == 5400
        assert title1 == title2 == title3 == "Repeat Test"

    @pytest.mark.asyncio
    async def test_cache_stores_metadata_after_fetch(self):
        """Cache correctly stores all metadata fields."""
        from app.api.websocket.video_loader import fetch_video_duration

        youtube_url = "https://youtube.com/watch?v=store123"

        # Mock SUPADATA client
        mock_video = MagicMock()
        mock_video.duration = 9999
        mock_video.title = "Storage Test Video"

        mock_service = MagicMock()
        mock_service.client.youtube.video = MagicMock(return_value=mock_video)

        with patch("app.api.websocket.video_loader.TranscriptService", return_value=mock_service), \
             patch("app.api.websocket.video_loader.detect_youtube_url", return_value="store123"):

            await fetch_video_duration(youtube_url)

        # Verify cache entry
        assert "store123" in video_metadata_cache
        cached = video_metadata_cache["store123"]

        assert cached.video_id == "store123"
        assert cached.duration == 9999
        assert cached.title == "Storage Test Video"
        assert isinstance(cached.fetched_at, datetime)

    @pytest.mark.asyncio
    async def test_cache_handles_video_without_title(self):
        """Cache correctly stores None for missing title."""
        from app.api.websocket.video_loader import fetch_video_duration

        youtube_url = "https://youtube.com/watch?v=notitle123"

        # Mock video without title
        mock_video = MagicMock()
        mock_video.duration = 1234
        del mock_video.title  # Simulate missing title attribute

        mock_service = MagicMock()
        mock_service.client.youtube.video = MagicMock(return_value=mock_video)

        with patch("app.api.websocket.video_loader.TranscriptService", return_value=mock_service), \
             patch("app.api.websocket.video_loader.detect_youtube_url", return_value="notitle123"):

            duration, title = await fetch_video_duration(youtube_url)

        # Check None was returned and cached
        assert duration == 1234
        assert title is None

        assert "notitle123" in video_metadata_cache
        assert video_metadata_cache["notitle123"].title is None

    @pytest.mark.asyncio
    async def test_zero_duration_not_cached(self):
        """Zero-duration metadata should NOT be cached to allow retries."""
        from app.api.websocket.video_loader import fetch_video_duration

        youtube_url = "https://youtube.com/watch?v=zerodur123"

        # Mock SUPADATA returning zero duration
        mock_video = MagicMock()
        mock_video.duration = 0
        mock_video.title = "Zero Duration Video"

        mock_service = MagicMock()
        mock_service.client.youtube.video = MagicMock(return_value=mock_video)

        with patch("app.api.websocket.video_loader.TranscriptService", return_value=mock_service), \
             patch("app.api.websocket.video_loader.detect_youtube_url", return_value="zerodur123"):

            duration, title = await fetch_video_duration(youtube_url)

        # Check zero duration was returned
        assert duration == 0
        assert title == "Zero Duration Video"

        # Check it was NOT cached
        assert "zerodur123" not in video_metadata_cache

    @pytest.mark.asyncio
    async def test_retry_after_zero_duration(self):
        """Second request after zero-duration should retry API (not cached)."""
        from app.api.websocket.video_loader import fetch_video_duration

        youtube_url = "https://youtube.com/watch?v=retry123"

        # First call: API returns zero duration
        mock_video_zero = MagicMock()
        mock_video_zero.duration = 0
        mock_video_zero.title = "Temp Unavailable"

        mock_service_1 = MagicMock()
        mock_service_1.client.youtube.video = MagicMock(return_value=mock_video_zero)

        with patch("app.api.websocket.video_loader.TranscriptService", return_value=mock_service_1), \
             patch("app.api.websocket.video_loader.detect_youtube_url", return_value="retry123"):

            duration_1, title_1 = await fetch_video_duration(youtube_url)

        # Verify first call returned zero and NOT cached
        assert duration_1 == 0
        assert "retry123" not in video_metadata_cache

        # Second call: API now returns valid duration
        mock_video_valid = MagicMock()
        mock_video_valid.duration = 3600
        mock_video_valid.title = "Now Available"

        mock_service_2 = MagicMock()
        mock_service_2.client.youtube.video = MagicMock(return_value=mock_video_valid)

        with patch("app.api.websocket.video_loader.TranscriptService", return_value=mock_service_2), \
             patch("app.api.websocket.video_loader.detect_youtube_url", return_value="retry123"):

            duration_2, title_2 = await fetch_video_duration(youtube_url)

        # Verify second call fetched from API (not cache) and got valid data
        assert duration_2 == 3600
        assert title_2 == "Now Available"

        # Verify API was called (not using cache)
        mock_service_2.client.youtube.video.assert_called_once_with(id="retry123")

        # Now it should be cached
        assert "retry123" in video_metadata_cache
        assert video_metadata_cache["retry123"].duration == 3600
