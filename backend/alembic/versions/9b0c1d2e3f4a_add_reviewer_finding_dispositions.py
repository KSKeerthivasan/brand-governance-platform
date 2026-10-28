"""add_reviewer_finding_dispositions

Revision ID: 9b0c1d2e3f4a
Revises: 8a9b0c1d2e3f
Create Date: 2026-10-28 14:30:00.000000

Adds reviewer_finding_dispositions table to capture structured reviewer feedback
and dispositions (confirmed_issue, false_positive, guideline_unclear, conflicting_guidelines,
insufficient_evidence, other) for historical governance analytics and guideline ambiguity signals.
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '9b0c1d2e3f4a'
down_revision: Union[str, Sequence[str], None] = '8a9b0c1d2e3f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'reviewer_finding_dispositions',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('organization_id', sa.String(length=36), nullable=False),
        sa.Column('governance_run_id', sa.String(length=36), nullable=False),
        sa.Column('finding_id', sa.String(length=36), nullable=False),
        sa.Column('rule_id', sa.String(length=36), nullable=True),
        sa.Column('content_item_id', sa.String(length=36), nullable=True),
        sa.Column('content_version_id', sa.String(length=36), nullable=True),
        sa.Column('disposition', sa.String(length=50), nullable=False),
        sa.Column('reviewer_id', sa.String(length=36), nullable=False),
        sa.Column('explanation', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['content_item_id'], ['content_items.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['content_version_id'], ['content_versions.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['finding_id'], ['governance_findings.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['governance_run_id'], ['governance_runs.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['reviewer_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['rule_id'], ['knowledge_rules.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('reviewer_finding_dispositions', schema=None) as batch_op:
        batch_op.create_index('ix_reviewer_finding_dispositions_org_id', ['organization_id'], unique=False)
        batch_op.create_index('ix_reviewer_finding_dispositions_run_id', ['governance_run_id'], unique=False)
        batch_op.create_index('ix_reviewer_finding_dispositions_finding_id', ['finding_id'], unique=False)
        batch_op.create_index('ix_reviewer_finding_dispositions_rule_id', ['rule_id'], unique=False)
        batch_op.create_index('ix_reviewer_finding_dispositions_item_id', ['content_item_id'], unique=False)
        batch_op.create_index('ix_reviewer_finding_dispositions_version_id', ['content_version_id'], unique=False)


def downgrade() -> None:
    with op.batch_alter_table('reviewer_finding_dispositions', schema=None) as batch_op:
        batch_op.drop_index('ix_reviewer_finding_dispositions_version_id')
        batch_op.drop_index('ix_reviewer_finding_dispositions_item_id')
        batch_op.drop_index('ix_reviewer_finding_dispositions_rule_id')
        batch_op.drop_index('ix_reviewer_finding_dispositions_finding_id')
        batch_op.drop_index('ix_reviewer_finding_dispositions_run_id')
        batch_op.drop_index('ix_reviewer_finding_dispositions_org_id')
    op.drop_table('reviewer_finding_dispositions')
