"""rename property_transactions.date to transaction_date

Revision ID: 0007
Revises: 0006
Create Date: 2026-05-11

Migration 0004 was edited in-place after being applied to the local dev DB,
so the column remained 'date' on disk while the ORM expected 'transaction_date'.
On fresh databases (CI) 0004 already creates the column as 'transaction_date',
so this migration is a no-op there. On existing DBs with the old name it
performs the rename.
"""

from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'property_transactions' AND column_name = 'date'
            ) THEN
                ALTER TABLE property_transactions RENAME COLUMN date TO transaction_date;
            END IF;
        END $$;
    """)


def downgrade() -> None:
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'property_transactions' AND column_name = 'transaction_date'
            ) THEN
                ALTER TABLE property_transactions RENAME COLUMN transaction_date TO date;
            END IF;
        END $$;
    """)
