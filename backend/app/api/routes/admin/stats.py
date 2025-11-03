"""
Admin Stats API Endpoint

Admin-only endpoint for dashboard statistics.
"""

from fastapi import APIRouter, Depends, Request
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.db.models import User
from app.dependencies import get_admin_user
from app.schemas.admin import AdminStatsResponse
from app.services.admin_service import AdminService

# Rate limiter configuration
limiter = Limiter(key_func=get_remote_address)

# Create router
router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/stats", response_model=AdminStatsResponse)
@limiter.limit("60/minute")
async def get_admin_stats(
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_user),
) -> AdminStatsResponse:
    """
    Get admin dashboard statistics (admin only).

    Returns counts for:
    - Total channels (all)
    - Active channels (not soft-deleted)
    - Total videos across all channels

    Rate limit: 60/minute

    Args:
        request: FastAPI request (for rate limiting)
        db: Database session
        admin: Authenticated admin user

    Returns:
        AdminStatsResponse: Dashboard statistics

    Raises:
        HTTPException 403: Non-admin access
    """
    service = AdminService(db)
    stats = await service.get_stats()

    return AdminStatsResponse(
        total_channels=stats["total_channels"],
        active_channels=stats["active_channels"],
        total_videos=stats["total_videos"],
    )
