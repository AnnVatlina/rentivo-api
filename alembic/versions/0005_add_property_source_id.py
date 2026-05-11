"""add source_id to properties

Revision ID: 0005
Revises: 0004
Create Date: 2026-05-11
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("properties", sa.Column("source_id", sa.UUID(), nullable=True))
    op.create_index(op.f("ix_properties_source_id"), "properties", ["source_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_properties_source_id"), table_name="properties")
    op.drop_column("properties", "source_id")
