"""add_channel_tables_and_modify_messages_chunks

Revision ID: 1befb8317517
Revises: aa2f19886ae7
Create Date: 2025-11-03 06:13:22.930153

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


# revision identifiers, used by Alembic.
revision: str = '1befb8317517'
down_revision: Union[str, Sequence[str], None] = 'aa2f19886ae7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Upgrade schema.

    Adds:
    - channels table for admin-managed content channels
    - channel_videos table for video-channel associations
    - channel_conversations table for per-user channel conversations
    - channel_conversation_id to messages table (nullable)
    - channel_id to chunks table (nullable)
    - CHECK constraints ensuring exactly one conversation/ownership type
    """
    # 1. Create channels table
    op.create_table(
        'channels',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('name', sa.String(100), nullable=False, unique=True, comment='Immutable URL slug'),
        sa.Column('display_title', sa.String(255), nullable=False),
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('qdrant_collection_name', sa.String(100), nullable=False, comment='Sanitized collection name'),
        sa.Column('is_active', sa.Boolean, nullable=False, server_default=sa.text('TRUE')),
        sa.Column('created_by', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()'))
    )

    # Create indexes on channels
    op.create_index('idx_channels_name', 'channels', ['name'], unique=True)
    op.create_index('idx_channels_is_active', 'channels', ['is_active'])
    op.create_index('idx_channels_qdrant_collection', 'channels', ['qdrant_collection_name'])

    # 2. Create channel_videos table
    op.create_table(
        'channel_videos',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('channel_id', UUID(as_uuid=True), sa.ForeignKey('channels.id', ondelete='CASCADE'), nullable=False),
        sa.Column('transcript_id', UUID(as_uuid=True), sa.ForeignKey('transcripts.id', ondelete='CASCADE'), nullable=False),
        sa.Column('added_by', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('added_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()'))
    )

    # Create unique constraint on channel_id + transcript_id
    op.create_unique_constraint('uq_channel_video', 'channel_videos', ['channel_id', 'transcript_id'])

    # 3. Create channel_conversations table
    op.create_table(
        'channel_conversations',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('channel_id', UUID(as_uuid=True), sa.ForeignKey('channels.id', ondelete='CASCADE'), nullable=False),
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()'))
    )

    # Create unique constraint and indexes on channel_conversations
    op.create_unique_constraint('uq_channel_user', 'channel_conversations', ['channel_id', 'user_id'])
    op.create_index('idx_channel_conversations_channel_user', 'channel_conversations', ['channel_id', 'user_id'])
    op.create_index('idx_channel_conversations_updated_at', 'channel_conversations', [sa.text('updated_at DESC')])

    # 4. Modify messages table - add channel_conversation_id
    op.add_column('messages', sa.Column('channel_conversation_id', UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        'fk_messages_channel_conversation',
        'messages',
        'channel_conversations',
        ['channel_conversation_id'],
        ['id'],
        ondelete='CASCADE'
    )
    op.create_index('idx_messages_channel_conversation_id', 'messages', ['channel_conversation_id'])

    # Add CHECK constraint to ensure exactly one conversation type
    op.create_check_constraint(
        'check_message_conversation_type',
        'messages',
        '(conversation_id IS NOT NULL AND channel_conversation_id IS NULL) OR '
        '(conversation_id IS NULL AND channel_conversation_id IS NOT NULL)'
    )

    # 5. Modify chunks table - add channel_id
    op.add_column('chunks', sa.Column('channel_id', UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        'fk_chunks_channel',
        'chunks',
        'channels',
        ['channel_id'],
        ['id'],
        ondelete='CASCADE'
    )
    op.create_index('idx_chunks_channel_id', 'chunks', ['channel_id'])

    # Add CHECK constraint to ensure exactly one ownership type
    op.create_check_constraint(
        'check_chunk_ownership',
        'chunks',
        '(user_id IS NOT NULL AND channel_id IS NULL) OR '
        '(user_id IS NULL AND channel_id IS NOT NULL)'
    )


def downgrade() -> None:
    """
    Downgrade schema.

    Removes all channel-related tables and columns added in upgrade.
    """
    # 1. Remove CHECK constraint and column from chunks
    op.drop_constraint('check_chunk_ownership', 'chunks', type_='check')
    op.drop_index('idx_chunks_channel_id', 'chunks')
    op.drop_constraint('fk_chunks_channel', 'chunks', type_='foreignkey')
    op.drop_column('chunks', 'channel_id')

    # 2. Remove CHECK constraint and column from messages
    op.drop_constraint('check_message_conversation_type', 'messages', type_='check')
    op.drop_index('idx_messages_channel_conversation_id', 'messages')
    op.drop_constraint('fk_messages_channel_conversation', 'messages', type_='foreignkey')
    op.drop_column('messages', 'channel_conversation_id')

    # 3. Drop channel_conversations table
    op.drop_index('idx_channel_conversations_updated_at', 'channel_conversations')
    op.drop_index('idx_channel_conversations_channel_user', 'channel_conversations')
    op.drop_constraint('uq_channel_user', 'channel_conversations', type_='unique')
    op.drop_table('channel_conversations')

    # 4. Drop channel_videos table
    op.drop_constraint('uq_channel_video', 'channel_videos', type_='unique')
    op.drop_table('channel_videos')

    # 5. Drop channels table
    op.drop_index('idx_channels_qdrant_collection', 'channels')
    op.drop_index('idx_channels_is_active', 'channels')
    op.drop_index('idx_channels_name', 'channels')
    op.drop_table('channels')
