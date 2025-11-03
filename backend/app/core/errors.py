"""
Custom exception classes for better error handling.

These exceptions are used throughout the application for consistent
error handling and response formatting.
"""


class AuthenticationError(Exception):
    """Raised when authentication fails (401)."""
    pass


class ConversationNotFoundError(Exception):
    """Raised when conversation doesn't exist in database."""
    pass


class ConversationAccessDeniedError(Exception):
    """Raised when user doesn't own the requested conversation."""
    pass


class RateLimitExceededError(Exception):
    """Raised when rate limit is exceeded for user actions."""
    pass


class InvalidInputError(Exception):
    """Raised when input validation fails."""
    pass


class TranscriptNotFoundError(Exception):
    """Raised when transcript doesn't exist in database."""
    pass


class TranscriptAlreadyExistsError(Exception):
    """Raised when attempting to ingest duplicate YouTube URL."""
    pass


class ExternalAPIError(Exception):
    """Raised when external API call fails (LLM, embeddings, YouTube, etc.)."""
    pass


class ChannelAlreadyExistsError(Exception):
    """Raised when attempting to create a channel with duplicate name."""
    pass


class ChannelNotFoundError(Exception):
    """Raised when channel doesn't exist in database."""
    pass


class VideoAlreadyInChannelError(Exception):
    """Raised when attempting to add a video that's already in the channel."""
    pass


class VideoNotInChannelError(Exception):
    """Raised when attempting to remove a video that's not in the channel."""
    pass
