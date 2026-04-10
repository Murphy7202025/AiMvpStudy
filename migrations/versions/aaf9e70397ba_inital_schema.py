"""inital_schema

Revision ID: aaf9e70397ba
Revises: 
Create Date: 2026-04-08 22:07:04.085758

"""
from typing import Union, Sequence

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector  # 确保导入，用于处理向量字段

# 唯一标识符
revision: str = 'aaf9e70397ba'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    # --- [1. 基础设施层] ---
    op.execute('CREATE EXTENSION IF NOT EXISTS vector')

    # --- [2. 业务配置层] ---
    op.create_table(
        "system_configs",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("key", sa.Unicode(255), unique=True, nullable=False),
        sa.Column("value", sa.Text, nullable=False),
        sa.Column("description", sa.Unicode(500)),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now(), nullable=False),
    )

    # --- [3. 核心业务层] ---
    # 在这里定义你真正的 AI 模型数据表
    op.create_table(
        "documents",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),

        # --- 在这里添加你的自定义字段 ---
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("meta_data", sa.JSON, nullable=True),  # 比如存储来源 URL 等

        # 向量字段：维度需与你选用的 Embedding 模型一致 (Gemini 是 768)
        sa.Column("embedding", Vector(768), nullable=True),

        sa.Column("created_at", sa.DateTime, server_default=sa.func.now(), nullable=False),
    )

    # --- [4. 索引优化层] ---
    op.create_index("idx_configs_key", "system_configs", ["key"])

    # 特别地：为向量字段创建 HNSW 索引以支持高性能 RAG 检索
    op.execute(
        'CREATE INDEX idx_docs_vec ON documents USING hnsw (embedding vector_l2_ops)'
    )


def downgrade():
    op.drop_index("idx_docs_vec", table_name="documents")
    op.drop_table("documents")
    op.drop_table("system_configs")
