"""
YoutubeTalker API - Main Application Entry Point

FastAPI application for AI-powered YouTube video Q&A and content generation.
"""

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.config import settings
from app.core.middleware import setup_middleware
from app.api.routes import auth, transcripts, health, conversations
from app.api.websocket.chat_handler import websocket_endpoint

# Import custom exceptions and handlers
from app.core.errors import (
    ConversationNotFoundError,
    ConversationAccessDeniedError,
    RateLimitExceededError as CustomRateLimitExceededError,
    InvalidInputError,
    TranscriptNotFoundError,
    TranscriptAlreadyExistsError,
    ExternalAPIError,
)
from app.core.exception_handlers import (
    conversation_not_found_handler,
    conversation_access_denied_handler,
    rate_limit_exceeded_handler,
    invalid_input_handler,
    transcript_not_found_handler,
    transcript_already_exists_handler,
    external_api_error_handler,
)

# Create FastAPI application instance
app = FastAPI(
    title="YoutubeTalker API",
    description="AI-powered YouTube video Q&A and content generation using RAG",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Configure rate limiter
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Setup middleware (CORS, logging, exception handling)
setup_middleware(app)

# Register custom exception handlers
app.add_exception_handler(ConversationNotFoundError, conversation_not_found_handler)
app.add_exception_handler(ConversationAccessDeniedError, conversation_access_denied_handler)
app.add_exception_handler(CustomRateLimitExceededError, rate_limit_exceeded_handler)
app.add_exception_handler(InvalidInputError, invalid_input_handler)
app.add_exception_handler(TranscriptNotFoundError, transcript_not_found_handler)
app.add_exception_handler(TranscriptAlreadyExistsError, transcript_already_exists_handler)
app.add_exception_handler(ExternalAPIError, external_api_error_handler)

# Include routers
app.include_router(auth.router)
app.include_router(transcripts.router)
app.include_router(health.router)
app.include_router(conversations.router)

# WebSocket endpoint
app.websocket("/ws/chat")(websocket_endpoint)


@app.get("/", tags=["root"])
async def root() -> dict:
    """
    Root endpoint - API health check.

    Returns:
        dict: Status message and API information
    """
    return {
        "status": "ok",
        "message": "YoutubeTalker API is running",
        "version": "0.1.0",
        "docs": "/docs",
    }


@app.get("/health", tags=["health"])
async def health_check() -> dict:
    """
    Health check endpoint.

    Returns:
        dict: Service health status
    """
    return {
        "status": "healthy",
        "service": "youtube-talker-api",
        "environment": settings.ENV,
    }


# Application startup event
@app.on_event("startup")
async def startup_event() -> None:
    """Execute tasks on application startup."""
    print("🚀 YoutubeTalker API starting...")
    print(f"📝 Environment: {settings.ENV}")
    print(f"🔍 Debug mode: {settings.DEBUG}")
    print(f"📚 API docs: http://localhost:8000/docs")


# Application shutdown event
@app.on_event("shutdown")
async def shutdown_event() -> None:
    """Execute cleanup tasks on application shutdown."""
    print("👋 YoutubeTalker API shutting down...")
