"""round3_schema_expansion

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-11-01 01:12:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import text

# revision identifiers, used by Alembic.
revision = 'd4e5f6a7b8c9'
down_revision = 'c3d4e5f6a7b8'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # -------------------------------------------------------------------------
    # 1. ORGANIZATIONS SOFT DELETION
    # -------------------------------------------------------------------------
    op.add_column('organizations', sa.Column('is_archived', sa.Boolean(), nullable=False, server_default=sa.text('false')))
    op.add_column('organizations', sa.Column('archived_at', sa.DateTime(), nullable=True))

    # -------------------------------------------------------------------------
    # 2. BRAND PROFILES & COLOR PALETTE
    # -------------------------------------------------------------------------
    op.create_table(
        'brand_profiles',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('organization_id', sa.String(length=36), nullable=False),
        sa.Column('brand_name', sa.String(length=255), nullable=False),
        sa.Column('brand_description', sa.Text(), nullable=False),
        sa.Column('approved_taglines', sa.JSON(), nullable=False, server_default='[]'),
        sa.Column('brand_personality', sa.JSON(), nullable=False, server_default='[]'),
        sa.Column('preferred_tone', sa.JSON(), nullable=False, server_default='[]'),
        sa.Column('tones_to_avoid', sa.JSON(), nullable=False, server_default='[]'),
        sa.Column('preferred_terminology', sa.JSON(), nullable=False, server_default='[]'),
        sa.Column('prohibited_terminology', sa.JSON(), nullable=False, server_default='[]'),
        sa.Column('writing_style', sa.String(length=100), nullable=False),
        sa.Column('approved_languages', sa.JSON(), nullable=False, server_default='["en"]'),
        sa.Column('primary_heading_font', sa.String(length=100), nullable=False),
        sa.Column('secondary_body_font', sa.String(length=100), nullable=False),
        sa.Column('additional_approved_fonts', sa.JSON(), nullable=False, server_default='[]'),
        sa.Column('typography_instructions', sa.Text(), nullable=True),
        sa.Column('visual_style', sa.JSON(), nullable=False, server_default='[]'),
        sa.Column('preferred_imagery_style', sa.JSON(), nullable=False, server_default='[]'),
        sa.Column('preferred_backgrounds', sa.JSON(), nullable=False, server_default='[]'),
        sa.Column('visual_styles_to_avoid', sa.JSON(), nullable=False, server_default='[]'),
        sa.Column('logo_usage_instructions', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='RESTRICT'),
        sa.UniqueConstraint('organization_id', 'id', name='uq_brand_profiles_org'),
    )
    op.create_index('ix_brand_profiles_organization_id', 'brand_profiles', ['organization_id'])

    op.create_table(
        'brand_colors',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('organization_id', sa.String(length=36), nullable=False),
        sa.Column('brand_profile_id', sa.String(length=36), nullable=False),
        sa.Column('colour_name', sa.String(length=100), nullable=False),
        sa.Column('colour_family', sa.String(length=50), nullable=False),
        sa.Column('colour_role', sa.String(length=50), nullable=False),
        sa.Column('hex_value', sa.String(length=7), nullable=False),
        sa.Column('rgb_r', sa.Integer(), nullable=False),
        sa.Column('rgb_g', sa.Integer(), nullable=False),
        sa.Column('rgb_b', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['organization_id', 'brand_profile_id'], ['brand_profiles.organization_id', 'brand_profiles.id'], name='fk_brand_colors_org_profile', ondelete='CASCADE'),
        sa.CheckConstraint('rgb_r BETWEEN 0 AND 255', name='chk_color_rgb_r'),
        sa.CheckConstraint('rgb_g BETWEEN 0 AND 255', name='chk_color_rgb_g'),
        sa.CheckConstraint('rgb_b BETWEEN 0 AND 255', name='chk_color_rgb_b'),
    )
    op.create_index('ix_brand_colors_organization_id', 'brand_colors', ['organization_id'])
    op.create_index('ix_brand_colors_brand_profile_id', 'brand_colors', ['brand_profile_id'])

    # -------------------------------------------------------------------------
    # 3. PRODUCTS (15 COLUMNS WITH 3-COLUMN UNIQUE CONSTRAINT)
    # -------------------------------------------------------------------------
    op.create_table(
        'products',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('organization_id', sa.String(length=36), nullable=False),
        sa.Column('product_id', sa.String(length=100), nullable=False),
        sa.Column('product_name', sa.String(length=255), nullable=False),
        sa.Column('product_category', sa.String(length=100), nullable=False),
        sa.Column('offering_type', sa.String(length=50), nullable=False),
        sa.Column('product_description', sa.Text(), nullable=False),
        sa.Column('variant_name', sa.String(length=100), nullable=True),
        sa.Column('sku', sa.String(length=100), nullable=True),
        sa.Column('pack_size', sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column('pack_unit', sa.String(length=50), nullable=True),
        sa.Column('ingredients_components', sa.Text(), nullable=True),
        sa.Column('key_features', sa.Text(), nullable=True),
        sa.Column('specifications', sa.Text(), nullable=True),
        sa.Column('known_limitations', sa.Text(), nullable=True),
        sa.Column('applicable_market', sa.String(length=100), nullable=False),
        sa.Column('record_status', sa.String(length=50), nullable=False, server_default='Active'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='RESTRICT'),
        sa.UniqueConstraint('organization_id', 'id', name='uq_products_org_id'),
        sa.UniqueConstraint('organization_id', 'product_id', name='uq_products_org_business_id'),
        sa.UniqueConstraint('organization_id', 'id', 'product_id', name='uq_products_org_id_business'),
        sa.CheckConstraint("offering_type IN ('Physical Product', 'Service', 'Digital Product')", name='chk_product_offering_type'),
        sa.CheckConstraint("record_status IN ('Active', 'Inactive', 'Discontinued')", name='chk_product_record_status'),
    )
    op.create_index('ix_products_organization_id', 'products', ['organization_id'])
    op.create_index('ix_products_product_id', 'products', ['product_id'])

    # -------------------------------------------------------------------------
    # 4. CLAIMS & REQUIRED DISCLOSURES
    # -------------------------------------------------------------------------
    op.create_table(
        'claims',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('organization_id', sa.String(length=36), nullable=False),
        sa.Column('product_id', sa.String(length=36), nullable=True),
        sa.Column('claim_id', sa.String(length=100), nullable=False),
        sa.Column('claim_text', sa.Text(), nullable=False),
        sa.Column('claim_type', sa.String(length=50), nullable=False),
        sa.Column('claim_status', sa.String(length=50), nullable=False),
        sa.Column('applicable_product_id', sa.String(length=100), nullable=False),
        sa.Column('approved_variations', sa.Text(), nullable=True),
        sa.Column('restricted_conditions', sa.Text(), nullable=True),
        sa.Column('prohibited_variations', sa.Text(), nullable=True),
        sa.Column('applicable_market', sa.String(length=100), nullable=False),
        sa.Column('effective_from', sa.Date(), nullable=False),
        sa.Column('effective_until', sa.Date(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], name='fk_claims_organization', ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(
            ['organization_id', 'product_id', 'applicable_product_id'],
            ['products.organization_id', 'products.id', 'products.product_id'],
            name='fk_claims_org_product_sku',
            ondelete='RESTRICT'
        ),
        sa.UniqueConstraint('organization_id', 'id', name='uq_claims_org_id'),
        sa.UniqueConstraint('organization_id', 'claim_id', name='uq_claims_org_business_id'),
        sa.CheckConstraint(
            "(applicable_product_id = 'ALL' AND product_id IS NULL) OR (applicable_product_id <> 'ALL' AND product_id IS NOT NULL)",
            name='chk_claim_product_applicability'
        ),
        sa.CheckConstraint(
            "claim_type IN ('Ingredient', 'Nutritional', 'Health', 'Performance', 'Quality', 'Comparative', 'Environmental', 'Endorsement', 'Origin', 'Safety', 'Other')",
            name='chk_claim_type'
        ),
        sa.CheckConstraint(
            "claim_status IN ('Approved', 'Restricted', 'Prohibited')",
            name='chk_claim_status'
        ),
        sa.CheckConstraint(
            "(claim_status <> 'Restricted') OR (restricted_conditions IS NOT NULL AND length(trim(restricted_conditions)) > 0)",
            name='chk_claim_restricted_condition'
        ),
    )
    op.create_index('ix_claims_organization_id', 'claims', ['organization_id'])
    op.create_index('ix_claims_product_id', 'claims', ['product_id'])
    op.create_index('ix_claims_claim_id', 'claims', ['claim_id'])

    op.create_table(
        'required_disclosures',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('organization_id', sa.String(length=36), nullable=False),
        sa.Column('product_id', sa.String(length=36), nullable=True),
        sa.Column('disclosure_id', sa.String(length=100), nullable=False),
        sa.Column('disclosure_text', sa.Text(), nullable=False),
        sa.Column('applicable_product_id', sa.String(length=100), nullable=False),
        sa.Column('applicable_market', sa.String(length=100), nullable=False),
        sa.Column('applies_when', sa.Text(), nullable=False),
        sa.Column('effective_from', sa.Date(), nullable=False),
        sa.Column('effective_until', sa.Date(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], name='fk_disclosures_organization', ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(
            ['organization_id', 'product_id', 'applicable_product_id'],
            ['products.organization_id', 'products.id', 'products.product_id'],
            name='fk_disclosures_org_product_sku',
            ondelete='RESTRICT'
        ),
        sa.UniqueConstraint('organization_id', 'id', name='uq_disclosures_org_id'),
        sa.UniqueConstraint('organization_id', 'disclosure_id', name='uq_disclosures_org_business_id'),
        sa.CheckConstraint(
            "(applicable_product_id = 'ALL' AND product_id IS NULL) OR (applicable_product_id <> 'ALL' AND product_id IS NOT NULL)",
            name='chk_disclosure_product_applicability'
        ),
    )
    op.create_index('ix_disclosures_organization_id', 'required_disclosures', ['organization_id'])
    op.create_index('ix_disclosures_product_id', 'required_disclosures', ['product_id'])
    op.create_index('ix_disclosures_disclosure_id', 'required_disclosures', ['disclosure_id'])

    # -------------------------------------------------------------------------
    # 5. BRAND ASSETS UPDATE
    # -------------------------------------------------------------------------
    op.add_column('brand_assets', sa.Column('associated_product_id', sa.String(length=36), nullable=True))
    op.add_column('brand_assets', sa.Column('usage_notes', sa.Text(), nullable=True))
    op.create_foreign_key(
        'fk_brand_assets_associated_product',
        'brand_assets', 'products',
        ['associated_product_id'], ['id'],
        ondelete='SET NULL'
    )
    op.create_index('ix_brand_assets_associated_product_id', 'brand_assets', ['associated_product_id'])

    # -------------------------------------------------------------------------
    # 6. STAGED IMPORTS & ATOMIC ROWS
    # -------------------------------------------------------------------------
    op.create_table(
        'staged_imports',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('organization_id', sa.String(length=36), nullable=False),
        sa.Column('import_type', sa.String(length=50), nullable=False),
        sa.Column('idempotency_key', sa.String(length=64), nullable=False),
        sa.Column('file_name', sa.String(length=255), nullable=False),
        sa.Column('file_sha256', sa.String(length=64), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='pending_preview'),
        sa.Column('total_rows', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('valid_rows', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('error_rows', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('has_disclosures', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('validation_summary', sa.JSON(), nullable=False, server_default='{}'),
        sa.Column('created_by', sa.String(length=36), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='SET NULL'),
        sa.UniqueConstraint('organization_id', 'id', name='uq_staged_imports_org_id'),
        sa.UniqueConstraint('organization_id', 'idempotency_key', name='uq_staged_imports_org_idempotency'),
        sa.CheckConstraint("import_type IN ('product_catalogue', 'claims_and_disclosures')", name='chk_staged_import_type'),
        sa.CheckConstraint("status IN ('pending_preview', 'committed', 'failed', 'discarded')", name='chk_staged_import_status'),
    )
    op.create_index('ix_staged_imports_organization_id', 'staged_imports', ['organization_id'])

    op.create_table(
        'staged_import_product_rows',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('organization_id', sa.String(length=36), nullable=False),
        sa.Column('import_id', sa.String(length=36), nullable=False),
        sa.Column('row_number', sa.Integer(), nullable=False),
        sa.Column('raw_data', sa.JSON(), nullable=False),
        sa.Column('parsed_data', sa.JSON(), nullable=True),
        sa.Column('validation_errors', sa.JSON(), nullable=False, server_default='[]'),
        sa.Column('is_valid', sa.Boolean(), nullable=False, server_default='false'),
        sa.ForeignKeyConstraint(['organization_id', 'import_id'], ['staged_imports.organization_id', 'staged_imports.id'], name='fk_staged_products_import', ondelete='CASCADE'),
    )
    op.create_index('ix_staged_import_product_rows_org_id', 'staged_import_product_rows', ['organization_id'])
    op.create_index('ix_staged_import_product_rows_import_id', 'staged_import_product_rows', ['import_id'])

    op.create_table(
        'staged_import_claim_rows',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('organization_id', sa.String(length=36), nullable=False),
        sa.Column('import_id', sa.String(length=36), nullable=False),
        sa.Column('row_number', sa.Integer(), nullable=False),
        sa.Column('raw_data', sa.JSON(), nullable=False),
        sa.Column('parsed_data', sa.JSON(), nullable=True),
        sa.Column('validation_errors', sa.JSON(), nullable=False, server_default='[]'),
        sa.Column('is_valid', sa.Boolean(), nullable=False, server_default='false'),
        sa.ForeignKeyConstraint(['organization_id', 'import_id'], ['staged_imports.organization_id', 'staged_imports.id'], name='fk_staged_claims_import', ondelete='CASCADE'),
    )
    op.create_index('ix_staged_import_claim_rows_org_id', 'staged_import_claim_rows', ['organization_id'])
    op.create_index('ix_staged_import_claim_rows_import_id', 'staged_import_claim_rows', ['import_id'])

    op.create_table(
        'staged_import_disclosure_rows',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('organization_id', sa.String(length=36), nullable=False),
        sa.Column('import_id', sa.String(length=36), nullable=False),
        sa.Column('row_number', sa.Integer(), nullable=False),
        sa.Column('raw_data', sa.JSON(), nullable=False),
        sa.Column('parsed_data', sa.JSON(), nullable=True),
        sa.Column('validation_errors', sa.JSON(), nullable=False, server_default='[]'),
        sa.Column('is_valid', sa.Boolean(), nullable=False, server_default='false'),
        sa.ForeignKeyConstraint(['organization_id', 'import_id'], ['staged_imports.organization_id', 'staged_imports.id'], name='fk_staged_disclosures_import', ondelete='CASCADE'),
    )
    op.create_index('ix_staged_import_disclosure_rows_org_id', 'staged_import_disclosure_rows', ['organization_id'])
    op.create_index('ix_staged_import_disclosure_rows_import_id', 'staged_import_disclosure_rows', ['import_id'])

    # -------------------------------------------------------------------------
    # 7. IMMUTABLE KNOWLEDGE BASE MANIFESTS & ACTIVE POINTER
    # -------------------------------------------------------------------------
    op.create_table(
        'knowledge_base_versions',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('organization_id', sa.String(length=36), nullable=False),
        sa.Column('version_num', sa.Integer(), nullable=False),
        sa.Column('manifest_sha256', sa.String(length=64), nullable=False),
        sa.Column('manifest_data', sa.JSON(), nullable=False),
        sa.Column('activated_by', sa.String(length=36), nullable=True),
        sa.Column('activated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('activation_reason', sa.String(length=255), nullable=False),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['activated_by'], ['users.id'], ondelete='RESTRICT'),
        sa.UniqueConstraint('organization_id', 'id', name='uq_kb_versions_org_id'),
        sa.UniqueConstraint('organization_id', 'version_num', name='uq_kb_versions_org_num'),
    )
    op.create_index('ix_kb_versions_org_id', 'knowledge_base_versions', ['organization_id'])

    op.create_table(
        'organization_active_knowledge_bases',
        sa.Column('organization_id', sa.String(length=36), primary_key=True),
        sa.Column('active_version_id', sa.String(length=36), nullable=False),
        sa.Column('activated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('activated_by', sa.String(length=36), nullable=True),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['active_version_id'], ['knowledge_base_versions.id'], name='fk_active_kb_version', ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['activated_by'], ['users.id'], ondelete='SET NULL'),
    )

    # PostgreSQL Immutability Trigger
    op.execute("""
        CREATE OR REPLACE FUNCTION trg_enforce_kb_immutability()
        RETURNS TRIGGER AS $$
        BEGIN
            IF TG_OP = 'DELETE' AND current_setting('inkloom.allow_admin_purge', true) = 'on' THEN
                RETURN OLD;
            END IF;
            RAISE EXCEPTION 'knowledge_base_versions records are strictly immutable and cannot be updated or deleted (attempted % on id %)', TG_OP, OLD.id;
        END;
        $$ LANGUAGE plpgsql;

        CREATE TRIGGER trg_protect_kb_version_immutability
        BEFORE UPDATE OR DELETE ON knowledge_base_versions
        FOR EACH ROW EXECUTE FUNCTION trg_enforce_kb_immutability();
    """)

    # -------------------------------------------------------------------------
    # 8. CONTENT ITEMS & GOVERNANCE RUNS WITH BACKFILL
    # -------------------------------------------------------------------------
    op.add_column('content_items', sa.Column('product_id', sa.String(length=36), nullable=True))
    op.create_unique_constraint('uq_content_items_org_id', 'content_items', ['organization_id', 'id'])
    op.create_foreign_key(
        'fk_content_items_org_product',
        'content_items', 'products',
        ['organization_id', 'product_id'], ['organization_id', 'id'],
        ondelete='RESTRICT'
    )
    op.create_index('ix_content_items_product_id', 'content_items', ['product_id'])

    op.alter_column('content_versions', 'body_text', nullable=True)

    op.add_column('governance_runs', sa.Column('organization_id', sa.String(length=36), nullable=True))
    op.add_column('governance_runs', sa.Column('knowledge_base_version_id', sa.String(length=36), nullable=True))
    op.add_column('governance_runs', sa.Column('baseline_status', sa.String(length=50), nullable=False, server_default='legacy_unversioned'))
    op.add_column('governance_runs', sa.Column('trigger_type', sa.String(length=50), nullable=False, server_default='user_check'))

    # Backfill organization_id on all existing governance runs from content items
    op.execute("""
        UPDATE governance_runs gr
        SET organization_id = ci.organization_id
        FROM content_versions cv
        JOIN content_items ci ON cv.content_item_id = ci.id
        WHERE gr.content_version_id = cv.id
          AND gr.organization_id IS NULL;
    """)

    op.alter_column('governance_runs', 'organization_id', nullable=False)
    op.create_index('ix_governance_runs_organization_id', 'governance_runs', ['organization_id'])
    op.create_index('ix_governance_runs_kb_version_id', 'governance_runs', ['knowledge_base_version_id'])

    op.create_foreign_key(
        'fk_gov_runs_org_kb',
        'governance_runs', 'knowledge_base_versions',
        ['organization_id', 'knowledge_base_version_id'],
        ['organization_id', 'id'],
        ondelete='RESTRICT'
    )
    op.create_check_constraint(
        'chk_gov_run_baseline_status',
        'governance_runs',
        "baseline_status IN ('legacy_unversioned', 'seeded_baseline_v1', 'versioned')"
    )

    # -------------------------------------------------------------------------
    # 9. SECURE INVITATIONS
    # -------------------------------------------------------------------------
    op.create_table(
        'organization_invitations',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('organization_id', sa.String(length=36), nullable=False),
        sa.Column('email_normalized', sa.String(length=255), nullable=False),
        sa.Column('role', sa.String(length=50), nullable=False),
        sa.Column('token_hash', sa.String(length=64), nullable=False, unique=True),
        sa.Column('delivery_method', sa.String(length=50), nullable=False, server_default='firebase_email_link'),
        sa.Column('delivery_status', sa.String(length=50), nullable=False, server_default='pending'),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='pending'),
        sa.Column('invited_by', sa.String(length=36), nullable=True),
        sa.Column('inviter_email_snapshot', sa.String(length=255), nullable=False),
        sa.Column('accepted_by_user_id', sa.String(length=36), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('consumed_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['invited_by'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['accepted_by_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.CheckConstraint("role IN ('org_admin', 'knowledge_reviewer', 'content_creator', 'approval_manager')", name='chk_invitation_role'),
        sa.CheckConstraint("status IN ('pending', 'accepted', 'expired', 'revoked')", name='chk_invitation_status'),
    )
    op.create_index('ix_org_invitations_org_id', 'organization_invitations', ['organization_id'])
    op.create_index('ix_org_invitations_email', 'organization_invitations', ['email_normalized'])
    op.create_index('ix_org_invitations_token_hash', 'organization_invitations', ['token_hash'])

    # Partial unique index for exactly one pending invitation per org + email
    op.execute("""
        CREATE UNIQUE INDEX idx_single_pending_invitation
        ON organization_invitations(organization_id, email_normalized)
        WHERE status = 'pending';
    """)

    # -------------------------------------------------------------------------
    # 10. IMPACT RESCORING JOBS & BATCH ITEMS (RESTRICT ON DELETE)
    # -------------------------------------------------------------------------
    op.create_table(
        'impact_rescoring_jobs',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('organization_id', sa.String(length=36), nullable=False),
        sa.Column('knowledge_base_version_id', sa.String(length=36), nullable=False),
        sa.Column('idempotency_key', sa.String(length=64), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='queued'),
        sa.Column('total_items', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('completed_items', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('failed_items', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_batches', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('completed_batches', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('is_archived', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('archived_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(
            ['organization_id', 'knowledge_base_version_id'],
            ['knowledge_base_versions.organization_id', 'knowledge_base_versions.id'],
            name='fk_impact_jobs_kb',
            ondelete='RESTRICT'
        ),
        sa.UniqueConstraint('organization_id', 'idempotency_key', name='uq_impact_job_org_idempotency'),
        sa.CheckConstraint("status IN ('queued', 'processing', 'completed', 'partially_failed', 'failed')", name='chk_impact_job_status'),
    )
    op.create_index('ix_impact_rescoring_jobs_org_id', 'impact_rescoring_jobs', ['organization_id'])
    op.create_index('ix_impact_rescoring_jobs_kb_id', 'impact_rescoring_jobs', ['knowledge_base_version_id'])

    op.create_table(
        'impact_rescoring_batch_items',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('job_id', sa.String(length=36), nullable=False),
        sa.Column('batch_index', sa.Integer(), nullable=False),
        sa.Column('content_version_id', sa.String(length=36), nullable=True),
        sa.Column('content_item_id', sa.String(length=36), nullable=False),
        sa.Column('version_num', sa.Integer(), nullable=False),
        sa.Column('content_checksum', sa.String(length=64), nullable=False),
        sa.Column('item_idempotency_key', sa.String(length=64), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='pending'),
        sa.Column('retry_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('new_governance_run_id', sa.String(length=36), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('processed_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['job_id'], ['impact_rescoring_jobs.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['content_version_id'], ['content_versions.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['new_governance_run_id'], ['governance_runs.id'], ondelete='RESTRICT'),
        sa.UniqueConstraint('job_id', 'item_idempotency_key', name='uq_batch_item_idempotency'),
        sa.CheckConstraint("status IN ('pending', 'completed', 'failed')", name='chk_batch_item_status'),
    )
    op.create_index('ix_impact_batch_items_job_id', 'impact_rescoring_batch_items', ['job_id'])
    op.create_index('ix_impact_batch_items_content_version_id', 'impact_rescoring_batch_items', ['content_version_id'])
    op.create_index('ix_impact_batch_items_content_item_id', 'impact_rescoring_batch_items', ['content_item_id'])


def downgrade() -> None:
    # -------------------------------------------------------------------------
    # 1. POSTER-ONLY DATA LOSS SAFETY CHECK
    # -------------------------------------------------------------------------
    conn = op.get_bind()
    null_body_count = conn.execute(
        text("SELECT COUNT(*) FROM content_versions WHERE body_text IS NULL")
    ).scalar()

    if null_body_count and null_body_count > 0:
        raise RuntimeError(
            f"Migration rollback aborted: found {null_body_count} poster-only content versions "
            "with NULL body_text. Reverting body_text to NOT NULL would cause unrecoverable data loss "
            "or require synthetic text generation. Manual archival of these records is required before rollback."
        )

    # -------------------------------------------------------------------------
    # 2. RESTORE CONTENT_VERSIONS.BODY_TEXT TO NOT NULL
    # -------------------------------------------------------------------------
    op.alter_column('content_versions', 'body_text', nullable=False)

    # -------------------------------------------------------------------------
    # 3. REVERT GOVERNANCE RUNS & CONTENT ITEMS
    # -------------------------------------------------------------------------
    op.drop_constraint('chk_gov_run_baseline_status', 'governance_runs', type_='check')
    op.drop_constraint('fk_gov_runs_org_kb', 'governance_runs', type_='foreignkey')
    op.drop_index('ix_governance_runs_kb_version_id', table_name='governance_runs')
    op.drop_index('ix_governance_runs_organization_id', table_name='governance_runs')
    op.drop_column('governance_runs', 'trigger_type')
    op.drop_column('governance_runs', 'baseline_status')
    op.drop_column('governance_runs', 'knowledge_base_version_id')
    op.drop_column('governance_runs', 'organization_id')

    op.drop_constraint('fk_content_items_org_product', 'content_items', type_='foreignkey')
    op.drop_constraint('uq_content_items_org_id', 'content_items', type_='unique')
    op.drop_index('ix_content_items_product_id', table_name='content_items')
    op.drop_column('content_items', 'product_id')

    op.drop_index('ix_brand_assets_associated_product_id', table_name='brand_assets')
    op.drop_constraint('fk_brand_assets_associated_product', 'brand_assets', type_='foreignkey')
    op.drop_column('brand_assets', 'usage_notes')
    op.drop_column('brand_assets', 'associated_product_id')

    # -------------------------------------------------------------------------
    # 4. DROP RESCORING & INVITATION TABLES
    # -------------------------------------------------------------------------
    op.drop_table('impact_rescoring_batch_items')
    op.drop_table('impact_rescoring_jobs')
    op.execute("DROP INDEX IF EXISTS idx_single_pending_invitation")
    op.drop_table('organization_invitations')

    # -------------------------------------------------------------------------
    # 5. DROP STAGED IMPORT TABLES
    # -------------------------------------------------------------------------
    op.drop_table('staged_import_disclosure_rows')
    op.drop_table('staged_import_claim_rows')
    op.drop_table('staged_import_product_rows')
    op.drop_table('staged_imports')

    # -------------------------------------------------------------------------
    # 6. DROP CLAIMS & DISCLOSURES
    # -------------------------------------------------------------------------
    op.drop_table('required_disclosures')
    op.drop_table('claims')
    op.drop_table('products')
    op.drop_table('brand_colors')
    op.drop_table('brand_profiles')

    # -------------------------------------------------------------------------
    # 7. DROP IMMUTABLE KNOWLEDGE BASE MANIFESTS
    # WARNING: THIS DELETES HISTORICAL GOVERNANCE BASELINES (TEST/DEV ONLY)
    # -------------------------------------------------------------------------
    op.drop_table('organization_active_knowledge_bases')
    op.execute("DROP TRIGGER IF EXISTS trg_protect_kb_version_immutability ON knowledge_base_versions")
    op.execute("DROP FUNCTION IF EXISTS trg_enforce_kb_immutability")
    op.drop_table('knowledge_base_versions')

    op.drop_column('organizations', 'archived_at')
    op.drop_column('organizations', 'is_archived')
