"""
Middleware Configuration

CORS, logging, request ID tracking, and exception handling middleware for the FastAPI application.
"""

import time
import uuid
from contextvars import ContextVar
from typing import Callable

from fastapi import FastAPI, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from loguru import logger

from app.config import settings

# Context variable for request ID (thread-safe, async-safe)
request_id_var: ContextVar[str] = ContextVar("request_id", default="no-request-id")


def setup_middleware(app: FastAPI) -> None:
    """
    Configure all middleware for the FastAPI application.

    Args:
        app: FastAPI application instance
    """
    # CORS Middleware - must be added first
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["*"],
    )

    # Request ID Middleware - must be first to inject request_id into context
    @app.middleware("http")
    async def request_id_middleware(request: Request, call_next: Callable) -> Response:
        """
        Generate and inject request ID for distributed tracing.

        Creates a unique UUID for each request and makes it available:
        - In logs via contextvars
        - In response headers as X-Request-ID

        Args:
            request: Incoming HTTP request
            call_next: Next middleware or route handler

        Returns:
            Response: HTTP response with X-Request-ID header
        """
        # Generate unique request ID
        req_id = str(uuid.uuid4())
        request_id_var.set(req_id)

        # Process request with request_id in context
        with logger.contextualize(request_id=req_id):
            response = await call_next(request)

            # Add request ID to response headers for client-side tracing
            response.headers["X-Request-ID"] = req_id

        return response

    # Request Logging Middleware - logs after request_id is set
    @app.middleware("http")
    async def logging_middleware(request: Request, call_next: Callable) -> Response:
        """
        Log all incoming requests with timing and status information.

        Args:
            request: Incoming HTTP request
            call_next: Next middleware or route handler

        Returns:
            Response: HTTP response
        """
        start_time = time.time()

        # Log incoming request
        logger.info(f"→ {request.method} {request.url.path}")

        # Process request
        response = await call_next(request)

        # Calculate duration in milliseconds
        duration = (time.time() - start_time) * 1000

        # Log response with status and timing
        logger.info(
            f"← {request.method} {request.url.path} | "
            f"Status: {response.status_code} | "
            f"Duration: {duration:.2f}ms"
        )

        return response

    # Exception Handling Middleware
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        """
        Handle all unhandled exceptions globally.

        Args:
            request: Incoming HTTP request
            exc: Unhandled exception

        Returns:
            JSONResponse: Standardized error response
        """
        error_message = str(exc)

        # Log with full exception traceback
        logger.exception(f"Unhandled exception: {error_message}")

        # In production, don't expose internal error details
        if settings.ENV == "production":
            error_message = "Internal server error"

        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "detail": error_message,
                "type": "internal_server_error",
            },
        )


def get_cors_config() -> dict:
    """
    Get CORS configuration for reference.

    Returns:
        dict: CORS configuration settings
    """
    return {
        "allow_origins": settings.allowed_origins_list,
        "allow_credentials": True,
        "allow_methods": ["*"],
        "allow_headers": ["*"],
        "expose_headers": ["*"],
    }
