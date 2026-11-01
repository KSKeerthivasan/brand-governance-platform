import os
import sys

# Ensure backend root is on sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError
from app.config import settings

def run_postgres_verification():
    print("Connecting to live database...")
    engine = create_engine(settings.DATABASE_URL)
    Session = sessionmaker(bind=engine)
    db = Session()

    try:
        org_id = db.execute(text("SELECT id FROM organizations LIMIT 1")).scalar()
        print(f"Using Organization ID: {org_id}")

        # Clean up any leftover test manifest from aborted run
        db.execute(text("SET LOCAL inkloom.allow_admin_purge = 'on'"))
        db.execute(text("DELETE FROM knowledge_base_versions WHERE id LIKE 'test-kb-%'"))
        db.commit()
        kb_id = "test-kb-verify-01"
        db.execute(text("""
            INSERT INTO knowledge_base_versions (id, organization_id, version_num, manifest_sha256, manifest_data, activation_reason)
            VALUES (:id, :org_id, 9991, 'hash_verify_1', '{"rules": []}', 'immutability test')
        """), {"id": kb_id, "org_id": org_id})
        db.commit()

        try:
            db.execute(text("UPDATE knowledge_base_versions SET activation_reason = 'tampered' WHERE id = :id"), {"id": kb_id})
            db.commit()
            raise AssertionError("FAIL: UPDATE on knowledge_base_versions should be blocked by trigger!")
        except Exception as e:
            db.rollback()
            assert "immutable" in str(e).lower(), f"Unexpected error: {e}"
            print("[PASS]: Immutability trigger blocked UPDATE on knowledge_base_versions")

        # -----------------------------------------------------------------
        # TEST 2: KB Version Immutability Trigger (DELETE)
        # -----------------------------------------------------------------
        try:
            db.execute(text("DELETE FROM knowledge_base_versions WHERE id = :id"), {"id": kb_id})
            db.commit()
            raise AssertionError("FAIL: DELETE on knowledge_base_versions should be blocked by trigger!")
        except Exception as e:
            db.rollback()
            assert "immutable" in str(e).lower(), f"Unexpected error: {e}"
            print("[PASS]: Immutability trigger blocked DELETE on knowledge_base_versions")

        # Clean up test KB version using admin purge override
        db.execute(text("SET LOCAL inkloom.allow_admin_purge = 'on'"))
        db.execute(text("DELETE FROM knowledge_base_versions WHERE id = :id"), {"id": kb_id})
        db.commit()
        print("[PASS]: Admin purge session override safely cleaned up test manifest")

        # -----------------------------------------------------------------
        # TEST 3: Cross-Organization ALL Claim Rejection
        # -----------------------------------------------------------------
        fake_org_id = "00000000-0000-0000-0000-000000000000"
        try:
            db.execute(text("""
                INSERT INTO claims (
                    id, organization_id, product_id, claim_id, claim_text,
                    claim_type, claim_status, applicable_product_id, applicable_market,
                    effective_from
                ) VALUES (
                    'test-clm-cross-01', :org_id, NULL, 'CLM-CROSS-01',
                    'Fake Claim', 'Ingredient', 'Approved', 'ALL',
                    'India', CURRENT_DATE
                )
            """), {"org_id": fake_org_id})
            db.commit()
            raise AssertionError("FAIL: Cross-org ALL claim should be rejected by fk_claims_organization!")
        except IntegrityError as e:
            db.rollback()
            assert "fk_claims_organization" in str(e).lower() or "foreign key" in str(e).lower()
            print("[PASS]: Cross-organization ALL claim rejected by independent organization foreign key")

        # -----------------------------------------------------------------
        # TEST 4: Product SKU Alignment & Deletion Restriction
        # -----------------------------------------------------------------
        prod_id = "test-prod-verify-01"
        sku = "TEST-SKU-VERIFY-01"
        db.execute(text("""
            INSERT INTO products (
                id, organization_id, product_id, product_name, product_category,
                offering_type, product_description, applicable_market, record_status
            ) VALUES (
                :id, :org_id, :sku, 'Test Beverage', 'Beverage',
                'Physical Product', 'Description', 'India', 'Active'
            )
        """), {"id": prod_id, "org_id": org_id, "sku": sku})
        db.commit()

        claim_id = "test-clm-verify-01"
        # Case A: Valid SKU alignment
        db.execute(text("""
            INSERT INTO claims (
                id, organization_id, product_id, claim_id, claim_text,
                claim_type, claim_status, applicable_product_id, applicable_market,
                effective_from
            ) VALUES (
                :cid, :org_id, :pid, 'CLM-VERIFY-01',
                'Valid Claim', 'Ingredient', 'Approved', :sku,
                'India', CURRENT_DATE
            )
        """), {"cid": claim_id, "org_id": org_id, "pid": prod_id, "sku": sku})
        db.commit()
        print("[PASS]: Valid product claim with matching SKU and surrogate product_id inserted")

        # Case B: SKU Mismatch
        try:
            db.execute(text("""
                INSERT INTO claims (
                    id, organization_id, product_id, claim_id, claim_text,
                    claim_type, claim_status, applicable_product_id, applicable_market,
                    effective_from
                ) VALUES (
                    'test-clm-mismatch-99', :org_id, :pid, 'CLM-MIS-99',
                    'Mismatch Claim', 'Ingredient', 'Approved', 'WRONG-SKU',
                    'India', CURRENT_DATE
                )
            """), {"org_id": org_id, "pid": prod_id})
            db.commit()
            raise AssertionError("FAIL: Claim with SKU mismatch should be rejected by 3-column composite FK!")
        except IntegrityError:
            db.rollback()
            print("[PASS]: SKU mismatch rejected by fk_claims_org_product_sku")

        # Case C: Product deletion restricted while claim references it
        try:
            db.execute(text("DELETE FROM products WHERE id = :id"), {"id": prod_id})
            db.commit()
            raise AssertionError("FAIL: Product deletion should be blocked by ON DELETE RESTRICT!")
        except IntegrityError:
            db.rollback()
            print("[PASS]: Product deletion blocked by ON DELETE RESTRICT when claim exists")

        # Clean up claim then product
        db.execute(text("DELETE FROM claims WHERE id = :id"), {"id": claim_id})
        db.execute(text("DELETE FROM products WHERE id = :id"), {"id": prod_id})
        db.commit()
        print("[PASS]: Cleaned up test product and claim")

        # -----------------------------------------------------------------
        # TEST 5: Single Pending Invitation Constraint & Token Rotation
        # -----------------------------------------------------------------
        inv_id_1 = "test-inv-v-01"
        inv_id_2 = "test-inv-v-02"
        test_email = "verify.invitation@example.com"

        db.execute(text("""
            INSERT INTO organization_invitations (
                id, organization_id, email_normalized, role, token_hash,
                inviter_email_snapshot, expires_at
            ) VALUES (
                :id, :org_id, :email, 'content_creator', 'hash_v_1',
                'admin@brand.com', NOW() + INTERVAL '7 days'
            )
        """), {"id": inv_id_1, "org_id": org_id, "email": test_email})
        db.commit()

        # Second simultaneous pending invitation fails
        try:
            db.execute(text("""
                INSERT INTO organization_invitations (
                    id, organization_id, email_normalized, role, token_hash,
                    inviter_email_snapshot, expires_at
                ) VALUES (
                    :id, :org_id, :email, 'content_creator', 'hash_v_2',
                    'admin@brand.com', NOW() + INTERVAL '7 days'
                )
            """), {"id": inv_id_2, "org_id": org_id, "email": test_email})
            db.commit()
            raise AssertionError("FAIL: Duplicate pending invitation should be rejected!")
        except IntegrityError:
            db.rollback()
            print("[PASS]: Duplicate pending invitation blocked by idx_single_pending_invitation")

        # Revoking the first allows token rotation
        db.execute(text("UPDATE organization_invitations SET status = 'revoked' WHERE id = :id"), {"id": inv_id_1})
        db.execute(text("""
            INSERT INTO organization_invitations (
                id, organization_id, email_normalized, role, token_hash,
                inviter_email_snapshot, expires_at
            ) VALUES (
                :id, :org_id, :email, 'content_creator', 'hash_v_2',
                'admin@brand.com', NOW() + INTERVAL '7 days'
            )
        """), {"id": inv_id_2, "org_id": org_id, "email": test_email})
        db.commit()
        print("[PASS]: Token rotation succeeded after previous invitation revoked")

        db.execute(text("DELETE FROM organization_invitations WHERE id IN (:id1, :id2)"), {"id1": inv_id_1, "id2": inv_id_2})
        db.commit()
        print("[PASS]: Cleaned up test invitations")

        # -----------------------------------------------------------------
        # TEST 6: Impact Rescoring Audit Preservation (RESTRICT)
        # -----------------------------------------------------------------
        # Need a KB version for job
        db.execute(text("""
            INSERT INTO knowledge_base_versions (id, organization_id, version_num, manifest_sha256, manifest_data, activation_reason)
            VALUES ('kb-rescore-test', :org_id, 9993, 'hash_rescore', '{"rules": []}', 'rescore test')
        """), {"org_id": org_id})

        job_id = "test-job-001"
        db.execute(text("""
            INSERT INTO impact_rescoring_jobs (
                id, organization_id, knowledge_base_version_id, idempotency_key, status
            ) VALUES (
                :id, :org_id, 'kb-rescore-test', 'idem-job-001', 'queued'
            )
        """), {"id": job_id, "org_id": org_id})

        batch_item_id = "test-item-001"
        db.execute(text("""
            INSERT INTO impact_rescoring_batch_items (
                id, job_id, batch_index, content_item_id, version_num,
                content_checksum, item_idempotency_key, status
            ) VALUES (
                :id, :job_id, 0, 'content-item-dummy', 1,
                'dummy_checksum', 'item-idem-001', 'pending'
            )
        """), {"id": batch_item_id, "job_id": job_id})
        db.commit()

        # Attempt to delete job must fail with RESTRICT
        try:
            db.execute(text("DELETE FROM impact_rescoring_jobs WHERE id = :id"), {"id": job_id})
            db.commit()
            raise AssertionError("FAIL: Deleting impact_rescoring_jobs should be blocked by ON DELETE RESTRICT!")
        except IntegrityError:
            db.rollback()
            print("[PASS]: Deletion of impact_rescoring_jobs blocked by ON DELETE RESTRICT")

        # Clean up batch item, job, and kb version
        db.execute(text("DELETE FROM impact_rescoring_batch_items WHERE id = :id"), {"id": batch_item_id})
        db.execute(text("DELETE FROM impact_rescoring_jobs WHERE id = :id"), {"id": job_id})
        db.execute(text("SET LOCAL inkloom.allow_admin_purge = 'on'"))
        db.execute(text("DELETE FROM knowledge_base_versions WHERE id = 'kb-rescore-test'"))
        db.commit()
        print("[PASS]: Cleaned up rescoring test records")

        print("\n========================================================")
        print("ALL 6 POSTGRESQL ACCEPTANCE TESTS PASSED SUCCESSFULLY!")
        print("========================================================")

    finally:
        db.close()

if __name__ == "__main__":
    run_postgres_verification()
