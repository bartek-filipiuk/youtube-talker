"""
Unit Tests for WebSocket Rate Limiter
"""

import pytest
from time import sleep
from uuid import uuid4

from app.api.websocket.rate_limiter import RateLimiter


@pytest.fixture
def rate_limiter():
    """Create a fresh RateLimiter instance for each test."""
    return RateLimiter(max_requests=3, window_seconds=2)  # 3 requests per 2 seconds for testing


@pytest.fixture
def user_id():
    """Create a test user ID."""
    return uuid4()


def test_first_request_allowed(rate_limiter, user_id):
    """First request should always be allowed."""
    assert rate_limiter.check_rate_limit(user_id) is True


def test_multiple_requests_within_limit(rate_limiter, user_id):
    """Multiple requests within limit should all be allowed."""
    # 3 requests allowed
    assert rate_limiter.check_rate_limit(user_id) is True
    assert rate_limiter.check_rate_limit(user_id) is True
    assert rate_limiter.check_rate_limit(user_id) is True


def test_rate_limit_exceeded(rate_limiter, user_id):
    """Request beyond limit should be rejected."""
    # Use up the limit (3 requests)
    for _ in range(3):
        assert rate_limiter.check_rate_limit(user_id) is True

    # 4th request should fail
    assert rate_limiter.check_rate_limit(user_id) is False


def test_different_users_independent_limits(rate_limiter):
    """Different users should have independent rate limits."""
    user1 = uuid4()
    user2 = uuid4()

    # User 1 uses up their limit
    for _ in range(3):
        assert rate_limiter.check_rate_limit(user1) is True

    # User 1's 4th request fails
    assert rate_limiter.check_rate_limit(user1) is False

    # User 2's first request still works
    assert rate_limiter.check_rate_limit(user2) is True


def test_sliding_window_resets(rate_limiter, user_id):
    """Sliding window should allow new requests after window expires."""
    # Use up the limit
    for _ in range(3):
        assert rate_limiter.check_rate_limit(user_id) is True

    # 4th request fails
    assert rate_limiter.check_rate_limit(user_id) is False

    # Wait for window to expire
    sleep(2.1)

    # Should be allowed again
    assert rate_limiter.check_rate_limit(user_id) is True


def test_partial_window_reset(rate_limiter, user_id):
    """Sliding window should partially reset as old requests expire."""
    # First request
    assert rate_limiter.check_rate_limit(user_id) is True

    # Wait a bit
    sleep(1.0)

    # Two more requests (total 3, at limit)
    assert rate_limiter.check_rate_limit(user_id) is True
    assert rate_limiter.check_rate_limit(user_id) is True

    # 4th fails (first request still in window)
    assert rate_limiter.check_rate_limit(user_id) is False

    # Wait for first request to expire
    sleep(1.1)

    # Should work now (first request expired)
    assert rate_limiter.check_rate_limit(user_id) is True


def test_reset_user(rate_limiter, user_id):
    """reset_user should clear rate limit for specific user."""
    # Use up the limit
    for _ in range(3):
        rate_limiter.check_rate_limit(user_id)

    # Should be blocked
    assert rate_limiter.check_rate_limit(user_id) is False

    # Reset user
    rate_limiter.reset_user(user_id)

    # Should work again
    assert rate_limiter.check_rate_limit(user_id) is True


def test_reset_user_non_existent(rate_limiter):
    """reset_user should not error for non-existent user."""
    non_existent_user = uuid4()
    rate_limiter.reset_user(non_existent_user)  # Should not raise


def test_get_remaining(rate_limiter, user_id):
    """get_remaining should return correct remaining request count."""
    # Initially, 3 remaining
    assert rate_limiter.get_remaining(user_id) == 3

    # After 1 request, 2 remaining
    rate_limiter.check_rate_limit(user_id)
    assert rate_limiter.get_remaining(user_id) == 2

    # After 2 requests, 1 remaining
    rate_limiter.check_rate_limit(user_id)
    assert rate_limiter.get_remaining(user_id) == 1

    # After 3 requests, 0 remaining
    rate_limiter.check_rate_limit(user_id)
    assert rate_limiter.get_remaining(user_id) == 0


def test_get_remaining_non_existent_user(rate_limiter):
    """get_remaining should return max for non-existent user."""
    non_existent_user = uuid4()
    assert rate_limiter.get_remaining(non_existent_user) == 3


def test_clear_all(rate_limiter, user_id):
    """clear_all should reset all rate limit data."""
    user2 = uuid4()

    # Use up limits for two users
    for _ in range(3):
        rate_limiter.check_rate_limit(user_id)
        rate_limiter.check_rate_limit(user2)

    # Both should be blocked
    assert rate_limiter.check_rate_limit(user_id) is False
    assert rate_limiter.check_rate_limit(user2) is False

    # Clear all
    rate_limiter.clear_all()

    # Both should work again
    assert rate_limiter.check_rate_limit(user_id) is True
    assert rate_limiter.check_rate_limit(user2) is True


def test_custom_limits():
    """Test creating rate limiter with custom limits."""
    custom_limiter = RateLimiter(max_requests=5, window_seconds=10)
    user_id = uuid4()

    # Should allow 5 requests
    for _ in range(5):
        assert custom_limiter.check_rate_limit(user_id) is True

    # 6th should fail
    assert custom_limiter.check_rate_limit(user_id) is False


def test_concurrent_requests_same_user(rate_limiter, user_id):
    """Test that concurrent requests from same user are properly limited."""
    # Simulate rapid-fire requests (common in real usage)
    results = [rate_limiter.check_rate_limit(user_id) for _ in range(5)]

    # First 3 should succeed
    assert results[0] is True
    assert results[1] is True
    assert results[2] is True

    # Last 2 should fail
    assert results[3] is False
    assert results[4] is False


def test_rate_limiter_singleton():
    """Test that the global rate_limiter singleton is properly configured."""
    from app.api.websocket.rate_limiter import rate_limiter

    # Should be configured for 10 requests per 60 seconds
    assert rate_limiter.max_requests == 10
    assert rate_limiter.window_seconds == 60
