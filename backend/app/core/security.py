"""
Security Utilities

Functions for password hashing, token generation, and token hashing.
Used by authentication service for secure credential and session management.
"""

import hashlib
import secrets

import bcrypt


def hash_password(password: str) -> str:
    """
    Hash password using bcrypt with cost factor 12.

    Bcrypt automatically handles salt generation, so each hash
    of the same password will be different.

    Args:
        password: Plain text password to hash

    Returns:
        Hashed password string (includes salt)

    Example:
        >>> hash_password("mypassword123")
        '$2b$12$...'
    """
    # Encode password to bytes
    password_bytes = password.encode('utf-8')

    # Generate hash with cost factor 12
    hashed = bcrypt.hashpw(password_bytes, bcrypt.gensalt(rounds=12))

    # Return as string (decode from bytes)
    return hashed.decode('utf-8')


def verify_password(plain: str, hashed: str) -> bool:
    """
    Verify password against hashed version.

    Uses bcrypt's constant-time comparison to prevent timing attacks.

    Args:
        plain: Plain text password to check
        hashed: Previously hashed password (from database)

    Returns:
        True if password matches, False otherwise

    Example:
        >>> hashed = hash_password("mypassword")
        >>> verify_password("mypassword", hashed)
        True
        >>> verify_password("wrongpassword", hashed)
        False
    """
    # Encode both to bytes
    plain_bytes = plain.encode('utf-8')
    hashed_bytes = hashed.encode('utf-8')

    # Verify with bcrypt (constant-time comparison)
    return bcrypt.checkpw(plain_bytes, hashed_bytes)


def generate_session_token() -> str:
    """
    Generate cryptographically secure random session token.

    Uses secrets module (cryptographically secure random number generator)
    instead of random module (not secure).

    Returns:
        64-character hex string (32 bytes)

    Example:
        >>> token = generate_session_token()
        >>> len(token)
        64
        >>> token != generate_session_token()  # Always unique
        True
    """
    # Generate 32 random bytes, convert to 64-character hex string
    return secrets.token_hex(32)


def hash_token(token: str) -> str:
    """
    Hash session token before storing in database (SHA-256).

    Rationale:
        If database is compromised, raw tokens cannot be used directly.
        Tokens must be hashed with same algorithm to match database entries.

    Note:
        Unlike password hashing, this is deterministic (no salt).
        Same token always produces same hash (needed for lookup).

    Args:
        token: Raw session token to hash

    Returns:
        SHA-256 hash as hex string (64 characters)

    Example:
        >>> token = "test_token_12345"
        >>> hash1 = hash_token(token)
        >>> hash2 = hash_token(token)
        >>> hash1 == hash2  # Deterministic
        True
        >>> len(hash1)
        64
    """
    # Encode token to bytes
    token_bytes = token.encode('utf-8')

    # Hash with SHA-256
    hash_object = hashlib.sha256(token_bytes)

    # Return hex digest (64 characters)
    return hash_object.hexdigest()
