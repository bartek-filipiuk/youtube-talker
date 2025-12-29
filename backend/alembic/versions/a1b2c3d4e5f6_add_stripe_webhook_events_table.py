"""add_stripe_webhook_events_table

Revision ID: a1b2c3d4e5f6
Revises: 526b978706b1
Create Date: 2025-12-29 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '526b978706b1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create stripe_webhook_events table for idempotency."""
    op.create_table(
        'stripe_webhook_events',
        sa.Column('id', sa.String(length=255), nullable=False, comment='Stripe event ID (evt_xxx)'),
        sa.Column('event_type', sa.String(length=100), nullable=False, comment='Stripe event type'),
        sa.Column('processed_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False, comment='When the event was processed'),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    """Drop stripe_webhook_events table."""
    op.drop_table('stripe_webhook_events')
