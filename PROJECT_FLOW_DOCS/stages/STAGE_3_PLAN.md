# Stage 3: Authentication & Session Management - Implementation Plan

**Created:** 2025-10-18
**Phase:** 3 (Auth & Sessions)
**Stages:** 3.1 - 3.6
**PR Strategy:** 2 Pull Requests

---

## Overview

Phase 3 implements complete user authentication and session management with:
- Secure password hashing (bcrypt)
- Session-based authentication (7-day expiry)
- Token generation and validation
- Rate-limited auth endpoints
- Full test coverage (unit + integration)

**Split Strategy:**
- **PR #3**: Core logic (3.1-3.3) - Security utils, auth service, schemas
- **PR #4**: API layer (3.4-3.6) - Endpoints, dependency, integration tests

---

## Design Decisions

### 1. Session Cleanup
**Decision:** Manual deletion only for MVP
**Rationale:** Keeps MVP simple, can add background task in post-MVP if needed
**Implementation:** `delete_expired()` method exists in SessionRepository but not called automatically

### 2. Password Validation
**Decision:** Minimum length 8 characters only
**Rationale:** KISS principle for MVP, sufficient for demo/testing
**Implementation:** Pydantic `Field(min_length=8)` validation

### 3. Login Rate Limiting
**Decision:** Add rate limiting to login/register endpoints (5 attempts/min)
**Rationale:** Prevent brute force attacks, SlowAPI already in stack
**Implementation:** `@limiter.limit("5/minute")` decorator on endpoints

### 4. Session Expiry Testing
**Decision:** Test logic only, no time mocking/delays
**Rationale:** Fast tests, avoid complexity of time manipulation
**Implementation:** Create sessions with past `expires_at`, verify validation fails

### 5. Error Logging
**Decision:** Standard logging, no special security audit log for MVP
**Rationale:** Keeps MVP simple, standard logs sufficient for debugging
**Implementation:** Use existing logging middleware

---

## PR #3: Core Authentication Logic (Stages 3.1-3.3)

### Branch: `feat/phase-3-auth-core`

---

### Stage 3.1: Security Utilities

**File:** `app/core/security.py`

#### Functions to Implement:

```python
def hash_password(password: str) -> str:
    """
    Hash password using bcrypt with cost factor 12.

    Args:
        password: Plain text password

    Returns:
        Hashed password string (includes salt)

    Example:
        >>> hash_password("mypassword123")
        '$2b$12$...'
    """
```

**Implementation Details:**
- Use `bcrypt.hashpw()` or `passlib.hash.bcrypt.hash()`
- Cost factor: 12 (good balance of security and performance)
- Returns string (bcrypt handles salt automatically)

```python
def verify_password(plain: str, hashed: str) -> bool:
    """
    Verify password against hashed version.

    Args:
        plain: Plain text password to check
        hashed: Previously hashed password

    Returns:
        True if password matches, False otherwise
    """
```

**Implementation Details:**
- Use `bcrypt.checkpw()` or `passlib.hash.bcrypt.verify()`
- Returns boolean
- Handles timing attacks (bcrypt is constant-time)

```python
def generate_session_token() -> str:
    """
    Generate cryptographically secure random session token.

    Returns:
        64-character hex string (32 bytes)

    Example:
        >>> generate_session_token()
        'a3f5b2c...(64 chars total)'
    """
```

**Implementation Details:**
- Use `secrets.token_hex(32)` - generates 32 bytes = 64 hex chars
- Cryptographically secure (not `random` module)

```python
def hash_token(token: str) -> str:
    """
    Hash session token before storing in database (SHA-256).

    Args:
        token: Raw session token

    Returns:
        SHA-256 hash as hex string

    Rationale:
        If database is compromised, tokens cannot be used directly.
    """
```

**Implementation Details:**
- Use `hashlib.sha256(token.encode()).hexdigest()`
- Deterministic hashing (same token = same hash)
- Not salted (need to find by hash)

#### Unit Tests: `tests/unit/test_security.py`

