"""add_chat_sessions_and_messages

Revision ID: 0171067fc425
Revises: 5693d6dc1907
Create Date: 2026-04-11 13:05:11.653833

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0171067fc425'
down_revision: Union[str, Sequence[str], None] = '5693d6dc1907'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    # [1] 创建会话主表 (Chat Sessions)
    op.create_table(
        'chat_sessions',
        sa.Column('id', sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column('title', sa.VARCHAR(255), nullable=True, comment="会话标题，可由AI自动总结或用户自定义"),
        sa.Column('created_at', sa.DateTime, nullable=True),
        sa.Column('created_by', sa.Unicode(100), nullable=True),
        sa.Column('updated_at', sa.DateTime, nullable=True),
        sa.Column('updated_by', sa.Unicode(100), nullable=True),
    )
    # 高频查询与排序字段索引
    op.create_index('idx_chat_sessions_id', 'chat_sessions', ['id'])
    op.create_index('idx_chat_sessions_created_at', 'chat_sessions', ['created_at'])

    # [2] 创建消息子表 (Chat Messages)
    op.create_table(
        'chat_messages',
        sa.Column('id', sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column('session_id', sa.BigInteger, sa.ForeignKey('chat_sessions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('role', sa.VARCHAR(50), nullable=False, comment="枚举值: user, model, system"),
        sa.Column('content', sa.Text, nullable=False),
        sa.Column('token_count', sa.Integer, nullable=True, comment="当前消息消耗的 Token 数量"),
        sa.Column('deleted_by', sa.Unicode(100), nullable=True),
        sa.Column('deleted_at', sa.DateTime, nullable=True),
        sa.Column('created_at', sa.DateTime, nullable=True),
        sa.Column('created_by', sa.Unicode(100), nullable=True),
        sa.Column('updated_at', sa.DateTime, nullable=True),
        sa.Column('updated_by', sa.Unicode(100), nullable=True),
    )
    # 核心外键索引（必须加，否则联表查询会导致全表扫描）
    op.create_index('idx_chat_messages_session_id', 'chat_messages', ['session_id'])
    # 高频 WHERE 条件过滤索引
    op.create_index('idx_chat_messages_role', 'chat_messages', ['role'])
    # 用于获取“最近N条历史记录”的排序索引
    op.create_index('idx_chat_messages_created_at', 'chat_messages', ['created_at'])


def downgrade():
    op.drop_index('idx_chat_messages_created_at', table_name='chat_messages')
    op.drop_index('idx_chat_messages_role', table_name='chat_messages')
    op.drop_index('idx_chat_messages_session_id', table_name='chat_messages')
    op.drop_table('chat_messages')

    op.drop_index('idx_chat_sessions_created_at', table_name='chat_sessions')
    op.drop_index('idx_chat_sessions_id', table_name='chat_sessions')
    op.drop_table('chat_sessions')
