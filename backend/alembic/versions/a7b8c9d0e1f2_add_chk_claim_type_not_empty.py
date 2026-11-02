"""add_chk_claim_type_not_empty - Enforce non-empty claim_type at database level.

Revision ID: a7b8c9d0e1f2
Revises: f6a7b8c9d0e1
Create Date: 2026-11-02 07:15:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'a7b8c9d0e1f2'
down_revision = 'f6a7b8c9d0e1'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add check constraint ensuring claim_type is not empty or whitespace-only
    op.create_check_constraint(
        'chk_claim_type_not_empty',
        'claims',
        "length(trim(claim_type)) > 0"
    )


def downgrade() -> None:
    op.drop_constraint('chk_claim_type_not_empty', 'claims', type_='check')