```python
import pytest
from app.core.security import (
    hash_password,
    verify_password,
    generate_session_token,
    hash_token,
)


def test_hash_password_returns_different_hashes():
    """Same password produces different hashes (salt works)."""
    password = "testpass123"
    hash1 = hash_password(password)
    hash2 = hash_password(password)

    assert hash1 != hash2
    assert hash1.startswith("$2b$")  # bcrypt format


def test_verify_password_correct():
    """Correct password verification returns True."""
    password = "mypassword"
    hashed = hash_password(password)

    assert verify_password(password, hashed) is True


def test_verify_password_incorrect():
    """Incorrect password verification returns False."""
    password = "mypassword"
    hashed = hash_password(password)

    assert verify_password("wrongpassword", hashed) is False


def test_generate_session_token_unique():
    """Generated tokens are unique."""
    token1 = generate_session_token()
    token2 = generate_session_token()

    assert token1 != token2
    assert len(token1) == 64
    assert len(token2) == 64


def test_hash_token_deterministic():
    """Same token produces same hash."""
    token = "test_token_12345"
    hash1 = hash_token(token)
    hash2 = hash_token(token)

    assert hash1 == hash2
    assert len(hash1) == 64  # SHA-256 hex = 64 chars


def test_hash_token_different_for_different_tokens():
    """Different tokens produce different hashes."""
    hash1 = hash_token("token1")
    hash2 = hash_token("token2")

    assert hash1 != hash2
```

**Acceptance Criteria:**
- All tests pass
- Coverage > 80% for `security.py`
- Functions work with edge cases (empty strings handled by Pydantic)

---

### Stage 3.2: Authentication Service

**File:** `app/services/auth_service.py`

#### AuthService Class:

```python
from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException

from app.core.security import hash_password, verify_password, generate_session_token, hash_token
from app.db.repositories.user_repo import UserRepository
from app.db.repositories.session_repo import SessionRepository
from app.db.models import User


class AuthService:
    """
    Business logic for authentication and session management.
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.user_repo = UserRepository(db)
        self.session_repo = SessionRepository(db)
```

#### Methods:

```python
async def register_user(self, email: str, password: str) -> User:
    """
    Register new user with email and password.

    Args:
        email: User email (validated by Pydantic)
        password: Plain password (min 8 chars, validated by Pydantic)

    Returns:
        Created User object

    Raises:
        HTTPException(409): Email already exists
    """
    # Check if email exists
    existing_user = await self.user_repo.get_by_email(email)
    if existing_user:
        raise HTTPException(status_code=409, detail="Email already registered")

    # Hash password
    password_hash = hash_password(password)

    # Create user
    user = await self.user_repo.create(email=email, password_hash=password_hash)
    await self.db.commit()

    return user
```

```python
async def login(self, email: str, password: str) -> dict:
    """
    Authenticate user and create session.

    Args:
        email: User email
        password: Plain password

    Returns:
        dict with keys: token, user_id, email

    Raises:
        HTTPException(401): Invalid credentials
    """
    # Get user by email
    user = await self.user_repo.get_by_email(email)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # Verify password
    if not verify_password(password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # Generate token
    token = generate_session_token()
    token_hash = hash_token(token)

    # Create session (7-day expiry)
    expires_at = datetime.utcnow() + timedelta(days=7)
    await self.session_repo.create(
        user_id=user.id,
        token_hash=token_hash,
        expires_at=expires_at
    )
    await self.db.commit()

    return {
        "token": token,
        "user_id": str(user.id),
        "email": user.email
    }
```

```python
async def logout(self, token: str) -> None:
    """
    Invalidate session (delete from database).

    Args:
        token: Session token

    Note:
        Idempotent - succeeds even if token doesn't exist
    """
    token_hash = hash_token(token)
    session = await self.session_repo.get_by_token(token_hash)

    if session:
        await self.session_repo.delete(session.id)
        await self.db.commit()
```

```python
async def validate_session(self, token: str) -> User:
    """
    Validate session token and return user.

    Args:
        token: Session token

    Returns:
        User object if session valid

    Raises:
        HTTPException(401): Invalid or expired session
    """
    token_hash = hash_token(token)
    session = await self.session_repo.get_by_token(token_hash)

    if not session:
        raise HTTPException(status_code=401, detail="Invalid session")

    # Check expiry
    if session.expires_at < datetime.utcnow():
        raise HTTPException(status_code=401, detail="Session expired")

    # Get user
    user = await self.user_repo.get_by_id(session.user_id)
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    return user
```

