"""make_conversation_id_nullable

Revision ID: cd7cc3eddba3
Revises: 4c2e2e27e7d0
Create Date: 2025-11-03 17:14:02.901019

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


# revision identifiers, used by Alembic.
revision: str = 'cd7cc3eddba3'
down_revision: Union[str, Sequence[str], None] = '4c2e2e27e7d0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Make conversation_id column nullable in messages table.

    This allows messages to belong to either personal conversations OR channel conversations,
    enforced by the existing check_message_conversation_type constraint.
    """
    op.alter_column(
        'messages',
        'conversation_id',
        existing_type=UUID(as_uuid=True),
        nullable=True
    )


def downgrade() -> None:
    """
    Make conversation_id column NOT NULL again.

    WARNING: This will fail if there are any messages with NULL conversation_id
    (i.e., channel conversation messages).
    """
    op.alter_column(
        'messages',
        'conversation_id',
        existing_type=UUID(as_uuid=True),
        nullable=False
    )
