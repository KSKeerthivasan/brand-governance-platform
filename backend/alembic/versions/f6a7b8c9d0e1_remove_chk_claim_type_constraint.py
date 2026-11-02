"""remove_chk_claim_type_constraint - Allow organizations to use custom claim categories
by removing the restrictive fixed chk_claim_type check constraint.

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-11-02 06:35:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'f6a7b8c9d0e1'
down_revision = 'e5f6a7b8c9d0'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Drop restrictive check constraint on claim_type
    op.drop_constraint('chk_claim_type', 'claims', type_='check')


def downgrade() -> None:
    # Check if any claims contain custom categories that violate the legacy check constraint
    bind = op.get_bind()
    custom_types = bind.execute(
        sa.text(
            "SELECT DISTINCT claim_type FROM claims "
            "WHERE claim_type NOT IN ('Ingredient', 'Nutritional', 'Health', 'Performance', "
            "'Quality', 'Comparative', 'Environmental', 'Endorsement', 'Origin', 'Safety', 'Other')"
        )
    ).fetchall()
    if custom_types:
        found = [row[0] for row in custom_types]
        raise RuntimeError(
            f"Cannot downgrade migration f6a7b8c9d0e1: claims table contains custom claim categories "
            f"not permitted by the legacy chk_claim_type constraint: {found}. "
            f"Please update or archive these records before downgrading."
        )

    # Re-create check constraint limiting claim_type to the 11 original predefined categories
    op.create_check_constraint(
        'chk_claim_type',
        'claims',
        "claim_type IN ('Ingredient', 'Nutritional', 'Health', 'Performance', 'Quality', 'Comparative', 'Environmental', 'Endorsement', 'Origin', 'Safety', 'Other')"
    )

