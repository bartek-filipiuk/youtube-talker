"""Unit tests for TranscriptService."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import httpx
from tenacity import RetryError
from supadata import SupadataError

from app.services.transcript_service import TranscriptService


class TestTranscriptService:
    """Unit tests for TranscriptService."""

    def test_extract_video_id_youtube_com(self):
        """Extract video ID from youtube.com URL."""
        service = TranscriptService()
        url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        assert service._extract_video_id(url) == "dQw4w9WgXcQ"

    def test_extract_video_id_youtube_com_without_www(self):
        """Extract video ID from youtube.com URL without www."""
        service = TranscriptService()
        url = "https://youtube.com/watch?v=dQw4w9WgXcQ"
        assert service._extract_video_id(url) == "dQw4w9WgXcQ"

    def test_extract_video_id_youtu_be(self):
        """Extract video ID from youtu.be URL."""
        service = TranscriptService()
        url = "https://youtu.be/dQw4w9WgXcQ"
        assert service._extract_video_id(url) == "dQw4w9WgXcQ"

    def test_extract_video_id_with_additional_params(self):
        """Extract video ID from URL with additional query parameters."""
        service = TranscriptService()
        url = "https://youtube.com/watch?v=dQw4w9WgXcQ&feature=share"
        assert service._extract_video_id(url) == "dQw4w9WgXcQ"

    def test_extract_video_id_invalid_url(self):
        """Raise ValueError for invalid URL."""
        service = TranscriptService()
        with pytest.raises(ValueError, match="Invalid YouTube URL"):
            service._extract_video_id("https://vimeo.com/123456")

    def test_extract_video_id_empty_url(self):
        """Raise ValueError for empty URL."""
        service = TranscriptService()
        with pytest.raises(ValueError, match="Invalid YouTube URL"):
            service._extract_video_id("")

    @pytest.mark.asyncio
    async def test_fetch_transcript_success(self):
        """Test successful transcript fetch with mocked API."""
        # Mock video metadata response
        mock_video = MagicMock()
        mock_video.id = "TEST123"
        mock_video.title = "Test Video"
        mock_video.description = "Test description"
        mock_video.duration = 120
        mock_video.channel = {"id": "UC123", "name": "Test Channel"}
        mock_video.tags = ["test", "video"]
        mock_video.thumbnail = "https://example.com/thumb.jpg"
        mock_video.upload_date = "2024-01-01"
        mock_video.view_count = 1000
        mock_video.like_count = 50

        # Mock transcript response
        mock_transcript = MagicMock()
        mock_transcript.content = "This is the transcript text."
        mock_transcript.lang = "en"
        mock_transcript.availableLangs = ["en"]

        # Mock the SUPADATA YouTube client
        mock_youtube = MagicMock()
        mock_youtube.video = MagicMock(return_value=mock_video)
        mock_youtube.transcript = MagicMock(return_value=mock_transcript)

        # Patch the Supadata client to return our mock
        with patch("app.services.transcript_service.Supadata") as mock_supadata_class:
            mock_supadata_class.return_value.youtube = mock_youtube
            service = TranscriptService()

            result = await service.fetch_transcript(
                "https://youtube.com/watch?v=TEST123"
            )

        assert result["youtube_video_id"] == "TEST123"
        assert result["transcript_text"] == "This is the transcript text."
        assert result["metadata"]["title"] == "Test Video"
        assert result["metadata"]["duration"] == 120
        assert result["metadata"]["language"] == "en"

    @pytest.mark.asyncio
    async def test_fetch_transcript_no_metadata(self):
        """Test fetch transcript when API returns minimal metadata."""
        # Mock video with minimal metadata
        mock_video = MagicMock()
        mock_video.id = "TEST123"
        mock_video.title = ""
        mock_video.description = ""
        mock_video.duration = 0
        mock_video.channel = {"id": "", "name": "Unknown"}
        mock_video.tags = []
        mock_video.thumbnail = ""
        mock_video.upload_date = ""
        mock_video.view_count = 0
        mock_video.like_count = 0
        mock_video.language = ""
        mock_video.available_languages = []

        # Mock transcript response
        mock_transcript = MagicMock()
        mock_transcript.content = "Transcript without metadata."

        # Mock the SUPADATA YouTube client
        mock_youtube = MagicMock()
        mock_youtube.video = MagicMock(return_value=mock_video)
        mock_youtube.transcript = MagicMock(return_value=mock_transcript)

        with patch("app.services.transcript_service.Supadata") as mock_supadata_class:
            mock_supadata_class.return_value.youtube = mock_youtube
            service = TranscriptService()

            result = await service.fetch_transcript(
                "https://youtube.com/watch?v=TEST123"
            )

        assert result["youtube_video_id"] == "TEST123"
        assert result["transcript_text"] == "Transcript without metadata."
        # Metadata will have empty values, not be empty dict
        assert result["metadata"]["title"] == ""
        assert result["metadata"]["channel_name"] == "Unknown"

    @pytest.mark.asyncio
    async def test_fetch_transcript_retry_on_timeout(self):
        """Test retry logic on SupadataError."""
        # Mock successful video response (used on both attempts)
        mock_video = MagicMock()
        mock_video.id = "RETRY"
        mock_video.title = "Success after retry"
        mock_video.description = ""
        mock_video.duration = 100
        mock_video.channel = {"id": "UC123", "name": "Test"}
        mock_video.tags = []
        mock_video.thumbnail = ""
        mock_video.upload_date = ""
        mock_video.view_count = 0
        mock_video.like_count = 0
        mock_video.language = "en"
        mock_video.available_languages = ["en"]

        # Mock successful transcript response
        mock_transcript = MagicMock()
        mock_transcript.content = "Success after retry"

        # Mock the SUPADATA YouTube client
        mock_youtube = MagicMock()
        mock_youtube.video = MagicMock(return_value=mock_video)
        # Mock transcript to fail first, then succeed
        mock_youtube.transcript = MagicMock(
            side_effect=[
                SupadataError("timeout", "Timeout error", "Request timed out"),
                mock_transcript,
            ]
        )

        with patch("app.services.transcript_service.Supadata") as mock_supadata_class:
            mock_supadata_class.return_value.youtube = mock_youtube
            service = TranscriptService()

            result = await service.fetch_transcript(
                "https://youtube.com/watch?v=RETRY"
            )

        assert result["transcript_text"] == "Success after retry"
        # Verify retry happened (2 calls to transcript)
        assert mock_youtube.transcript.call_count == 2

    @pytest.mark.asyncio
    async def test_fetch_transcript_retry_on_http_error(self):
        """Test retry logic on HTTP error via SupadataError."""
        # Mock successful video response
        mock_video = MagicMock()
        mock_video.id = "RETRY"
        mock_video.title = "Success after retry"
        mock_video.description = ""
        mock_video.duration = 100
        mock_video.channel = {"id": "UC123", "name": "Test"}
        mock_video.tags = []
        mock_video.thumbnail = ""
        mock_video.upload_date = ""
        mock_video.view_count = 0
        mock_video.like_count = 0
        mock_video.language = "en"
        mock_video.available_languages = ["en"]

        # Mock successful transcript response
        mock_transcript = MagicMock()
        mock_transcript.content = "Success after retry"

        # Mock the SUPADATA YouTube client
        mock_youtube = MagicMock()
        mock_youtube.video = MagicMock(return_value=mock_video)
        # Mock transcript to fail first with HTTP error, then succeed
        mock_youtube.transcript = MagicMock(
            side_effect=[
                SupadataError("http-error", "500 Server Error", "Internal server error"),
                mock_transcript,
            ]
        )

        with patch("app.services.transcript_service.Supadata") as mock_supadata_class:
            mock_supadata_class.return_value.youtube = mock_youtube
            service = TranscriptService()

            result = await service.fetch_transcript(
                "https://youtube.com/watch?v=RETRY"
            )

        assert result["transcript_text"] == "Success after retry"
        assert mock_youtube.transcript.call_count == 2

    @pytest.mark.asyncio
    async def test_fetch_transcript_api_error_after_retries(self):
        """Test handling of API errors after retries exhausted."""
        # Mock video to succeed
        mock_video = MagicMock()
        mock_video.id = "ERROR"

        # Mock the SUPADATA YouTube client
        mock_youtube = MagicMock()
        mock_youtube.video = MagicMock(return_value=mock_video)
        # Mock transcript to fail all 3 attempts
        mock_youtube.transcript = MagicMock(
            side_effect=SupadataError("http-error", "500 Server Error", "Persistent server error")
        )

        with patch("app.services.transcript_service.Supadata") as mock_supadata_class:
            mock_supadata_class.return_value.youtube = mock_youtube
            service = TranscriptService()

            with pytest.raises(RetryError):
                await service.fetch_transcript("https://youtube.com/watch?v=ERROR")

        # Should have tried 3 times (initial + 2 retries)
        assert mock_youtube.transcript.call_count == 3

    @pytest.mark.asyncio
    async def test_fetch_transcript_invalid_url_format(self):
        """Test that invalid URL raises ValueError before making API call."""
        service = TranscriptService()

        # Should raise ValueError without making any API calls
        with pytest.raises(ValueError, match="Invalid YouTube URL"):
            await service.fetch_transcript("https://notayoutubeurl.com/video")
