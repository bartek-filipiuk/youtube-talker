"""
Admin API Routes

Admin-only routes for system management.
"""

from app.api.routes.admin.channels import router as channels_router
from app.api.routes.admin.settings import router as settings_router
from app.api.routes.admin.stats import router as stats_router
from app.api.routes.admin.users import router as users_router

__all__ = ["channels_router", "settings_router", "stats_router", "users_router"]
