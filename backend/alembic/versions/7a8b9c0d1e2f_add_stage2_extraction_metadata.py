"""add_stage2_extraction_metadata

Revision ID: 7a8b9c0d1e2f
Revises: f5905479dc52
Create Date: 2026-10-27 08:45:00.000000

Adds structured metadata columns to knowledge_rules and knowledge_facts to support
Stage 2 Gemini-extracted candidate governance metadata, evidence validation,
source status, contextual rules, and reviewer correction tracking.
All columns are nullable with safe defaults, ensuring 100% backward compatibility.
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '7a8b9c0d1e2f'
down_revision: Union[str, Sequence[str], None] = 'f5905479dc52'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Extend knowledge_rules with Stage 2 metadata
    with op.batch_alter_table('knowledge_rules', schema=None) as batch_op:
        batch_op.add_column(sa.Column('rule_code', sa.String(length=50), nullable=True))
        batch_op.add_column(sa.Column('source_status', sa.String(length=50), nullable=True, server_default='unknown'))
        batch_op.add_column(sa.Column('enforcement_action', sa.String(length=50), nullable=True, server_default='flag_for_review'))
        batch_op.add_column(sa.Column('rationale', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('recommended_alternatives', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('exceptions', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('examples_bad', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('examples_good', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('evidence_passage', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('page_number', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('evidence_validation', sa.String(length=50), nullable=True, server_default='unverified'))
        batch_op.add_column(sa.Column('uncertainty_notes', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('original_extraction', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('is_corrected', sa.Boolean(), nullable=False, server_default='0'))
        batch_op.create_index('ix_knowledge_rules_rule_code', ['rule_code'], unique=False)

    # 2. Extend knowledge_facts with Stage 2 metadata
    with op.batch_alter_table('knowledge_facts', schema=None) as batch_op:
        batch_op.add_column(sa.Column('product_id', sa.String(length=50), nullable=True))
        batch_op.add_column(sa.Column('unit', sa.String(length=50), nullable=True))
        batch_op.add_column(sa.Column('value_status', sa.String(length=50), nullable=True, server_default='explicitly_stated'))
        batch_op.add_column(sa.Column('source_status', sa.String(length=50), nullable=True, server_default='approved'))
        batch_op.add_column(sa.Column('page_number', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('evidence_validation', sa.String(length=50), nullable=True, server_default='unverified'))
        batch_op.add_column(sa.Column('uncertainty_notes', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('original_extraction', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('is_corrected', sa.Boolean(), nullable=False, server_default='0'))
        batch_op.create_index('ix_knowledge_facts_product_id', ['product_id'], unique=False)


def downgrade() -> None:
    with op.batch_alter_table('knowledge_facts', schema=None) as batch_op:
        batch_op.drop_index('ix_knowledge_facts_product_id')
        batch_op.drop_column('is_corrected')
        batch_op.drop_column('original_extraction')
        batch_op.drop_column('uncertainty_notes')
        batch_op.drop_column('evidence_validation')
        batch_op.drop_column('page_number')
        batch_op.drop_column('source_status')
        batch_op.drop_column('value_status')
        batch_op.drop_column('unit')
        batch_op.drop_column('product_id')

    with op.batch_alter_table('knowledge_rules', schema=None) as batch_op:
        batch_op.drop_index('ix_knowledge_rules_rule_code')
        batch_op.drop_column('is_corrected')
        batch_op.drop_column('original_extraction')
        batch_op.drop_column('uncertainty_notes')
        batch_op.drop_column('evidence_validation')
        batch_op.drop_column('page_number')
        batch_op.drop_column('evidence_passage')
        batch_op.drop_column('examples_good')
        batch_op.drop_column('examples_bad')
        batch_op.drop_column('exceptions')
        batch_op.drop_column('recommended_alternatives')
        batch_op.drop_column('rationale')
        batch_op.drop_column('enforcement_action')
        batch_op.drop_column('source_status')
        batch_op.drop_column('rule_code')
