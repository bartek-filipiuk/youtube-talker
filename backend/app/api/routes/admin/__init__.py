"""
Admin API Routes

Admin-only routes for system management.
"""

from app.api.routes.admin.channels import router as channels_router

__all__ = ["channels_router"]
