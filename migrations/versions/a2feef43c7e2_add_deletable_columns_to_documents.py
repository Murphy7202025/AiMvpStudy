"""add_deletable_columns_to_documents

Revision ID: a2feef43c7e2
Revises: 0171067fc425
Create Date: 2026-04-11 21:52:18.699528

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a2feef43c7e2'
down_revision: Union[str, Sequence[str], None] = '0171067fc425'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
