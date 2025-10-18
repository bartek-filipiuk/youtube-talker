"""Remove template_type constraint for MVP extensibility

Revision ID: 9660aa8618fd
Revises: fcd6e385eb69
Create Date: 2025-10-18 06:28:52.819187

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9660aa8618fd'
down_revision: Union[str, Sequence[str], None] = 'fcd6e385eb69'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Remove template_type CHECK constraint to allow flexible content types.

    For MVP, only 'linkedin' is supported, but validation is moved to application
    layer (Pydantic) to allow easy addition of new types post-MVP without migrations.
    """
    # Drop the template_type CHECK constraint
    op.drop_constraint(
        constraint_name='check_template_type',
        table_name='templates',
        type_='check'
    )


def downgrade() -> None:
    """
    Re-add template_type CHECK constraint (for rollback only).

    Note: This adds back the original constraint with 4 types.
    If you've added custom types, this migration may fail.
    """
    # Re-add the template_type CHECK constraint
    op.create_check_constraint(
        constraint_name='check_template_type',
        table_name='templates',
        condition="template_type IN ('linkedin', 'twitter', 'blog', 'email')"
    )
