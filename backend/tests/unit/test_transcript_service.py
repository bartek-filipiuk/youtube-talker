"""Unit tests for TranscriptService."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import httpx
from tenacity import RetryError

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
        service = TranscriptService()

        # Create mock response
        mock_response_data = {
            "transcript": "This is the transcript text.",
            "metadata": {
                "title": "Test Video",
                "duration": 120,
                "language": "en",
            },
        }

        # Create mock response object
        mock_response = MagicMock()
        mock_response.json.return_value = mock_response_data
        mock_response.raise_for_status = MagicMock()

        # Create mock client that implements async context manager
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch("httpx.AsyncClient", return_value=mock_client):
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
        """Test fetch transcript when API returns no metadata."""
        service = TranscriptService()

        mock_response_data = {
            "transcript": "Transcript without metadata.",
        }

        # Create mock response object
        mock_response = MagicMock()
        mock_response.json.return_value = mock_response_data
        mock_response.raise_for_status = MagicMock()

        # Create mock client that implements async context manager
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await service.fetch_transcript(
                "https://youtube.com/watch?v=TEST123"
            )

        assert result["youtube_video_id"] == "TEST123"
        assert result["transcript_text"] == "Transcript without metadata."
        assert result["metadata"] == {}

    @pytest.mark.asyncio
    async def test_fetch_transcript_retry_on_timeout(self):
        """Test retry logic on timeout."""
        service = TranscriptService()

        # Create mock response for successful retry
        mock_response_success = MagicMock()
        mock_response_success.json.return_value = {
            "transcript": "Success after retry",
            "metadata": {},
        }
        mock_response_success.raise_for_status = MagicMock()

        # Create mock client that implements async context manager
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None

        # Side effect: first call raises TimeoutException, second returns success
        mock_client.post = AsyncMock(side_effect=[
            httpx.TimeoutException("Request timeout"),
            mock_response_success,
        ])

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await service.fetch_transcript(
                "https://youtube.com/watch?v=RETRY"
            )

        assert result["transcript_text"] == "Success after retry"
        # Verify retry happened (2 calls)
        assert mock_client.post.call_count == 2

    @pytest.mark.asyncio
    async def test_fetch_transcript_retry_on_http_error(self):
        """Test retry logic on HTTP error (5xx)."""
        service = TranscriptService()

        # Create mock response for successful retry
        mock_response_success = MagicMock()
        mock_response_success.json.return_value = {
            "transcript": "Success after retry",
            "metadata": {},
        }
        mock_response_success.raise_for_status = MagicMock()

        # Create mock for HTTPStatusError
        mock_request = MagicMock()
        mock_error_response = MagicMock()
        mock_error_response.status_code = 500

        # Create mock client that implements async context manager
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None

        # Side effect: first call raises HTTPStatusError, second returns success
        mock_client.post = AsyncMock(side_effect=[
            httpx.HTTPStatusError(
                "500 Server Error",
                request=mock_request,
                response=mock_error_response,
            ),
            mock_response_success,
        ])

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await service.fetch_transcript(
                "https://youtube.com/watch?v=RETRY"
            )

        assert result["transcript_text"] == "Success after retry"
        assert mock_client.post.call_count == 2

    @pytest.mark.asyncio
    async def test_fetch_transcript_api_error_after_retries(self):
        """Test handling of API errors after retries exhausted."""
        service = TranscriptService()

        mock_request = MagicMock()
        mock_error_response = MagicMock()
        mock_error_response.status_code = 500

        # Create mock client that implements async context manager
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None

        # All 3 attempts fail
        mock_client.post = AsyncMock(side_effect=httpx.HTTPStatusError(
            "500 Server Error",
            request=mock_request,
            response=mock_error_response,
        ))

        with patch("httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(RetryError):
                await service.fetch_transcript("https://youtube.com/watch?v=ERROR")

        # Should have tried 3 times (initial + 2 retries)
        assert mock_client.post.call_count == 3

    @pytest.mark.asyncio
    async def test_fetch_transcript_invalid_url_format(self):
        """Test that invalid URL raises ValueError before making API call."""
        service = TranscriptService()

        # Should raise ValueError without making any API calls
        with pytest.raises(ValueError, match="Invalid YouTube URL"):
            await service.fetch_transcript("https://notayoutubeurl.com/video")
