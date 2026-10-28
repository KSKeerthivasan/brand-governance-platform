"""add_page_number_to_governance_findings

Revision ID: a1b2c3d4e5f6
Revises: 9b0c1d2e3f4a
Create Date: 2026-10-28 18:05:00.000000

Adds page_number column to governance_findings table for multi-page PDF creative governance.
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '9b0c1d2e3f4a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Safely add nullable page_number column to governance_findings
    op.add_column(
        'governance_findings',
        sa.Column('page_number', sa.Integer(), nullable=True)
    )
    # Create an index on (governance_run_id, page_number) for efficient page-level queries
    op.create_index(
        'ix_governance_findings_run_page',
        'governance_findings',
        ['governance_run_id', 'page_number']
    )


def downgrade() -> None:
    op.drop_index('ix_governance_findings_run_page', table_name='governance_findings')
    op.drop_column('governance_findings', 'page_number')
