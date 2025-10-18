"""
Unit Tests for Security Utilities

Tests password hashing, verification, token generation, and token hashing.
"""

import pytest

from app.core.security import (
    hash_password,
    verify_password,
    generate_session_token,
    hash_token,
)


class TestPasswordHashing:
    """Tests for password hashing and verification."""

    def test_hash_password_returns_different_hashes(self):
        """Same password produces different hashes due to salt."""
        password = "testpass123"
        hash1 = hash_password(password)
        hash2 = hash_password(password)

        assert hash1 != hash2, "Hashes should be different (salt is random)"
        assert hash1.startswith("$2b$"), "Should use bcrypt format"
        assert hash2.startswith("$2b$"), "Should use bcrypt format"

    def test_hash_password_returns_string(self):
        """Hash password returns string (not bytes)."""
        password = "mypassword"
        hashed = hash_password(password)

        assert isinstance(hashed, str), "Should return string, not bytes"

    def test_verify_password_correct(self):
        """Correct password verification returns True."""
        password = "mypassword"
        hashed = hash_password(password)

        assert verify_password(password, hashed) is True

    def test_verify_password_incorrect(self):
        """Incorrect password verification returns False."""
        password = "mypassword"
        hashed = hash_password(password)

        assert verify_password("wrongpassword", hashed) is False

    def test_verify_password_case_sensitive(self):
        """Password verification is case-sensitive."""
        password = "MyPassword"
        hashed = hash_password(password)

        assert verify_password("mypassword", hashed) is False
        assert verify_password("MyPassword", hashed) is True

    def test_verify_password_with_special_characters(self):
        """Password with special characters works correctly."""
        password = "p@ssw0rd!#$%"
        hashed = hash_password(password)

        assert verify_password(password, hashed) is True
        assert verify_password("p@ssw0rd!#$", hashed) is False

    def test_hash_password_with_unicode(self):
        """Password with unicode characters works correctly."""
        password = "пароль123"  # Cyrillic
        hashed = hash_password(password)

        assert verify_password(password, hashed) is True
        assert verify_password("пароль124", hashed) is False


class TestSessionTokenGeneration:
    """Tests for session token generation."""

    def test_generate_session_token_unique(self):
        """Generated tokens are unique."""
        token1 = generate_session_token()
        token2 = generate_session_token()

        assert token1 != token2, "Tokens should be unique"

    def test_generate_session_token_length(self):
        """Generated tokens are 64 characters (32 bytes hex)."""
        token = generate_session_token()

        assert len(token) == 64, "Token should be 64 characters (32 bytes hex)"

    def test_generate_session_token_is_hex(self):
        """Generated tokens contain only hex characters."""
        token = generate_session_token()

        # Should be valid hex string
        try:
            int(token, 16)
            valid_hex = True
        except ValueError:
            valid_hex = False

        assert valid_hex, "Token should be valid hexadecimal"

    def test_generate_session_token_multiple(self):
        """Generating many tokens produces unique results."""
        tokens = [generate_session_token() for _ in range(100)]

        # All tokens should be unique
        assert len(set(tokens)) == 100, "All tokens should be unique"


class TestTokenHashing:
    """Tests for token hashing."""

    def test_hash_token_deterministic(self):
        """Same token produces same hash (deterministic)."""
        token = "test_token_12345"
        hash1 = hash_token(token)
        hash2 = hash_token(token)

        assert hash1 == hash2, "Same token should produce same hash"

    def test_hash_token_different_for_different_tokens(self):
        """Different tokens produce different hashes."""
        hash1 = hash_token("token1")
        hash2 = hash_token("token2")

        assert hash1 != hash2, "Different tokens should produce different hashes"

    def test_hash_token_length(self):
        """Hash token returns SHA-256 hex digest (64 characters)."""
        token = "any_token"
        hashed = hash_token(token)

        assert len(hashed) == 64, "SHA-256 hex digest should be 64 characters"

    def test_hash_token_is_hex(self):
        """Hashed token is valid hexadecimal."""
        token = "test_token"
        hashed = hash_token(token)

        # Should be valid hex string
        try:
            int(hashed, 16)
            valid_hex = True
        except ValueError:
            valid_hex = False

        assert valid_hex, "Hashed token should be valid hexadecimal"

    def test_hash_token_with_empty_string(self):
        """Hashing empty string produces valid hash."""
        hashed = hash_token("")

        assert len(hashed) == 64, "Should produce valid SHA-256 hash"
        assert isinstance(hashed, str), "Should return string"

    def test_hash_token_with_special_characters(self):
        """Token with special characters hashes correctly."""
        token = "token!@#$%^&*()"
        hashed = hash_token(token)

        assert len(hashed) == 64
        # Same token should produce same hash
        assert hashed == hash_token(token)


class TestIntegration:
    """Integration tests for security functions."""

    def test_full_password_flow(self):
        """Test complete password registration and login flow."""
        # Registration: hash password
        password = "user_password_123"
        hashed = hash_password(password)

        # Login: verify password
        assert verify_password(password, hashed) is True
        assert verify_password("wrong_password", hashed) is False

    def test_full_session_token_flow(self):
        """Test complete session token generation and validation flow."""
        # Generate token
        raw_token = generate_session_token()

        # Store hashed version
        stored_hash = hash_token(raw_token)

        # Validate: hash incoming token and compare
        incoming_token = raw_token
        incoming_hash = hash_token(incoming_token)

        assert stored_hash == incoming_hash, "Token should validate correctly"

        # Invalid token should not match
        invalid_token = generate_session_token()
        invalid_hash = hash_token(invalid_token)

        assert stored_hash != invalid_hash, "Invalid token should not match"
