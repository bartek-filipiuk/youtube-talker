"""
YoutubeTalker API - Main Application Entry Point

FastAPI application for AI-powered YouTube video Q&A and content generation.
"""

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.config import settings

# Import logging configuration to initialize loguru
# This must be imported early to ensure all subsequent imports use the configured logger
import app.core.logging  # noqa: F401
from loguru import logger

from app.core.middleware import setup_middleware
from app.api.routes import auth, transcripts, health, conversations, channels, channel_conversations
from app.api.routes.admin import channels_router, settings_router, stats_router, users_router
from app.api.websocket.chat_handler import websocket_endpoint

# Import custom exceptions and handlers
from app.core.errors import (
    AuthenticationError,
    ConversationNotFoundError,
    ConversationAccessDeniedError,
    RateLimitExceededError as CustomRateLimitExceededError,
    InvalidInputError,
    TranscriptNotFoundError,
    TranscriptAlreadyExistsError,
    ExternalAPIError,
    ChannelAlreadyExistsError,
    ChannelNotFoundError,
    VideoAlreadyInChannelError,
    VideoNotInChannelError,
)
from app.core.exception_handlers import (
    authentication_error_handler,
    conversation_not_found_handler,
    conversation_access_denied_handler,
    rate_limit_exceeded_handler,
    invalid_input_handler,
    transcript_not_found_handler,
    transcript_already_exists_handler,
    external_api_error_handler,
    http_exception_handler,
    global_exception_handler,
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
# Use custom handler for consistent error format with request_id
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)

# Setup middleware (CORS, logging, exception handling)
setup_middleware(app)

# Register custom exception handlers
app.add_exception_handler(AuthenticationError, authentication_error_handler)
app.add_exception_handler(ConversationNotFoundError, conversation_not_found_handler)
app.add_exception_handler(ConversationAccessDeniedError, conversation_access_denied_handler)
app.add_exception_handler(CustomRateLimitExceededError, rate_limit_exceeded_handler)
app.add_exception_handler(InvalidInputError, invalid_input_handler)
app.add_exception_handler(TranscriptNotFoundError, transcript_not_found_handler)
app.add_exception_handler(TranscriptAlreadyExistsError, transcript_already_exists_handler)
app.add_exception_handler(ExternalAPIError, external_api_error_handler)

# Register HTTPException handler (preserves FastAPI's built-in HTTP exceptions)
# MUST be registered before global Exception handler to prevent override
app.add_exception_handler(HTTPException, http_exception_handler)

# Register global exception handler (catch-all for unhandled exceptions)
app.add_exception_handler(Exception, global_exception_handler)

# Include routers
app.include_router(auth.router)
app.include_router(transcripts.router)
app.include_router(health.router)
app.include_router(conversations.router)
app.include_router(channels_router)  # Admin channel routes
app.include_router(settings_router)  # Admin settings routes
app.include_router(stats_router)  # Admin stats routes
app.include_router(users_router)  # Admin user management routes
app.include_router(channels.router)  # Public channel discovery
app.include_router(channel_conversations.router)  # Channel conversations

# WebSocket endpoint
app.websocket("/api/ws/chat")(websocket_endpoint)


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
    import os

    logger.info("🚀 YoutubeTalker API starting...")
    logger.info(f"📝 Environment: {settings.ENV}")
    logger.info(f"🔍 Debug mode: {settings.DEBUG}")
    logger.info("📚 API docs: http://localhost:8000/docs")

    # Configure LangSmith tracing if enabled
    if settings.LANGSMITH_TRACING and settings.LANGSMITH_API_KEY:
        os.environ["LANGCHAIN_TRACING_V2"] = "true"
        os.environ["LANGCHAIN_API_KEY"] = settings.LANGSMITH_API_KEY
        os.environ["LANGCHAIN_PROJECT"] = settings.LANGSMITH_PROJECT
        os.environ["LANGCHAIN_ENDPOINT"] = settings.LANGSMITH_ENDPOINT
        logger.info(f"🔬 LangSmith tracing enabled: {settings.LANGSMITH_PROJECT}")
    else:
        logger.info("🔬 LangSmith tracing disabled")


# Application shutdown event
@app.on_event("shutdown")
async def shutdown_event() -> None:
    """Execute cleanup tasks on application shutdown."""
    logger.info("👋 YoutubeTalker API shutting down...")