#### Unit Tests: `tests/unit/test_auth_service.py`

```python
import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock
from fastapi import HTTPException

from app.services.auth_service import AuthService
from app.db.models import User, Session


@pytest.fixture
def mock_db():
    """Mock database session."""
    db = AsyncMock()
    return db


@pytest.fixture
def auth_service(mock_db):
    """AuthService with mocked repositories."""
    service = AuthService(mock_db)
    service.user_repo = AsyncMock()
    service.session_repo = AsyncMock()
    return service


@pytest.mark.asyncio
async def test_register_user_success(auth_service, mock_db):
    """Successful user registration."""
    # Mock: email doesn't exist
    auth_service.user_repo.get_by_email.return_value = None

    # Mock: user creation
    mock_user = User(id="test-uuid", email="test@example.com", password_hash="hashed")
    auth_service.user_repo.create.return_value = mock_user

    # Register
    user = await auth_service.register_user("test@example.com", "password123")

    assert user.email == "test@example.com"
    auth_service.user_repo.create.assert_called_once()
    mock_db.commit.assert_called_once()


@pytest.mark.asyncio
async def test_register_user_duplicate_email(auth_service):
    """Registration fails with duplicate email."""
    # Mock: email exists
    existing_user = User(id="existing-uuid", email="test@example.com", password_hash="hash")
    auth_service.user_repo.get_by_email.return_value = existing_user

    # Should raise 409
    with pytest.raises(HTTPException) as exc_info:
        await auth_service.register_user("test@example.com", "password123")

    assert exc_info.value.status_code == 409


@pytest.mark.asyncio
async def test_login_success(auth_service, mock_db):
    """Successful login creates session."""
    # Mock: user exists
    mock_user = User(
        id="user-uuid",
        email="test@example.com",
        password_hash="$2b$12$..."  # Real bcrypt hash for "password123"
    )
    # Need to actually hash for verify_password to work
    from app.core.security import hash_password
    mock_user.password_hash = hash_password("password123")
    auth_service.user_repo.get_by_email.return_value = mock_user

    # Login
    result = await auth_service.login("test@example.com", "password123")

    assert "token" in result
    assert result["email"] == "test@example.com"
    auth_service.session_repo.create.assert_called_once()


@pytest.mark.asyncio
async def test_login_wrong_password(auth_service):
    """Login fails with wrong password."""
    from app.core.security import hash_password
    mock_user = User(
        id="user-uuid",
        email="test@example.com",
        password_hash=hash_password("correctpassword")
    )
    auth_service.user_repo.get_by_email.return_value = mock_user

    with pytest.raises(HTTPException) as exc_info:
        await auth_service.login("test@example.com", "wrongpassword")

    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_login_nonexistent_user(auth_service):
    """Login fails for nonexistent user."""
    auth_service.user_repo.get_by_email.return_value = None

    with pytest.raises(HTTPException) as exc_info:
        await auth_service.login("nonexistent@example.com", "password")

    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_logout_success(auth_service, mock_db):
    """Successful logout deletes session."""
    mock_session = Session(id="session-uuid", user_id="user-uuid", token_hash="hash", expires_at=datetime.utcnow())
    auth_service.session_repo.get_by_token.return_value = mock_session

    await auth_service.logout("some-token")

    auth_service.session_repo.delete.assert_called_once_with(mock_session.id)
    mock_db.commit.assert_called_once()


@pytest.mark.asyncio
async def test_logout_invalid_token(auth_service, mock_db):
    """Logout with invalid token is idempotent (no error)."""
    auth_service.session_repo.get_by_token.return_value = None

    await auth_service.logout("invalid-token")

    # Should not call delete or commit
    auth_service.session_repo.delete.assert_not_called()


@pytest.mark.asyncio
async def test_validate_session_success(auth_service):
    """Valid session returns user."""
    mock_session = Session(
        id="session-uuid",
        user_id="user-uuid",
        token_hash="hash",
        expires_at=datetime.utcnow() + timedelta(days=7)
    )
    mock_user = User(id="user-uuid", email="test@example.com", password_hash="hash")

    auth_service.session_repo.get_by_token.return_value = mock_session
    auth_service.user_repo.get_by_id.return_value = mock_user

    user = await auth_service.validate_session("valid-token")

    assert user.email == "test@example.com"


@pytest.mark.asyncio
async def test_validate_session_expired(auth_service):
    """Expired session raises 401."""
    mock_session = Session(
        id="session-uuid",
        user_id="user-uuid",
        token_hash="hash",
        expires_at=datetime.utcnow() - timedelta(hours=1)  # Expired 1 hour ago
    )
    auth_service.session_repo.get_by_token.return_value = mock_session

    with pytest.raises(HTTPException) as exc_info:
        await auth_service.validate_session("expired-token")

    assert exc_info.value.status_code == 401
    assert "expired" in exc_info.value.detail.lower()


@pytest.mark.asyncio
async def test_validate_session_invalid_token(auth_service):
    """Invalid session token raises 401."""
    auth_service.session_repo.get_by_token.return_value = None

    with pytest.raises(HTTPException) as exc_info:
        await auth_service.validate_session("invalid-token")

    assert exc_info.value.status_code == 401
```

