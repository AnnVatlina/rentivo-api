"""add compound interest to deposits

Revision ID: 0002
Revises: a1a38c84507b
Create Date: 2026-05-11
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "a1a38c84507b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("deposits", sa.Column("interest_type", sa.String(20), nullable=False, server_default="simple"))
    op.add_column("deposits", sa.Column("compound_frequency", sa.String(20), nullable=True))


def downgrade() -> None:
    op.drop_column("deposits", "compound_frequency")
    op.drop_column("deposits", "interest_type")
