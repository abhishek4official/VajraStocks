"""add_conversation_tables

Revision ID: 41a74077c957
Revises: e5f6a7b8c9d0
Create Date: 2026-06-20 00:37:28.095300

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '41a74077c957'
down_revision: Union[str, Sequence[str], None] = 'e5f6a7b8c9d0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'conversation_threads',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('agent_type', sa.String(length=50), nullable=False),
        sa.Column('title', sa.String(length=200), nullable=False),
        sa.Column('message_count', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('last_active_at', sa.DateTime(), nullable=False),
        sa.Column('is_archived', sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('conversation_threads') as batch_op:
        batch_op.create_index('ix_conv_threads_agent_active', ['agent_type', 'last_active_at'], unique=False)
        batch_op.create_index('ix_conversation_threads_agent_type', ['agent_type'], unique=False)

    op.create_table(
        'conversation_messages',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('thread_id', sa.String(length=36), nullable=False),
        sa.Column('role', sa.String(length=10), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('recommendation', sa.String(length=20), nullable=True),
        sa.Column('confidence', sa.String(length=10), nullable=True),
        sa.Column('annotation', sa.Text(), nullable=True),
        sa.Column('is_summarized', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['thread_id'], ['conversation_threads.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('conversation_messages') as batch_op:
        batch_op.create_index('ix_conv_messages_thread_created', ['thread_id', 'created_at'], unique=False)

    op.create_table(
        'conversation_summaries',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('thread_id', sa.String(length=36), nullable=False),
        sa.Column('summary_text', sa.Text(), nullable=False),
        sa.Column('covers_message_ids', sa.JSON(), nullable=True),
        sa.Column('key_tickers', sa.JSON(), nullable=True),
        sa.Column('key_decisions', sa.JSON(), nullable=True),
        sa.Column('generated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['thread_id'], ['conversation_threads.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade() -> None:
    op.drop_table('conversation_summaries')
    with op.batch_alter_table('conversation_messages') as batch_op:
        batch_op.drop_index('ix_conv_messages_thread_created')
    op.drop_table('conversation_messages')
    with op.batch_alter_table('conversation_threads') as batch_op:
        batch_op.drop_index('ix_conversation_threads_agent_type')
        batch_op.drop_index('ix_conv_threads_agent_active')
    op.drop_table('conversation_threads')
