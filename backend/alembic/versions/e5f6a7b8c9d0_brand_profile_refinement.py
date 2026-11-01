"""brand_profile_refinement - Add spelling_convention, writing_style_instructions,
preferred_visual_treatments columns to brand_profiles table; add usage_instructions
to brand_colors table; widen writing_style from String(100) to Text.

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-11-01 23:30:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'e5f6a7b8c9d0'
down_revision = 'd4e5f6a7b8c9'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Widen writing_style from String(100) to Text
    op.alter_column(
        'brand_profiles', 'writing_style',
        type_=sa.Text(),
        existing_type=sa.String(length=100),
        existing_nullable=False
    )

    # Add new Section B columns
    op.add_column('brand_profiles',
        sa.Column('spelling_convention', sa.String(length=50), nullable=True)
    )
    op.add_column('brand_profiles',
        sa.Column('writing_style_instructions', sa.Text(), nullable=True)
    )

    # Add new Section E column
    op.add_column('brand_profiles',
        sa.Column('preferred_visual_treatments', sa.JSON(), nullable=False, server_default='[]')
    )

    # Add usage_instructions to brand_colors
    op.add_column('brand_colors',
        sa.Column('usage_instructions', sa.Text(), nullable=True)
    )


def downgrade() -> None:
    op.drop_column('brand_colors', 'usage_instructions')
    op.drop_column('brand_profiles', 'preferred_visual_treatments')
    op.drop_column('brand_profiles', 'writing_style_instructions')
    op.drop_column('brand_profiles', 'spelling_convention')
    op.alter_column(
        'brand_profiles', 'writing_style',
        type_=sa.String(length=100),
        existing_type=sa.Text(),
        existing_nullable=False
    )
