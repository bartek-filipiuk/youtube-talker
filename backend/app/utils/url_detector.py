"""
URL Detection Utilities

Detect and extract YouTube video IDs from various URL formats.
"""

import re
from typing import Optional

# YouTube URL patterns (video ID is always 11 characters)
YOUTUBE_PATTERNS = [
    # watch?v=VIDEO_ID (handles v= anywhere in query string)
    r"(?:https?://)?(?:www\.|m\.)?youtube\.com/watch\?(?:.*&)?v=([a-zA-Z0-9_-]{11})",
    # Short URLs: youtu.be/VIDEO_ID
    r"(?:https?://)?(?:www\.)?youtu\.be/([a-zA-Z0-9_-]{11})",
    # Embed URLs: youtube.com/embed/VIDEO_ID
    r"(?:https?://)?(?:www\.|m\.)?youtube\.com/embed/([a-zA-Z0-9_-]{11})",
    # Old-style: youtube.com/v/VIDEO_ID
    r"(?:https?://)?(?:www\.|m\.)?youtube\.com/v/([a-zA-Z0-9_-]{11})",
]


def detect_youtube_url(text: str) -> Optional[str]:
    """
    Detect YouTube URL and extract video ID.

    Supports multiple YouTube URL formats:
    - https://www.youtube.com/watch?v=VIDEO_ID
    - https://youtu.be/VIDEO_ID
    - https://www.youtube.com/embed/VIDEO_ID
    - https://www.youtube.com/v/VIDEO_ID

    Args:
        text: Text that may contain a YouTube URL

    Returns:
        Video ID (11 characters) if found, None otherwise

    Examples:
        >>> detect_youtube_url("Check out https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        'dQw4w9WgXcQ'

        >>> detect_youtube_url("https://youtu.be/dQw4w9WgXcQ")
        'dQw4w9WgXcQ'

        >>> detect_youtube_url("No video here")
        None
    """
    if not text or not isinstance(text, str):
        return None

    for pattern in YOUTUBE_PATTERNS:
        match = re.search(pattern, text)
        if match:
            return match.group(1)

    return None


def is_youtube_url(text: str) -> bool:
    """
    Check if text contains a YouTube URL.

    Args:
        text: Text to check

    Returns:
        True if YouTube URL detected, False otherwise

    Examples:
        >>> is_youtube_url("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        True

        >>> is_youtube_url("No video here")
        False
    """
    return detect_youtube_url(text) is not None
