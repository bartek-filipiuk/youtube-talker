"""
Global exception handlers for FastAPI.

These handlers convert custom exceptions into appropriate HTTP responses
with consistent formatting including request IDs for tracing.
"""

from loguru import logger
from fastapi import Request
from fastapi.responses import JSONResponse

from app.core.errors import (
    AuthenticationError,
    ConversationNotFoundError,
    ConversationAccessDeniedError,
    RateLimitExceededError,
    InvalidInputError,
    TranscriptNotFoundError,
    TranscriptAlreadyExistsError,
    ExternalAPIError,
)


def create_error_response(
    status_code: int,
    detail: str,
    error_code: str,
    request_id: str | None = None
) -> JSONResponse:
    """
    Create standardized error response with request tracing.

    Args:
        status_code: HTTP status code
        detail: Human-readable error message
        error_code: Machine-readable error code
        request_id: Request ID for tracing (optional)

    Returns:
        JSONResponse with consistent error format
    """
    content = {
        "detail": detail,
        "error_code": error_code,
    }

    if request_id:
        content["request_id"] = request_id

    return JSONResponse(status_code=status_code, content=content)


async def authentication_error_handler(
    request: Request, exc: AuthenticationError
) -> JSONResponse:
    """Handle AuthenticationError → 401 response."""
    logger.warning(f"Authentication failed: {request.url.path} - {str(exc)}")
    return create_error_response(
        status_code=401,
        detail=str(exc) or "Authentication failed",
        error_code="AUTHENTICATION_FAILED",
        request_id=request.headers.get("X-Request-ID")
    )


async def conversation_not_found_handler(
    request: Request, exc: ConversationNotFoundError
) -> JSONResponse:
    """Handle ConversationNotFoundError → 404 response."""
    logger.warning(f"Conversation not found: {request.url.path}")
    return create_error_response(
        status_code=404,
        detail="Conversation not found",
        error_code="CONVERSATION_NOT_FOUND",
        request_id=request.headers.get("X-Request-ID")
    )


async def conversation_access_denied_handler(
    request: Request, exc: ConversationAccessDeniedError
) -> JSONResponse:
    """Handle ConversationAccessDeniedError → 403 response."""
    logger.warning(f"Access denied to conversation: {request.url.path}")
    return create_error_response(
        status_code=403,
        detail="Access denied to this conversation",
        error_code="CONVERSATION_ACCESS_DENIED",
        request_id=request.headers.get("X-Request-ID")
    )


async def rate_limit_exceeded_handler(
    request: Request, exc: RateLimitExceededError
) -> JSONResponse:
    """Handle RateLimitExceededError → 429 response."""
    logger.warning(f"Rate limit exceeded: {request.url.path}")
    return create_error_response(
        status_code=429,
        detail="Rate limit exceeded. Please try again later.",
        error_code="RATE_LIMIT_EXCEEDED",
        request_id=request.headers.get("X-Request-ID")
    )


async def invalid_input_handler(
    request: Request, exc: InvalidInputError
) -> JSONResponse:
    """Handle InvalidInputError → 400 response."""
    logger.warning(f"Invalid input: {request.url.path} - {str(exc)}")
    return create_error_response(
        status_code=400,
        detail=str(exc) or "Invalid input",
        error_code="INVALID_INPUT",
        request_id=request.headers.get("X-Request-ID")
    )


async def transcript_not_found_handler(
    request: Request, exc: TranscriptNotFoundError
) -> JSONResponse:
    """Handle TranscriptNotFoundError → 404 response."""
    logger.warning(f"Transcript not found: {request.url.path}")
    return create_error_response(
        status_code=404,
        detail="Transcript not found",
        error_code="TRANSCRIPT_NOT_FOUND",
        request_id=request.headers.get("X-Request-ID")
    )


async def transcript_already_exists_handler(
    request: Request, exc: TranscriptAlreadyExistsError
) -> JSONResponse:
    """Handle TranscriptAlreadyExistsError → 409 response."""
    logger.warning(f"Transcript already exists: {request.url.path}")
    return create_error_response(
        status_code=409,
        detail="Transcript already exists for this YouTube URL",
        error_code="TRANSCRIPT_ALREADY_EXISTS",
        request_id=request.headers.get("X-Request-ID")
    )


async def external_api_error_handler(
    request: Request, exc: ExternalAPIError
) -> JSONResponse:
    """Handle ExternalAPIError → 503 response."""
    logger.exception(f"External API error: {request.url.path} - {str(exc)}")
    return create_error_response(
        status_code=503,
        detail="External service temporarily unavailable. Please try again later.",
        error_code="EXTERNAL_API_ERROR",
        request_id=request.headers.get("X-Request-ID")
    )


async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Handle all unhandled exceptions → 500 response.

    This is a catch-all handler for any exceptions not caught by specific handlers.
    It logs the full traceback and returns a generic error message to avoid
    leaking internal implementation details.
    """
    logger.exception(
        f"Unhandled exception: {request.method} {request.url.path} - {type(exc).__name__}: {str(exc)}"
    )
    return create_error_response(
        status_code=500,
        detail="An internal error occurred. Please try again later.",
        error_code="INTERNAL_SERVER_ERROR",
        request_id=request.headers.get("X-Request-ID")
    )
