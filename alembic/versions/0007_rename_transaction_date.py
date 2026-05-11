"""rename property_transactions.date to transaction_date

Revision ID: 0007
Revises: 0006
Create Date: 2026-05-11

The column was named 'date' in the initial migration but later renamed in
the model to avoid a Python namespace conflict with datetime.date in
Pydantic v2. This migration brings the schema in sync with the ORM.
"""

from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("property_transactions", "date", new_column_name="transaction_date")


def downgrade() -> None:
    op.alter_column("property_transactions", "transaction_date", new_column_name="date")
