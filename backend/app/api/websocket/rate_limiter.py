"""
WebSocket Rate Limiter

Simple in-memory rate limiter for WebSocket connections.
Limits messages per user within a sliding time window.
"""

from loguru import logger
from collections import defaultdict
from time import time
from typing import Dict, List
from uuid import UUID



class RateLimiter:
    """
    Rate limiter for WebSocket messages.

    Uses sliding window algorithm with in-memory storage.
    Good for MVP with single-instance deployment.

    For production with multiple instances, consider Redis-based rate limiting.
    """

    def __init__(self, max_requests: int = 10, window_seconds: int = 60):
        """
        Initialize rate limiter.

        Args:
            max_requests: Maximum number of requests allowed in the window
            window_seconds: Time window in seconds (default: 60 = 1 minute)
        """
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests: Dict[UUID, List[float]] = defaultdict(list)
        logger.info(
            f"RateLimiter initialized: {max_requests} requests per {window_seconds}s"
        )

    def check_rate_limit(self, user_id: UUID) -> bool:
        """
        Check if user has exceeded rate limit.

        Uses sliding window: removes timestamps outside the current window,
        then checks if the remaining count is below the limit.

        Args:
            user_id: User's UUID

        Returns:
            True if request is allowed, False if rate limit exceeded

        Example:
            if not rate_limiter.check_rate_limit(user_id):
                return ErrorMessage(code="RATE_LIMIT")
        """
        now = time()

        # Remove timestamps outside the current window
        cutoff_time = now - self.window_seconds
        self.requests[user_id] = [
            timestamp
            for timestamp in self.requests[user_id]
            if timestamp > cutoff_time
        ]

        # Check if limit exceeded
        current_count = len(self.requests[user_id])

        if current_count >= self.max_requests:
            logger.warning(
                f"Rate limit exceeded for user {user_id}: "
                f"{current_count}/{self.max_requests} in {self.window_seconds}s"
            )
            return False

        # Record this request
        self.requests[user_id].append(now)
        logger.debug(
            f"Rate limit check passed for user {user_id}: "
            f"{current_count + 1}/{self.max_requests}"
        )
        return True

    def reset_user(self, user_id: UUID) -> None:
        """
        Reset rate limit for a specific user.

        Useful for testing or administrative actions.

        Args:
            user_id: User's UUID
        """
        if user_id in self.requests:
            del self.requests[user_id]
            logger.info(f"Rate limit reset for user {user_id}")

    def get_remaining(self, user_id: UUID) -> int:
        """
        Get remaining requests for a user in the current window.

        Args:
            user_id: User's UUID

        Returns:
            Number of requests remaining before rate limit is hit
        """
        now = time()
        cutoff_time = now - self.window_seconds

        # Count requests in current window
        current_count = sum(
            1 for timestamp in self.requests.get(user_id, [])
            if timestamp > cutoff_time
        )

        return max(0, self.max_requests - current_count)

    def clear_all(self) -> None:
        """
        Clear all rate limit data.

        Useful for testing or system maintenance.
        """
        self.requests.clear()
        logger.info("All rate limit data cleared")


# Global singleton instance
# 10 messages per minute (60 seconds) per user
rate_limiter = RateLimiter(max_requests=10, window_seconds=60)
