"""
Pydantic Schemas for Authentication

Request and response models for authentication endpoints.
All schemas include validation for data integrity.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, ConfigDict


class RegisterRequest(BaseModel):
    """
    User registration request.

    Validates:
    - Email format (via EmailStr)
    - Password minimum length (8 characters)
    """

    email: EmailStr = Field(
        ...,
        description="User email address",
        examples=["user@example.com"],
    )
    password: str = Field(
        ...,
        min_length=8,
        description="Password must be at least 8 characters",
        examples=["mypassword123"],
    )


class LoginRequest(BaseModel):
    """
    User login request.

    No validation needed beyond types (password validation during registration only).
    """

    email: EmailStr = Field(
        ...,
        description="User email address",
        examples=["user@example.com"],
    )
    password: str = Field(
        ...,
        description="User password",
        examples=["mypassword123"],
    )


class TokenResponse(BaseModel):
    """
    Session token response after successful login.

    Includes:
    - Session token (64-character hex string)
    - User ID (UUID as string)
    - User email
    """

    token: str = Field(
        ...,
        description="Session token for authentication (64 characters)",
        examples=["a3f5b2c1d4e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0f1a2"],
    )
    user_id: str = Field(
        ...,
        description="User ID (UUID as string)",
        examples=["123e4567-e89b-12d3-a456-426614174000"],
    )
    email: str = Field(
        ...,
        description="User email address",
        examples=["user@example.com"],
    )


class UserResponse(BaseModel):
    """
    User data response (for /auth/me and registration).

    Returns user information without sensitive data (no password_hash).
    """

    model_config = ConfigDict(from_attributes=True)  # Enable ORM mode (SQLAlchemy 2.0)

    id: UUID = Field(
        ...,
        description="User ID",
        examples=["123e4567-e89b-12d3-a456-426614174000"],
    )
    email: str = Field(
        ...,
        description="User email address",
        examples=["user@example.com"],
    )
    role: str = Field(
        ...,
        description="User role (user or admin)",
        examples=["user", "admin"],
    )
    created_at: datetime = Field(
        ...,
        description="Account creation timestamp",
        examples=["2025-01-01T12:00:00"],
    )