**Acceptance Criteria:**
- All tests pass
- Mocked repositories (no database calls in unit tests)
- Coverage > 80% for `auth_service.py`

---

### Stage 3.3: Pydantic Schemas

**File:** `app/schemas/auth.py`

```python
"""
Pydantic schemas for authentication endpoints.
"""

from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    """User registration request."""
    email: EmailStr
    password: str = Field(..., min_length=8, description="Password must be at least 8 characters")


class LoginRequest(BaseModel):
    """User login request."""
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    """Session token response after login."""
    token: str
    user_id: str  # UUID as string
    email: str


class UserResponse(BaseModel):
    """User data response."""
    id: UUID
    email: str
    created_at: datetime

    class Config:
        from_attributes = True  # SQLAlchemy 2.0 (was orm_mode in v1)
```

**No Unit Tests Needed:**
- Pydantic schemas are declarative
- Validation is automatic (tested via integration tests)

**Acceptance Criteria:**
- Schemas defined with proper types
- Email validation works (Pydantic EmailStr)
- Password minimum length enforced

---

### PR #3 Completion Checklist

- [ ] `app/core/security.py` implemented
- [ ] `tests/unit/test_security.py` written and passing
- [ ] `app/services/auth_service.py` implemented
- [ ] `tests/unit/test_auth_service.py` written and passing
- [ ] `app/schemas/auth.py` defined
- [ ] Run `pytest tests/unit/test_security.py tests/unit/test_auth_service.py -v`
- [ ] Run `pytest tests/unit/ --cov=app/core/security --cov=app/services/auth_service`
- [ ] Verify coverage > 80%
- [ ] No linting errors: `ruff check app/`
- [ ] Code formatted: `black app/`
- [ ] Create branch: `git checkout -b feat/phase-3-auth-core`
- [ ] Commit changes with descriptive message
- [ ] Push to remote: `git push origin feat/phase-3-auth-core`
- [ ] Create PR #3 via `gh pr create`
- [ ] Update HANDOFF.md: Mark 3.1, 3.2, 3.3 as complete

---

## PR #4: API Layer (Stages 3.4-3.6)

### Branch: `feat/phase-3-auth-api`

**Note:** Start PR #4 after PR #3 is merged to main

---

### Stage 3.4: Auth API Endpoints

**File:** `app/api/routes/auth.py`

