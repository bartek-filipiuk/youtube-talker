"""make_user_id_nullable_in_chunks

Revision ID: 4c2e2e27e7d0
Revises: 1befb8317517
Create Date: 2025-11-03 14:33:13.611629

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4c2e2e27e7d0'
down_revision: Union[str, Sequence[str], None] = '1befb8317517'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Make user_id column nullable in chunks table.

    This is required for channel chunks which have channel_id but no user_id.
    The check_chunk_ownership constraint requires exactly one of user_id or channel_id,
    so user_id must be nullable for channel chunks.
    """
    op.alter_column('chunks', 'user_id',
                    existing_type=sa.UUID(),
                    nullable=True)


def downgrade() -> None:
    """
    Revert user_id column to NOT NULL in chunks table.

    WARNING: This will fail if any channel chunks exist (user_id IS NULL).
    """
    # First, we need to handle existing NULL values
    # Option 1: Delete all channel chunks (user_id IS NULL AND channel_id IS NOT NULL)
    # Option 2: Set a default user_id (not ideal)
    # For safety, this migration will fail if channel chunks exist

    op.alter_column('chunks', 'user_id',
                    existing_type=sa.UUID(),
                    nullable=False)
