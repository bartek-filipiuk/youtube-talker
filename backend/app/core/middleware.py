"""
Middleware Configuration

CORS, logging, and exception handling middleware for the FastAPI application.
"""

import time
from typing import Callable

from fastapi import FastAPI, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings


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

    # Request Logging Middleware
    @app.middleware("http")
    async def log_requests(request: Request, call_next: Callable) -> Response:
        """
        Log all incoming requests with timing information.

        Args:
            request: Incoming HTTP request
            call_next: Next middleware or route handler

        Returns:
            Response: HTTP response
        """
        start_time = time.time()

        # Log request
        print(f"→ {request.method} {request.url.path}")

        # Process request
        response = await call_next(request)

        # Calculate duration
        duration = time.time() - start_time

        # Log response
        print(
            f"← {request.method} {request.url.path} "
            f"[{response.status_code}] ({duration:.3f}s)"
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
        print(f"❌ Unhandled exception: {error_message}")

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
