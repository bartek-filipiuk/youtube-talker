"""
Transcript API Endpoints

Provides REST endpoints for transcript ingestion and management.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import TranscriptAlreadyExistsError, InvalidInputError
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
        AuthenticationError: User not authenticated (401)
        TranscriptAlreadyExistsError: Transcript already exists for this video (409)
        InvalidInputError: Invalid YouTube URL format (400)
        RateLimitExceededError: Rate limit exceeded (429)
        ExternalAPIError: SUPADATA API error or external service failure (503)
        Exception: Unexpected server errors handled by global handler (500)

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


@router.delete("/{transcript_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("20/minute")
async def delete_transcript(
    request: Request,
    transcript_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    """
    Delete a transcript and all associated data.

    Full deletion pipeline:
        1. Verify transcript exists and user owns it
        2. Get all chunk IDs for this transcript
        3. Delete vectors from Qdrant (best-effort)
        4. Delete transcript from PostgreSQL (cascades to chunks)
        5. Decrement user's transcript_count

    Rate limit: 20 requests per minute per IP.

    Args:
        request: FastAPI request (for rate limiting)
        transcript_id: UUID of transcript to delete
        db: Database session
        user: Current authenticated user

    Returns:
        None (204 No Content on success)

    Raises:
        AuthenticationError: User not authenticated (401)
        HTTPException: Transcript not found or access denied (404/403)
        RateLimitExceededError: Rate limit exceeded (429)
        Exception: Unexpected server errors handled by global handler (500)

    Example:
        >>> DELETE /api/transcripts/550e8400-e29b-41d4-a716-446655440000
        >>> Headers: {"Authorization": "Bearer <token>"}
        >>> Response: 204 No Content
    """
    service = TranscriptService()

    try:
        await service.delete_transcript(
            transcript_id=str(transcript_id),
            user_id=str(user.id),
            db_session=db,
        )
    except ValueError as e:
        # Transcript not found or user doesn't own it
        error_msg = str(e)
        if "not found" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Transcript {transcript_id} not found",
            )
        elif "does not own" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to delete this transcript",
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_msg,
            )
