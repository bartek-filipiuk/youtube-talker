"""
YoutubeTalker API - Main Application Entry Point

FastAPI application for AI-powered YouTube video Q&A and content generation.
"""

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app.config import settings
from app.core.middleware import setup_middleware

# Create FastAPI application instance
app = FastAPI(
    title="YoutubeTalker API",
    description="AI-powered YouTube video Q&A and content generation using RAG",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Setup middleware (CORS, logging, exception handling)
setup_middleware(app)


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
