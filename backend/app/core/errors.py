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
