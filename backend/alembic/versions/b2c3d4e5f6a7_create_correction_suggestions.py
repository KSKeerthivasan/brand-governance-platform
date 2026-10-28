"""create_correction_suggestions

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-10-28 19:25:00.000000

Creates correction_suggestions table for explainable context-preserving correction suggestions (Milestone 5D).
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()

    if 'correction_suggestions' not in tables:
        op.create_table(
            'correction_suggestions',
            sa.Column('id', sa.String(length=36), primary_key=True),
            sa.Column('finding_id', sa.String(length=36), sa.ForeignKey('governance_findings.id', ondelete='CASCADE'), nullable=False),
            sa.Column('content_item_id', sa.String(length=36), sa.ForeignKey('content_items.id', ondelete='CASCADE'), nullable=False),
            sa.Column('content_version_id', sa.String(length=36), sa.ForeignKey('content_versions.id', ondelete='CASCADE'), nullable=False),
            sa.Column('source_checksum', sa.String(length=64), nullable=False),
            sa.Column('target_type', sa.String(length=50), nullable=False),
            sa.Column('page_number', sa.Integer(), nullable=True),
            sa.Column('rule_id', sa.String(length=36), sa.ForeignKey('knowledge_rules.id', ondelete='SET NULL'), nullable=True),
            sa.Column('rule_code', sa.String(length=50), nullable=True),
            sa.Column('fact_id', sa.String(length=36), sa.ForeignKey('knowledge_facts.id', ondelete='SET NULL'), nullable=True),
            sa.Column('fact_key', sa.String(length=100), nullable=True),
            sa.Column('original_text', sa.Text(), nullable=False),
            sa.Column('proposed_text', sa.Text(), nullable=True),
            sa.Column('diff_preview', sa.Text(), nullable=True),
            sa.Column('explanation', sa.Text(), nullable=False),
            sa.Column('evidence_source', sa.String(length=255), nullable=False),
            sa.Column('correction_type', sa.String(length=50), nullable=False),
            sa.Column('confidence', sa.String(length=20), nullable=False, server_default='high'),
            sa.Column('can_auto_apply', sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column('status', sa.String(length=50), nullable=False, server_default='pending'),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('resolved_at', sa.DateTime(), nullable=True)
        )
        op.create_index('ix_correction_suggestions_finding_id', 'correction_suggestions', ['finding_id'])
        op.create_index('ix_correction_suggestions_content_item_id', 'correction_suggestions', ['content_item_id'])
        op.create_index('ix_correction_suggestions_content_version_id', 'correction_suggestions', ['content_version_id'])
        op.create_index('ix_correction_suggestions_rule_id', 'correction_suggestions', ['rule_id'])
        op.create_index('ix_correction_suggestions_fact_id', 'correction_suggestions', ['fact_id'])


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()

    if 'correction_suggestions' in tables:
        op.drop_index('ix_correction_suggestions_fact_id', table_name='correction_suggestions')
        op.drop_index('ix_correction_suggestions_rule_id', table_name='correction_suggestions')
        op.drop_index('ix_correction_suggestions_content_version_id', table_name='correction_suggestions')
        op.drop_index('ix_correction_suggestions_content_item_id', table_name='correction_suggestions')
        op.drop_index('ix_correction_suggestions_finding_id', table_name='correction_suggestions')
        op.drop_table('correction_suggestions')
