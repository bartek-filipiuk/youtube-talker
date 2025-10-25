"""
Global exception handlers for FastAPI.

These handlers convert custom exceptions into appropriate HTTP responses
with consistent formatting.
"""

from loguru import logger
from fastapi import Request
from fastapi.responses import JSONResponse

from app.core.errors import (
    ConversationNotFoundError,
    ConversationAccessDeniedError,
    RateLimitExceededError,
    InvalidInputError,
    TranscriptNotFoundError,
    TranscriptAlreadyExistsError,
    ExternalAPIError,
)



async def conversation_not_found_handler(
    request: Request, exc: ConversationNotFoundError
) -> JSONResponse:
    """Handle ConversationNotFoundError → 404 response."""
    logger.warning(f"Conversation not found: {request.url.path}")
    return JSONResponse(
        status_code=404,
        content={"detail": "Conversation not found"}
    )


async def conversation_access_denied_handler(
    request: Request, exc: ConversationAccessDeniedError
) -> JSONResponse:
    """Handle ConversationAccessDeniedError → 403 response."""
    logger.warning(f"Access denied to conversation: {request.url.path}")
    return JSONResponse(
        status_code=403,
        content={"detail": "Access denied to this conversation"}
    )


async def rate_limit_exceeded_handler(
    request: Request, exc: RateLimitExceededError
) -> JSONResponse:
    """Handle RateLimitExceededError → 429 response."""
    logger.warning(f"Rate limit exceeded: {request.url.path}")
    return JSONResponse(
        status_code=429,
        content={"detail": "Rate limit exceeded. Please try again later."}
    )


async def invalid_input_handler(
    request: Request, exc: InvalidInputError
) -> JSONResponse:
    """Handle InvalidInputError → 400 response."""
    logger.warning(f"Invalid input: {request.url.path} - {str(exc)}")
    return JSONResponse(
        status_code=400,
        content={"detail": str(exc) or "Invalid input"}
    )


async def transcript_not_found_handler(
    request: Request, exc: TranscriptNotFoundError
) -> JSONResponse:
    """Handle TranscriptNotFoundError → 404 response."""
    logger.warning(f"Transcript not found: {request.url.path}")
    return JSONResponse(
        status_code=404,
        content={"detail": "Transcript not found"}
    )


async def transcript_already_exists_handler(
    request: Request, exc: TranscriptAlreadyExistsError
) -> JSONResponse:
    """Handle TranscriptAlreadyExistsError → 409 response."""
    logger.warning(f"Transcript already exists: {request.url.path}")
    return JSONResponse(
        status_code=409,
        content={"detail": "Transcript already exists for this YouTube URL"}
    )


async def external_api_error_handler(
    request: Request, exc: ExternalAPIError
) -> JSONResponse:
    """Handle ExternalAPIError → 503 response."""
    logger.error(f"External API error: {request.url.path} - {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=503,
        content={"detail": "External service temporarily unavailable. Please try again later."}
    )
