"""
Centralized logging configuration using loguru.

Features:
- JSON-formatted logs for production parsing
- Request ID injection for tracing
- File rotation (500 MB per file)
- Console output with colors (dev mode)
- Async-safe logging
"""

import sys
from pathlib import Path

from loguru import logger

from app.config import settings

# Remove default handler
logger.remove()

# Console format with request ID support
# Note: request_id is optional - defaults to "no-request-id" if not set
console_format = (
    "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
    "<level>{level: <8}</level> | "
    "<cyan>{extra[request_id]}</cyan> | "
    "<level>{message}</level>"
)

# Add console handler (colored, human-readable)
logger.add(
    sys.stdout,
    format=console_format,
    level="DEBUG" if settings.DEBUG else "INFO",
    colorize=True,
)

# Create logs directory if it doesn't exist
log_dir = Path("logs")
log_dir.mkdir(exist_ok=True)

# Add file handler (JSON format, rotated)
# This is production-ready: compressed, rotated, and in JSON for log aggregation tools
logger.add(
    "logs/app.log",
    format="{time} {level} {message} {extra}",
    level="DEBUG",
    rotation="500 MB",  # Rotate when file reaches 500 MB
    compression="zip",   # Compress old log files
    serialize=True,      # JSON format for structured logging
    enqueue=True,        # Async-safe (thread-safe queue)
)

# Configure default request_id for logs without request context
logger.configure(extra={"request_id": "no-request-id"})
