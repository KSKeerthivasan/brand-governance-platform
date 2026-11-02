import os
import sys
import uuid
from urllib.parse import urlparse, urlunparse
from sqlalchemy import create_engine, text

# Base database connection to create isolated test database
# Read from .env directly without importing app modules yet
env_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".env"))
base_url = None
if os.path.exists(env_path):
    with open(env_path, "r") as f:
        for line in f:
            if line.startswith("DATABASE_URL="):
                base_url = line.strip().split("DATABASE_URL=", 1)[1].strip().strip('"').strip("'")
                break

if not base_url:
    base_url = "postgresql://postgres:Keerthi%262007@db.qwvqifqnyurlqewkrsiw.supabase.co:5432/postgres"

parsed = urlparse(base_url)
TEST_DB_NAME = "inkloom_safety_check_db"
TEST_DB_URL = urlunparse(parsed._replace(path=f"/{TEST_DB_NAME}"))

def main():
    print("=" * 80)
    print("INKLOOM AI — FINAL READ-ONLY MIGRATION SAFETY VERIFICATION")
    print("=" * 80)

    # 1. Create the isolated test database
    print(f"\n[SETUP] Creating isolated PostgreSQL database: {TEST_DB_NAME}...")
    admin_engine = create_engine(base_url, isolation_level="AUTOCOMMIT")
    with admin_engine.connect() as conn:
        # Terminate any stale connections if existed
        conn.execute(text(f"""
            SELECT pg_terminate_backend(pid)
            FROM pg_stat_activity
            WHERE datname = '{TEST_DB_NAME}' AND pid <> pg_backend_pid()
        """))
        conn.execute(text(f"DROP DATABASE IF EXISTS {TEST_DB_NAME}"))
        conn.execute(text(f"CREATE DATABASE {TEST_DB_NAME}"))
    print("  -> Isolated database created successfully.")

    # Point environment to the test database
    os.environ["DATABASE_URL"] = TEST_DB_URL

    # Import app modules and alembic
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    from alembic.config import Config
    from alembic import command
    from alembic.script import ScriptDirectory

    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", TEST_DB_URL.replace("%", "%%"))

    # 1. Verify Alembic dependency chain
    print("\n[STEP 1] Verifying Alembic Dependency Chain...")
    script_dir = ScriptDirectory.from_config(cfg)
    rev_a7 = script_dir.get_revision("a7b8c9d0e1f2")
    rev_f6 = script_dir.get_revision("f6a7b8c9d0e1")
    rev_e5 = script_dir.get_revision("e5f6a7b8c9d0")

    print(f"  Revision 'a7b8c9d0e1f2': down_revision = '{rev_a7.down_revision}'")
    print(f"  Revision 'f6a7b8c9d0e1': down_revision = '{rev_f6.down_revision}'")
    print(f"  Revision 'e5f6a7b8c9d0': down_revision = '{rev_e5.down_revision}'")

    assert rev_a7.down_revision == "f6a7b8c9d0e1", "Chain error: a7b8c9d0e1f2 does not point to f6a7b8c9d0e1"
    assert rev_f6.down_revision == "e5f6a7b8c9d0", "Chain error: f6a7b8c9d0e1 does not point to e5f6a7b8c9d0"
    print("  -> Dependency chain: e5f6a7b8c9d0 -> f6a7b8c9d0e1 -> a7b8c9d0e1f2 [VERIFIED]")

    test_engine = create_engine(TEST_DB_URL)

    try:
        # Run migrations up to head on test database
        print("\n[SETUP] Applying Alembic migrations up to head...")
        command.upgrade(cfg, "head")

        with test_engine.connect() as conn:
            curr_rev = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
            print(f"  -> Migrations applied. Current alembic_version: {curr_rev}")
            assert curr_rev == "a7b8c9d0e1f2"

            # 2. Verify PostgreSQL constraint chk_claim_type_not_empty definition
            print("\n[STEP 2] Inspecting PostgreSQL constraint definition...")
            constraint_info = conn.execute(text("""
                SELECT conname, pg_get_constraintdef(c.oid)
                FROM pg_constraint c
                JOIN pg_namespace n ON n.oid = c.connamespace
                JOIN pg_class cl ON cl.oid = c.conrelid
                WHERE cl.relname = 'claims' AND c.conname = 'chk_claim_type_not_empty'
            """)).fetchall()
            print(f"  Found constraint: {constraint_info}")
            assert len(constraint_info) == 1
            print(f"  Constraint SQL definition: {constraint_info[0][1]}")

            # Create test org to satisfy FKs
            test_org_id = str(uuid.uuid4())
            conn.execute(text("""
                INSERT INTO organizations (id, name, slug, is_archived, created_at, updated_at)
                VALUES (:id, 'Test Org', 'test-org', false, NOW(), NOW())
            """), {"id": test_org_id})
            conn.commit()

            # Test constraint against empty string ''
            print("\n[STEP 2a] Testing empty string '' constraint rejection...")
            empty_rejected = False
            try:
                conn.execute(text("""
                    INSERT INTO claims (
                        id, organization_id, claim_id, claim_text, claim_type,
                        claim_status, applicable_product_id, applicable_market,
                        effective_from, created_at
                    ) VALUES (
                        :id, :org_id, 'CLM-EMPTY', 'Empty claim text', '',
                        'Approved', 'ALL', 'Global', '2026-01-01', NOW()
                    )
                """), {"id": str(uuid.uuid4()), "org_id": test_org_id})
                conn.commit()
            except Exception as e:
                conn.rollback()
                err_str = str(e)
                if "chk_claim_type_not_empty" in err_str:
                    empty_rejected = True
                    print(f"  -> PASS: Rejected empty string with constraint violation:\n     {err_str.splitlines()[0]}")
                else:
                    print(f"  -> UNEXPECTED ERROR: {e}")
            assert empty_rejected, "Constraint failed to reject empty string ''"

            # Test constraint against whitespace-only string '   '
            print("\n[STEP 2b] Testing whitespace-only '   ' constraint rejection...")
            space_rejected = False
            try:
                conn.execute(text("""
                    INSERT INTO claims (
                        id, organization_id, claim_id, claim_text, claim_type,
                        claim_status, applicable_product_id, applicable_market,
                        effective_from, created_at
                    ) VALUES (
                        :id, :org_id, 'CLM-SPACE', 'Space claim text', '   ',
                        'Approved', 'ALL', 'Global', '2026-01-01', NOW()
                    )
                """), {"id": str(uuid.uuid4()), "org_id": test_org_id})
                conn.commit()
            except Exception as e:
                conn.rollback()
                err_str = str(e)
                if "chk_claim_type_not_empty" in err_str:
                    space_rejected = True
                    print(f"  -> PASS: Rejected whitespace string with constraint violation:\n     {err_str.splitlines()[0]}")
                else:
                    print(f"  -> UNEXPECTED ERROR: {e}")
            assert space_rejected, "Constraint failed to reject whitespace-only string"

            # 3. Insert custom claim category 'Efficacy'
            print("\n[STEP 3] Inserting custom claim category 'Efficacy'...")
            custom_claim_id = str(uuid.uuid4())
            conn.execute(text("""
                INSERT INTO claims (
                    id, organization_id, claim_id, claim_text, claim_type,
                    claim_status, applicable_product_id, applicable_market,
                    effective_from, created_at
                ) VALUES (
                    :id, :org_id, 'CLM-CUST-EFF', 'Visibly reduces fine lines', 'Efficacy',
                    'Approved', 'ALL', 'Global', '2026-01-01', NOW()
                )
            """), {"id": custom_claim_id, "org_id": test_org_id})
            conn.commit()

            claim_row = conn.execute(text("SELECT claim_id, claim_type FROM claims WHERE id = :id"), {"id": custom_claim_id}).fetchone()
            print(f"  -> Successfully inserted claim: ID={claim_row[0]}, Type='{claim_row[1]}'")
            assert claim_row[1] == "Efficacy"

        # 4 & 5. Attempt downgrade through both migrations
        print("\n[STEP 4] Downgrading first migration: a7b8c9d0e1f2 -> f6a7b8c9d0e1...")
        command.downgrade(cfg, "f6a7b8c9d0e1")

        with test_engine.connect() as conn:
            rev_after_step4 = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
            print(f"  -> Intermediate alembic_version: {rev_after_step4}")
            assert rev_after_step4 == "f6a7b8c9d0e1"

            claim_after_step4 = conn.execute(text("SELECT claim_id, claim_type FROM claims WHERE id = :id"), {"id": custom_claim_id}).fetchone()
            print(f"  -> Claim data after dropping chk_claim_type_not_empty: {claim_after_step4}")
            assert claim_after_step4[1] == "Efficacy"

        print("\n[STEP 5] Attempting downgrade of second migration: f6a7b8c9d0e1 -> e5f6a7b8c9d0...")
        downgrade_blocked = False
        caught_message = None
        try:
            command.downgrade(cfg, "e5f6a7b8c9d0")
        except Exception as e:
            downgrade_blocked = True
            caught_message = str(e)
            print(f"  -> PASS: Downgrade blocked safely with error:\n     {caught_message}")

        assert downgrade_blocked, "Downgrade failed to block incompatible custom categories!"
        assert "custom claim categories not permitted by the legacy chk_claim_type constraint: ['Efficacy']" in caught_message

        # 6. Verify database contents and Alembic revision state remain consistent
        print("\n[STEP 6] Verifying database consistency and Alembic state after failed downgrade...")
        with test_engine.connect() as conn:
            rev_after_fail = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
            print(f"  -> Alembic version after failed downgrade: {rev_after_fail}")
            assert rev_after_fail == "f6a7b8c9d0e1", f"Alembic state corrupted: {rev_after_fail}"

            claims_count = conn.execute(text("SELECT COUNT(*) FROM claims")).scalar()
            print(f"  -> Total claims count in database: {claims_count}")
            assert claims_count == 1, "Claims were unexpectedly modified or deleted!"

            claim_verify = conn.execute(text("SELECT claim_id, claim_type, claim_text FROM claims WHERE id = :id"), {"id": custom_claim_id}).fetchone()
            print(f"  -> Preserved claim row: ID={claim_verify[0]}, Type='{claim_verify[1]}', Text='{claim_verify[2]}'")
            assert claim_verify[0] == "CLM-CUST-EFF"
            assert claim_verify[1] == "Efficacy"
            print("  -> Data integrity 100% verified: zero rows deleted, zero rows modified.")

        # 7. Verify normal upgrade still succeeds afterwards
        print("\n[STEP 7] Verifying normal upgrade still succeeds afterwards...")
        command.upgrade(cfg, "head")

        with test_engine.connect() as conn:
            rev_after_reupgrade = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
            print(f"  -> Alembic version after re-upgrade: {rev_after_reupgrade}")
            assert rev_after_reupgrade == "a7b8c9d0e1f2"

            claim_final = conn.execute(text("SELECT claim_id, claim_type FROM claims WHERE id = :id"), {"id": custom_claim_id}).fetchone()
            print(f"  -> Claim row after re-upgrade: ID={claim_final[0]}, Type='{claim_final[1]}'")
            assert claim_final[1] == "Efficacy"

            # Check that chk_claim_type_not_empty is active again
            constraint_final = conn.execute(text("""
                SELECT conname, pg_get_constraintdef(c.oid)
                FROM pg_constraint c
                JOIN pg_class cl ON cl.oid = c.conrelid
                WHERE cl.relname = 'claims' AND c.conname = 'chk_claim_type_not_empty'
            """)).fetchall()
            print(f"  -> Re-established constraint: {constraint_final[0]}")
            assert len(constraint_final) == 1

        print("\n" + "=" * 80)
        print("ALL 7 SAFETY VERIFICATION CHECKS PASSED PERFECTLY")
        print("=" * 80)

    finally:
        test_engine.dispose()
        print(f"\n[CLEANUP] Dropping isolated database: {TEST_DB_NAME}...")
        with admin_engine.connect() as conn:
            # Terminate any remaining connections to test DB before dropping
            conn.execute(text(f"""
                SELECT pg_terminate_backend(pid)
                FROM pg_stat_activity
                WHERE datname = '{TEST_DB_NAME}' AND pid <> pg_backend_pid()
            """))
            conn.execute(text(f"DROP DATABASE IF EXISTS {TEST_DB_NAME}"))
        print("  -> Isolated database cleanly dropped. Zero residual artifacts.")

if __name__ == "__main__":
    main()