```python
"""
Authentication API endpoints.
"""

from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.ext.asyncio import AsyncSession
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.db.session import get_db
from app.schemas.auth import RegisterRequest, LoginRequest, TokenResponse, UserResponse
from app.services.auth_service import AuthService

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)


@router.post("/register", response_model=UserResponse, status_code=201)
@limiter.limit("5/minute")
async def register(
    request: RegisterRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Register new user.

    Rate limit: 5 attempts per minute
    """
    auth_service = AuthService(db)
    user = await auth_service.register_user(request.email, request.password)
    return user


@router.post("/login", response_model=TokenResponse)
@limiter.limit("5/minute")
async def login(
    request: LoginRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Login and receive session token.

    Rate limit: 5 attempts per minute
    """
    auth_service = AuthService(db)
    result = await auth_service.login(request.email, request.password)
    return result


@router.post("/logout", status_code=204)
async def logout(
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db)
):
    """
    Logout (invalidate session).

    Requires: Authorization header with Bearer token
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing authorization header")

    token = authorization.replace("Bearer ", "")
    auth_service = AuthService(db)
    await auth_service.logout(token)
    return None  # 204 No Content


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user = Depends(get_current_user),
):
    """
    Get current authenticated user info.

    Requires: Valid session token
    """
    return current_user
```

**Update:** `app/main.py`

```python
from app.api.routes import auth

# Add to existing routers
app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
```

**SlowAPI Configuration** (if not already in `main.py`):

```python
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
```

---

### Stage 3.5: Authentication Dependency

**File:** `app/dependencies.py` (or `app/api/dependencies.py`)

```python
"""
FastAPI dependency injection functions.
"""

from fastapi import Depends, HTTPException, Header
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.db.models import User
from app.services.auth_service import AuthService


async def get_current_user(
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db)
) -> User:
    """
    Dependency to get current authenticated user from token.

    Args:
        authorization: Authorization header (Bearer <token>)
        db: Database session

    Returns:
        User object

    Raises:
        HTTPException(401): Invalid or missing token
    """
    if not authorization:
        raise HTTPException(
            status_code=401,
            detail="Missing authorization header"
        )

    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Invalid authorization header format. Expected: Bearer <token>"
        )

    token = authorization.replace("Bearer ", "")

    auth_service = AuthService(db)
    try:
        user = await auth_service.validate_session(token)
        return user
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=401, detail="Invalid session")
```

**Import in `auth.py`:**

```python
from app.dependencies import get_current_user
```

---

### Stage 3.6: Integration Tests

**File:** `tests/integration/test_auth_endpoints.py`

