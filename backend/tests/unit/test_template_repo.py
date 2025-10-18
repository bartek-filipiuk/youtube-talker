"""
Unit Tests for TemplateRepository
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import User
from app.db.repositories.template_repo import TemplateRepository


@pytest.mark.asyncio
async def test_create_template(db_session: AsyncSession, test_user: User):
    """Test creating a new template."""
    repo = TemplateRepository(db_session)
    template = await repo.create_template(
        user_id=test_user.id,
        template_type="linkedin",
        template_name="My Custom Template",
        template_content="Custom template: {title}",
        variables=["title"],
        is_default=False,
    )

    assert template.id is not None
    assert template.user_id == test_user.id
    assert template.template_type == "linkedin"
    assert template.template_name == "My Custom Template"
    assert template.template_content == "Custom template: {title}"
    assert template.variables == ["title"]
    assert template.is_default is False


@pytest.mark.asyncio
async def test_get_custom_template(db_session: AsyncSession, test_user: User):
    """Test retrieving a custom user template."""
    repo = TemplateRepository(db_session)

    # Create custom template
    await repo.create_template(
        user_id=test_user.id,
        template_type="linkedin",
        template_name="Custom",
        template_content="Custom: {title}",
        variables=["title"],
    )

    # Get template
    template = await repo.get_template(test_user.id, "linkedin")

    assert template is not None
    assert template.template_content == "Custom: {title}"
    assert template.template_name == "Custom"


@pytest.mark.asyncio
async def test_get_default_template_fallback(
    db_session: AsyncSession, test_user: User
):
    """Test fallback to default template when no custom template exists."""
    repo = TemplateRepository(db_session)

    # Create default template (user_id = None)
    await repo.create_template(
        user_id=None,
        template_type="linkedin",
        template_name="Default LinkedIn",
        template_content="Default: {title}",
        variables=["title"],
        is_default=True,
    )

    # Get template (should return default since no custom exists)
    template = await repo.get_template(test_user.id, "linkedin")

    assert template is not None
    assert template.template_content == "Default: {title}"
    assert template.user_id is None
    assert template.is_default is True


@pytest.mark.asyncio
async def test_custom_template_overrides_default(
    db_session: AsyncSession, test_user: User
):
    """Test that custom template is returned over default."""
    repo = TemplateRepository(db_session)

    # Create default template
    await repo.create_template(
        user_id=None,
        template_type="linkedin",
        template_name="Default",
        template_content="Default: {title}",
        variables=["title"],
        is_default=True,
    )

    # Create custom template
    await repo.create_template(
        user_id=test_user.id,
        template_type="linkedin",
        template_name="Custom",
        template_content="Custom: {title}",
        variables=["title"],
    )

    # Get template (should return custom)
    template = await repo.get_template(test_user.id, "linkedin")

    assert template is not None
    assert template.template_content == "Custom: {title}"
    assert template.user_id == test_user.id


@pytest.mark.asyncio
async def test_get_template_not_found(db_session: AsyncSession, test_user: User):
    """Test retrieving non-existent template returns None."""
    repo = TemplateRepository(db_session)
    template = await repo.get_template(test_user.id, "nonexistent_type")

    assert template is None


@pytest.mark.asyncio
async def test_delete_template(db_session: AsyncSession, test_user: User):
    """Test deleting a template."""
    repo = TemplateRepository(db_session)

    # Create template
    template = await repo.create_template(
        user_id=test_user.id,
        template_type="email",
        template_name="Test",
        template_content="Test",
        variables=[],
    )

    # Delete template
    result = await repo.delete(template.id)
    assert result is True

    # Verify deleted
    deleted_template = await repo.get_by_id(template.id)
    assert deleted_template is None
