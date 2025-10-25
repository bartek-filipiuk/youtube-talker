"""
Transcript API Endpoints

Provides REST endpoints for transcript ingestion and management.
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import TranscriptAlreadyExistsError, InvalidInputError, ExternalAPIError
from app.db.session import get_db
from app.db.models import User
from app.dependencies import get_current_user
from app.schemas.transcript import TranscriptIngestRequest, TranscriptResponse
from app.services.transcript_service import TranscriptService

# Rate limiter configuration
limiter = Limiter(key_func=get_remote_address)

# Create router
router = APIRouter(prefix="/api/transcripts", tags=["transcripts"])


@router.post("/ingest", response_model=TranscriptResponse, status_code=201)
@limiter.limit("10/minute")
async def ingest_transcript(
    request: Request,
    body: TranscriptIngestRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> TranscriptResponse:
    """
    Ingest YouTube transcript for authenticated user.

    Full pipeline execution:
        1. Fetch transcript from SUPADATA API
        2. Check for duplicate (by youtube_video_id + user_id)
        3. Save transcript to PostgreSQL
        4. Chunk the transcript text (700 tokens, 20% overlap)
        5. Generate embeddings (OpenAI text-embedding-3-small)
        6. Save chunks to PostgreSQL
        7. Upsert vectors to Qdrant

    Rate limit: 10 requests per minute per IP.

    Args:
        request: FastAPI request (for rate limiting)
        body: Ingestion request (youtube_url)
        db: Database session
        user: Current authenticated user

    Returns:
        TranscriptResponse with ingestion results

    Raises:
        HTTPException(401): User not authenticated
        HTTPException(409): Transcript already exists for this video
        HTTPException(422): Invalid YouTube URL format
        HTTPException(429): Rate limit exceeded
        HTTPException(502): SUPADATA API error or external service failure
        HTTPException(500): Unexpected server error

    Example:
        >>> POST /api/transcripts/ingest
        >>> Headers: {"Authorization": "Bearer <token>"}
        >>> Body: {"youtube_url": "https://youtube.com/watch?v=dQw4w9WgXcQ"}
        >>> Response: {
        >>>   "id": "550e8400-e29b-41d4-a716-446655440000",
        >>>   "youtube_video_id": "dQw4w9WgXcQ",
        >>>   "chunk_count": 12,
        >>>   "metadata": {"title": "...", "duration": 213, "language": "en"}
        >>> }
    """
    service = TranscriptService()

    try:
        result = await service.ingest_transcript(
            youtube_url=body.youtube_url,
            user_id=user.id,
            db_session=db,
        )

        return TranscriptResponse(
            id=result["transcript_id"],
            youtube_video_id=result["youtube_video_id"],
            chunk_count=result["chunk_count"],
            metadata=result["metadata"],
        )

    except ValueError as e:
        # Duplicate or validation error
        error_msg = str(e)
        if "already exists" in error_msg.lower():
            raise TranscriptAlreadyExistsError()
        else:
            raise InvalidInputError(error_msg)

    except Exception as e:
        # External service error (SUPADATA, OpenAI, Qdrant)
        error_msg = str(e)
        if "httpx" in error_msg.lower() or "api" in error_msg.lower():
            raise ExternalAPIError(f"External service error: {error_msg}")
        else:
            # Unexpected server error - let global handler catch it
            raise
