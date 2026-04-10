"""fix_vector_index_cosine

Revision ID: fe728ebe9110
Revises: aaf9e70397ba
Create Date: 2026-04-10 12:13:21.641918

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'fe728ebe9110'
down_revision: Union[str, Sequence[str], None] = 'aaf9e70397ba'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    # 删除旧的 L2 索引
    op.drop_index("idx_docs_vec", table_name="documents")
    # 创建正确的余弦距离索引
    op.execute(
        'CREATE INDEX idx_docs_vec ON documents USING hnsw (embedding vector_cosine_ops)'
    )


def downgrade():
    op.drop_index("idx_docs_vec", table_name="documents")
    op.execute(
        'CREATE INDEX idx_docs_vec ON documents USING hnsw (embedding vector_l2_ops)'
    )
