"""
Health Check Endpoints

Provides service health status for monitoring and orchestration.
Used by load balancers, monitoring tools, and deployment scripts.
"""

from loguru import logger
from typing import Dict, Any

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.services.qdrant_service import QdrantService


router = APIRouter(tags=["health"])


@router.get("/api/health")
async def health_check() -> Dict[str, str]:
    """
    Basic health check endpoint.

    Returns 200 OK if service is running.
    Used by load balancers and orchestration tools.

    Returns:
        {"status": "ok"}

    Example:
        curl http://localhost:8000/api/health
    """
    return {"status": "ok"}


@router.get("/api/health/db")
async def health_check_db(db: AsyncSession = Depends(get_db)) -> JSONResponse:
    """
    Database health check endpoint.

    Tests PostgreSQL connectivity by executing a simple query.
    Returns 200 OK if connection succeeds, 503 Service Unavailable if fails.

    Args:
        db: Database session (injected via Depends)

    Returns:
        200: {"status": "healthy", "service": "postgresql"}
        503: {"status": "unhealthy", "service": "postgresql", "error": "..."}

    Example:
        curl http://localhost:8000/api/health/db
    """
    try:
        # Execute simple query to verify connection
        await db.execute(text("SELECT 1"))
        logger.debug("Database health check passed")
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={"status": "healthy", "service": "postgresql"}
        )
    except Exception as e:
        logger.error(f"Database health check failed: {e}", exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "unhealthy",
                "service": "postgresql",
                "error": str(e)
            }
        )


@router.get("/api/health/qdrant")
async def health_check_qdrant() -> JSONResponse:
    """
    Qdrant vector store health check endpoint.

    Tests Qdrant connectivity using QdrantService health check.
    Returns 200 OK if connection succeeds, 503 Service Unavailable if fails.

    Returns:
        200: {"status": "healthy", "service": "qdrant"}
        503: {"status": "unhealthy", "service": "qdrant", "error": "..."}

    Example:
        curl http://localhost:8000/api/health/qdrant
    """
    try:
        qdrant_service = QdrantService()
        is_healthy = await qdrant_service.health_check()

        if is_healthy:
            logger.debug("Qdrant health check passed")
            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content={"status": "healthy", "service": "qdrant"}
            )
        else:
            logger.warning("Qdrant health check failed: connection unsuccessful")
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content={
                    "status": "unhealthy",
                    "service": "qdrant",
                    "error": "Connection unsuccessful"
                }
            )
    except Exception as e:
        logger.error(f"Qdrant health check failed: {e}", exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "unhealthy",
                "service": "qdrant",
                "error": str(e)
            }
        )
