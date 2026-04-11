"""inital_tables

Revision ID: 5693d6dc1907
Revises: 
Create Date: 2026-04-10 22:06:57.243973

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector


# revision identifiers, used by Alembic.
revision: str = '5693d6dc1907'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    # [1] 基础设施
    op.execute('CREATE EXTENSION IF NOT EXISTS vector')

    # [2] 业务配置表
    op.create_table(
        'system_configs',
        sa.Column('id', sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column('key', sa.Unicode(255), unique=True, nullable=False),
        sa.Column('value', sa.Text, nullable=False),
        sa.Column('description', sa.Unicode(500), nullable=True),
        sa.Column('created_at', sa.DateTime, nullable=True),
        sa.Column('created_by', sa.Unicode(100), nullable=True),
        sa.Column('updated_at', sa.DateTime, nullable=True),
        sa.Column('updated_by', sa.Unicode(100), nullable=True),
    )
    op.create_index('idx_system_configs_id', 'system_configs', ['id'])
    op.create_index('idx_system_configs_key', 'system_configs', ['key'])
    op.create_index('idx_system_configs_created_at', 'system_configs', ['created_at'])

    # [3] 文档主表（元数据）
    op.create_table(
        'documents',
        sa.Column('id', sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column('title', sa.VARCHAR(255), nullable=True),
        sa.Column('source', sa.VARCHAR(500), nullable=True),
        sa.Column('created_at', sa.DateTime, nullable=True),
        sa.Column('created_by', sa.Unicode(100), nullable=True),
        sa.Column('updated_at', sa.DateTime, nullable=True),
        sa.Column('updated_by', sa.Unicode(100), nullable=True),
    )
    op.create_index('idx_documents_id', 'documents', ['id'])
    op.create_index('idx_documents_created_at', 'documents', ['created_at'])

    # [4] 文档分块表（内容 + 向量）
    op.create_table(
        'document_chunks',
        sa.Column('id', sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column('document_id', sa.BigInteger,
                  sa.ForeignKey('documents.id', ondelete='CASCADE'),
                  nullable=False),
        sa.Column('content', sa.Text, nullable=False),
        # 新增字段：用于记录分块的文本长度，方便后续统计和调优
        sa.Column('content_length', sa.Integer, nullable=True),
        sa.Column('chunk_index', sa.Integer, nullable=False),
        sa.Column('embedding', Vector(768), nullable=True),
        sa.Column('created_at', sa.DateTime, nullable=True),
        sa.Column('created_by', sa.Unicode(100), nullable=True),
        sa.Column('updated_at', sa.DateTime, nullable=True),
        sa.Column('updated_by', sa.Unicode(100), nullable=True),
    )
    op.create_index('idx_document_chunks_id', 'document_chunks', ['id'])
    op.create_index('idx_document_chunks_document_id', 'document_chunks', ['document_id'])
    op.create_index('idx_document_chunks_created_at', 'document_chunks', ['created_at'])
    op.create_index('idx_document_chunks_content_length', 'document_chunks', ['content_length'])

    # [5] 向量索引（针对余弦距离优化）
    op.execute(
        'CREATE INDEX idx_chunks_embedding ON document_chunks '
        'USING hnsw (embedding vector_cosine_ops)'
    )


def downgrade():
    op.drop_index('idx_chunks_embedding', table_name='document_chunks')
    op.drop_index('idx_document_chunks_created_at', table_name='document_chunks')
    op.drop_index('idx_document_chunks_document_id', table_name='document_chunks')
    op.drop_index('idx_document_chunks_id', table_name='document_chunks')
    op.drop_index('idx_document_chunks_content_length', table_name='document_chunks')
    op.drop_table('document_chunks')

    op.drop_index('idx_documents_created_at', table_name='documents')
    op.drop_index('idx_documents_id', table_name='documents')
    op.drop_table('documents')

    op.drop_index('idx_system_configs_created_at', table_name='system_configs')
    op.drop_index('idx_system_configs_key', table_name='system_configs')
    op.drop_index('idx_system_configs_id', table_name='system_configs')
    op.drop_table('system_configs')
