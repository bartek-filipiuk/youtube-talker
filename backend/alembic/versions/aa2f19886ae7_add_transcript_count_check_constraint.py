"""add_transcript_count_check_constraint

Add CHECK constraint to users table to prevent transcript_count from exceeding limit.
Prevents race conditions where concurrent requests could cause count > 10 for regular users.

Revision ID: aa2f19886ae7
Revises: 4e67c9eefea6
Create Date: 2025-11-01 07:47:49.360528

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'aa2f19886ae7'
down_revision: Union[str, Sequence[str], None] = '4e67c9eefea6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add CHECK constraint to prevent transcript_count exceeding 10 for regular users."""
    op.create_check_constraint(
        "check_user_transcript_limit",
        "users",
        "role = 'admin' OR transcript_count <= 10"
    )


def downgrade() -> None:
    """Remove CHECK constraint."""
    op.drop_constraint("check_user_transcript_limit", "users", type_="check")
