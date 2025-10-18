"""
Template Repository

Database operations for Template model.
"""

from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Template
from app.db.repositories.base import BaseRepository


class TemplateRepository(BaseRepository[Template]):
    """Repository for Template model operations."""

    def __init__(self, session: AsyncSession):
        super().__init__(Template, session)

    async def get_template(
        self, user_id: UUID, template_type: str
    ) -> Optional[Template]:
        """
        Get template for a user, with fallback to default template.

        Looks for user-specific template first, then falls back to default.

        Args:
            user_id: User's UUID
            template_type: Type of template ('linkedin', 'twitter', etc.)

        Returns:
            Template instance or None if not found
        """
        # First try user-specific template
        result = await self.session.execute(
            select(Template).where(
                Template.user_id == user_id, Template.template_type == template_type
            )
        )
        template = result.scalar_one_or_none()

        if template:
            return template

        # Fall back to default template
        result = await self.session.execute(
            select(Template).where(
                Template.user_id.is_(None),
                Template.template_type == template_type,
                Template.is_default == True,
            )
        )
        return result.scalar_one_or_none()

    async def create_template(
        self,
        user_id: Optional[UUID],
        template_type: str,
        template_name: str,
        template_content: str,
        variables: list,
        is_default: bool = False,
    ) -> Template:
        """
        Create a new template.

        Args:
            user_id: User's UUID (None for system templates)
            template_type: Type of template
            template_name: Template name
            template_content: Jinja2 template content
            variables: List of variable names
            is_default: Whether this is a default template

        Returns:
            Created Template instance
        """
        return await super().create(
            user_id=user_id,
            template_type=template_type,
            template_name=template_name,
            template_content=template_content,
            variables=variables,
            is_default=is_default,
        )
