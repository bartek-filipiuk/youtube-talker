"""
Unit Tests for URL Detector

Tests YouTube URL detection and video ID extraction.
"""

import pytest

from app.utils.url_detector import detect_youtube_url, is_youtube_url


class TestDetectYoutubeUrl:
    """Tests for detect_youtube_url function."""

    def test_standard_youtube_url(self):
        """Test standard YouTube watch URL format."""
        url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        assert detect_youtube_url(url) == "dQw4w9WgXcQ"

    def test_short_youtube_url(self):
        """Test shortened youtu.be URL format."""
        url = "https://youtu.be/dQw4w9WgXcQ"
        assert detect_youtube_url(url) == "dQw4w9WgXcQ"

    def test_embed_youtube_url(self):
        """Test YouTube embed URL format."""
        url = "https://www.youtube.com/embed/dQw4w9WgXcQ"
        assert detect_youtube_url(url) == "dQw4w9WgXcQ"

    def test_v_youtube_url(self):
        """Test YouTube /v/ URL format."""
        url = "https://www.youtube.com/v/dQw4w9WgXcQ"
        assert detect_youtube_url(url) == "dQw4w9WgXcQ"

    def test_url_without_protocol(self):
        """Test URL without https:// protocol."""
        url = "www.youtube.com/watch?v=dQw4w9WgXcQ"
        assert detect_youtube_url(url) == "dQw4w9WgXcQ"

    def test_url_without_www(self):
        """Test URL without www prefix."""
        url = "https://youtube.com/watch?v=dQw4w9WgXcQ"
        assert detect_youtube_url(url) == "dQw4w9WgXcQ"

    def test_url_in_sentence(self):
        """Test URL detection within a sentence."""
        text = "Check out this video https://www.youtube.com/watch?v=dQw4w9WgXcQ it's great!"
        assert detect_youtube_url(text) == "dQw4w9WgXcQ"

    def test_url_with_additional_params(self):
        """Test URL with query parameters after video ID."""
        url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=10s&list=PLtest"
        assert detect_youtube_url(url) == "dQw4w9WgXcQ"

    def test_url_with_params_before_video_id(self):
        """Test URL with query parameters before video ID."""
        url = "https://www.youtube.com/watch?feature=share&v=dQw4w9WgXcQ"
        assert detect_youtube_url(url) == "dQw4w9WgXcQ"

    def test_video_id_with_underscore(self):
        """Test video ID containing underscore."""
        url = "https://www.youtube.com/watch?v=_dQw4w9WgXc"
        assert detect_youtube_url(url) == "_dQw4w9WgXc"

    def test_video_id_with_dash(self):
        """Test video ID containing dash."""
        url = "https://www.youtube.com/watch?v=-Qw4w9WgXcQ"
        assert detect_youtube_url(url) == "-Qw4w9WgXcQ"

    def test_no_youtube_url(self):
        """Test text without YouTube URL."""
        text = "This is just a normal message with no video"
        assert detect_youtube_url(text) is None

    def test_invalid_youtube_url(self):
        """Test invalid YouTube URL format."""
        url = "https://www.youtube.com/channel/UCtest"
        assert detect_youtube_url(url) is None

    def test_wrong_video_id_length(self):
        """Test YouTube URL with incorrect video ID length."""
        url = "https://www.youtube.com/watch?v=short"
        assert detect_youtube_url(url) is None

    def test_empty_string(self):
        """Test empty string input."""
        assert detect_youtube_url("") is None

    def test_none_input(self):
        """Test None input."""
        assert detect_youtube_url(None) is None

    def test_non_string_input(self):
        """Test non-string input."""
        assert detect_youtube_url(12345) is None

    def test_multiple_urls_returns_first(self):
        """Test that multiple URLs returns the first match."""
        text = "First: https://youtu.be/abc12345678 Second: https://youtu.be/xyz98765432"
        assert detect_youtube_url(text) == "abc12345678"

    def test_mixed_case_domain(self):
        """Test mixed case YouTube domain."""
        url = "https://www.YouTube.com/watch?v=dQw4w9WgXcQ"
        # URL should not match due to case sensitivity in domain
        assert detect_youtube_url(url) is None

    def test_mobile_youtube_url(self):
        """Test mobile YouTube URL (m.youtube.com)."""
        url = "https://m.youtube.com/watch?v=dQw4w9WgXcQ"
        # Mobile URLs are supported
        assert detect_youtube_url(url) == "dQw4w9WgXcQ"


class TestIsYoutubeUrl:
    """Tests for is_youtube_url function."""

    def test_valid_url_returns_true(self):
        """Test valid YouTube URL returns True."""
        url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        assert is_youtube_url(url) is True

    def test_invalid_url_returns_false(self):
        """Test invalid URL returns False."""
        text = "No video here"
        assert is_youtube_url(text) is False

    def test_empty_string_returns_false(self):
        """Test empty string returns False."""
        assert is_youtube_url("") is False

    def test_short_url_returns_true(self):
        """Test shortened youtu.be URL returns True."""
        url = "https://youtu.be/dQw4w9WgXcQ"
        assert is_youtube_url(url) is True

    def test_url_in_sentence_returns_true(self):
        """Test URL within sentence returns True."""
        text = "Check this out: https://youtu.be/dQw4w9WgXcQ"
        assert is_youtube_url(text) is True