```python
"""
Integration tests for authentication endpoints.
"""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta

from app.main import app
from app.db.models import User, Session
from app.core.security import hash_password, hash_token


@pytest.mark.asyncio
async def test_register_success(client: AsyncClient, db_session: AsyncSession):
    """Successful user registration."""
    response = await client.post(
        "/api/auth/register",
        json={"email": "newuser@example.com", "password": "password123"}
    )

    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "newuser@example.com"
    assert "id" in data
    assert "created_at" in data


@pytest.mark.asyncio
async def test_register_duplicate_email(client: AsyncClient, db_session: AsyncSession, test_user: User):
    """Registration with duplicate email returns 409."""
    response = await client.post(
        "/api/auth/register",
        json={"email": test_user.email, "password": "password123"}
    )

    assert response.status_code == 409
    assert "already registered" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_register_invalid_email(client: AsyncClient):
    """Registration with invalid email returns 422."""
    response = await client.post(
        "/api/auth/register",
        json={"email": "not-an-email", "password": "password123"}
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_register_short_password(client: AsyncClient):
    """Registration with short password returns 422."""
    response = await client.post(
        "/api/auth/register",
        json={"email": "test@example.com", "password": "short"}
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient, test_user: User):
    """Successful login returns token."""
    response = await client.post(
        "/api/auth/login",
        json={"email": test_user.email, "password": "testpassword"}
    )

    assert response.status_code == 200
    data = response.json()
    assert "token" in data
    assert data["email"] == test_user.email
    assert len(data["token"]) == 64  # 32 bytes hex


@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient, test_user: User):
    """Login with wrong password returns 401."""
    response = await client.post(
        "/api/auth/login",
        json={"email": test_user.email, "password": "wrongpassword"}
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_login_nonexistent_user(client: AsyncClient):
    """Login with nonexistent email returns 401."""
    response = await client.post(
        "/api/auth/login",
        json={"email": "nonexistent@example.com", "password": "password123"}
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_logout_success(client: AsyncClient, test_user: User, test_session: Session, test_token: str):
    """Successful logout invalidates session."""
    response = await client.post(
        "/api/auth/logout",
        headers={"Authorization": f"Bearer {test_token}"}
    )

    assert response.status_code == 204


@pytest.mark.asyncio
async def test_logout_without_token(client: AsyncClient):
    """Logout without token returns 401."""
    response = await client.post("/api/auth/logout")

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_me_success(client: AsyncClient, test_user: User, test_session: Session, test_token: str):
    """Get current user with valid token."""
    response = await client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {test_token}"}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["email"] == test_user.email


@pytest.mark.asyncio
async def test_get_me_without_token(client: AsyncClient):
    """Get current user without token returns 401."""
    response = await client.get("/api/auth/me")

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_me_invalid_token(client: AsyncClient):
    """Get current user with invalid token returns 401."""
    response = await client.get(
        "/api/auth/me",
        headers={"Authorization": "Bearer invalid_token_12345"}
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_me_expired_token(client: AsyncClient, db_session: AsyncSession, test_user: User):
    """Get current user with expired token returns 401."""
    from app.core.security import generate_session_token, hash_token

    # Create expired session
    token = generate_session_token()
    token_hash = hash_token(token)
    expired_session = Session(
        user_id=test_user.id,
        token_hash=token_hash,
        expires_at=datetime.utcnow() - timedelta(hours=1)  # Expired 1 hour ago
    )
    db_session.add(expired_session)
    await db_session.commit()

    response = await client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 401
    assert "expired" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_rate_limiting_register(client: AsyncClient):
    """Registration is rate limited to 5/minute."""
    # Make 6 rapid requests
    for i in range(6):
        response = await client.post(
            "/api/auth/register",
            json={"email": f"test{i}@example.com", "password": "password123"}
        )

        if i < 5:
            assert response.status_code in [201, 422]  # Success or validation error
        else:
            assert response.status_code == 429  # Too Many Requests


@pytest.mark.asyncio
async def test_rate_limiting_login(client: AsyncClient, test_user: User):
    """Login is rate limited to 5/minute."""
    # Make 6 rapid requests
    for i in range(6):
        response = await client.post(
            "/api/auth/login",
            json={"email": test_user.email, "password": "testpassword"}
        )

        if i < 5:
            assert response.status_code in [200, 401]  # Success or auth error
        else:
            assert response.status_code == 429  # Too Many Requests
```

**Test Fixtures** (add to `tests/conftest.py`):

```python
import pytest
from httpx import AsyncClient
from datetime import datetime, timedelta

from app.main import app
from app.db.models import User, Session
from app.core.security import hash_password, generate_session_token, hash_token


@pytest.fixture
async def client():
    """Async HTTP client for testing."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client


@pytest.fixture
async def test_user(db_session: AsyncSession) -> User:
    """Create test user."""
    user = User(
        email="test@example.com",
        password_hash=hash_password("testpassword")
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def test_session(db_session: AsyncSession, test_user: User) -> tuple[Session, str]:
    """Create test session and return session + raw token."""
    token = generate_session_token()
    token_hash = hash_token(token)

    session = Session(
        user_id=test_user.id,
        token_hash=token_hash,
        expires_at=datetime.utcnow() + timedelta(days=7)
    )
    db_session.add(session)
    await db_session.commit()
    await db_session.refresh(session)

    return session


@pytest.fixture
async def test_token(test_session: Session) -> str:
    """Return raw token for test session."""
    token = generate_session_token()
    # Note: This needs to be the same token used in test_session
    # Better approach: return both from test_session fixture
    return token
```

**Better Fixture Approach:**

```python
@pytest.fixture
async def test_auth(db_session: AsyncSession, test_user: User) -> dict:
    """Create test session and return user, session, and token."""
    token = generate_session_token()
    token_hash = hash_token(token)

    session = Session(
        user_id=test_user.id,
        token_hash=token_hash,
        expires_at=datetime.utcnow() + timedelta(days=7)
    )
    db_session.add(session)
    await db_session.commit()
    await db_session.refresh(session)

    return {
        "user": test_user,
        "session": session,
        "token": token
    }
```

---

### PR #4 Completion Checklist

