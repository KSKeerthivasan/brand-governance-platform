"""add_scope_to_knowledge_rules

Revision ID: 8a9b0c1d2e3f
Revises: 7a8b9c0d1e2f
Create Date: 2026-10-28 10:50:00.000000

Adds scope column to knowledge_rules to support channel- and content-format-specific
rule applicability in the context-aware governance engine.
Nullable with server_default='all_channels' for 100% backward compatibility.
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '8a9b0c1d2e3f'
down_revision: Union[str, Sequence[str], None] = '7a8b9c0d1e2f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('knowledge_rules', schema=None) as batch_op:
        batch_op.add_column(sa.Column('scope', sa.String(length=255), nullable=True, server_default='all_channels'))


def downgrade() -> None:
    with op.batch_alter_table('knowledge_rules', schema=None) as batch_op:
        batch_op.drop_column('scope')
