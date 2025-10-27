"""add_user_role_and_transcript_count

Revision ID: 1a95e025e49d
Revises: 2b4a2190f4a6
Create Date: 2025-10-27 20:23:02.972738

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1a95e025e49d'
down_revision: Union[str, Sequence[str], None] = '2b4a2190f4a6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create user_role enum type
    user_role_enum = sa.Enum('user', 'admin', name='user_role', create_type=True)
    user_role_enum.create(op.get_bind(), checkfirst=True)

    # Add role column with default 'user'
    op.add_column('users', sa.Column('role', sa.Enum('user', 'admin', name='user_role'),
                                      nullable=False, server_default='user'))

    # Add transcript_count column with default 0
    op.add_column('users', sa.Column('transcript_count', sa.Integer(),
                                      nullable=False, server_default='0'))

    # Create index on role column for faster role-based queries
    op.create_index('idx_users_role', 'users', ['role'])


def downgrade() -> None:
    """Downgrade schema."""
    # Drop index
    op.drop_index('idx_users_role', table_name='users')

    # Drop columns
    op.drop_column('users', 'transcript_count')
    op.drop_column('users', 'role')

    # Drop enum type
    sa.Enum(name='user_role').drop(op.get_bind(), checkfirst=True)