- [ ] `app/api/routes/auth.py` implemented with all endpoints
- [ ] `app/dependencies.py` with `get_current_user()` dependency
- [ ] SlowAPI rate limiting configured in `main.py`
- [ ] Router added to `main.py`
- [ ] `tests/integration/test_auth_endpoints.py` written
- [ ] Test fixtures added to `conftest.py`
- [ ] Run `pytest tests/integration/test_auth_endpoints.py -v`
- [ ] Test manually via Swagger UI (`/docs`)
- [ ] Verify all endpoints work correctly
- [ ] Run coverage: `pytest tests/ --cov=app`
- [ ] Verify overall coverage > 80%
- [ ] No linting errors: `ruff check app/`
- [ ] Code formatted: `black app/`
- [ ] Create branch: `git checkout -b feat/phase-3-auth-api`
- [ ] Commit changes
- [ ] Push to remote
- [ ] Create PR #4 via `gh pr create`
- [ ] Update HANDOFF.md: Mark 3.4, 3.5, 3.6 as complete

---

## Testing Strategy

### Unit Tests (PR #3)
- **Scope:** Individual functions/methods
- **Mocking:** Mock database repositories, external dependencies
- **Speed:** Fast (no database)
- **Coverage Target:** > 80% for security.py and auth_service.py

### Integration Tests (PR #4)
- **Scope:** Full request/response cycle
- **Database:** Real test database (separate from dev)
- **Speed:** Slower (database operations)
- **Coverage Target:** All endpoints, auth flows, error cases

---

## Dependencies to Install

Add to `requirements.txt` or `pyproject.toml`:

```txt
# Password hashing
bcrypt>=4.0.0
# OR
passlib[bcrypt]>=1.7.4

# Rate limiting
slowapi>=0.1.9

# Email validation (if not already present)
pydantic[email]>=2.0.0
```

Install:
```bash
pip install bcrypt slowapi pydantic[email]
```

---

## Common Issues & Solutions

### Issue 1: Bcrypt hash verification fails
**Symptom:** `verify_password()` returns False for correct password
**Cause:** Password stored as bytes instead of string
**Solution:** Ensure bcrypt returns string: `hash_password().decode('utf-8')` if using `bcrypt.hashpw()`

### Issue 2: Rate limiting doesn't work
**Symptom:** Can make unlimited requests
**Cause:** SlowAPI not configured in main.py
**Solution:** Add limiter state and exception handler to FastAPI app

### Issue 3: Integration tests fail with "event loop closed"
**Symptom:** AsyncIO errors in pytest
**Cause:** Multiple event loops created
**Solution:** Ensure `pytest-asyncio` is installed and `asyncio_mode = "auto"` in pytest config

### Issue 4: 401 on valid token
**Symptom:** `get_current_user()` raises 401 for valid token
**Cause:** Token not properly extracted from header
**Solution:** Verify `authorization.replace("Bearer ", "")` removes prefix correctly

---

## Documentation Updates

### After PR #3 Merged:
- Update HANDOFF.md: Mark 3.1-3.3 complete
- Update STARTER.md: Add note about security utilities

### After PR #4 Merged:
- Update HANDOFF.md: Mark 3.4-3.6 complete
- Update STARTER.md: Add auth endpoints to API section
- Update README.md: Add auth flow documentation

---

## Next Steps After Phase 3

Once Phase 3 is complete:
1. Merge both PRs to main
2. Verify all tests pass on main branch
3. Update project documentation
4. Begin Phase 4: Transcript Ingestion Pipeline

**Phase 4 will use:**
- `get_current_user()` dependency for protected endpoints
- Authentication system for user-specific data isolation
- Session validation for WebSocket connections (Phase 7)

---

## Summary

**Phase 3 Deliverables:**
- ✅ Secure password hashing with bcrypt
- ✅ Session-based authentication (7-day expiry)
- ✅ Token generation and validation
- ✅ Rate-limited auth endpoints (5/min)
- ✅ Full test coverage (unit + integration)
- ✅ Protected endpoint dependency (`get_current_user`)

**PRs:**
- PR #3: Core logic (security, service, schemas)
- PR #4: API layer (endpoints, dependency, tests)

**Ready for Phase 4!** 🎉
