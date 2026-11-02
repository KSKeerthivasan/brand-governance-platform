import io
import uuid
import pytest
from datetime import datetime
from openpyxl import Workbook

from app.database import SessionLocal
from app.models.organization import Organization, User, OrganizationMembership
from app.models.content import ContentItem, ContentVersion, GovernanceRun, GovernanceFinding
from app.models.knowledge import KnowledgeBaseVersion, OrganizationActiveKnowledgeBase
from app.models.brand import Brand, BrandProfile, BrandColor
from app.models.product import Product
from app.models.claim import Claim, RequiredDisclosure
from app.services.governance_engine import governance_engine
from app.services.knowledge_resolver import resolve_knowledge_base


@pytest.fixture
def test_setup(client, auth_tokens):
    """
    Sets up an isolated test organization, users, and v1 baseline snapshot.
    """
    db = SessionLocal()
    org_id = auth_tokens["org_admin"]["headers"]["X-Organization-Id"]
    reviewer_headers = auth_tokens["knowledge_reviewer"]["headers"]
    creator_headers = auth_tokens["content_creator"]["headers"]

    # Verify baseline FreshSip BrandProfile and active v1 KB exists
    v1_version = db.query(KnowledgeBaseVersion).filter(
        KnowledgeBaseVersion.organization_id == org_id,
        KnowledgeBaseVersion.version_num == 1
    ).first()
    assert v1_version is not None, "v1 version record must exist"
    active_kb = db.query(OrganizationActiveKnowledgeBase).filter(
        OrganizationActiveKnowledgeBase.organization_id == org_id
    ).first()
    assert active_kb is not None, "Active KB must exist for test organization"
    active_kb.active_version_id = v1_version.id
    db.commit()

    # Create a test draft ContentItem & ContentVersion for governance evaluation
    creator_user = db.query(User).filter(User.email == "creator@freshsip.demo").first()
    brand = db.query(Brand).filter(Brand.organization_id == org_id).first()

    content_item = ContentItem(
        organization_id=org_id,
        brand_id=brand.id if brand else None,
        title="FreshSip Summer Campaign",
        channel="Social Media",
        created_by=creator_user.id,
        current_version_num=1,
        status="draft"
    )
    db.add(content_item)
    db.flush()

    content_version = ContentVersion(
        content_item_id=content_item.id,
        version_num=1,
        body_text="Enjoy our delicious Valencia Orange juice. Packed with essential nutrients for your day.",
        created_by=creator_user.id,
        checksum="test_initial_checksum_123"
    )
    db.add(content_version)
    db.commit()
    db.refresh(content_item)
    db.refresh(content_version)

    yield {
        "db": db,
        "org_id": org_id,
        "reviewer_headers": reviewer_headers,
        "creator_headers": creator_headers,
        "v1_version_id": v1_version.id,
        "content_item": content_item,
        "content_version": content_version,
    }
    db.close()


def _create_claims_excel_bytes(claims_data, disclosures_data):
    """Helper to generate in-memory valid Claims and Disclosures Excel workbook."""
    wb = Workbook()
    ws_claims = wb.active
    ws_claims.title = "Claims_Register"
    ws_claims.append(["claim_id", "applicable_product_id", "claim_text", "claim_status", "claim_type", "restricted_conditions", "prohibited_variations", "approved_variations", "applicable_market", "effective_from", "effective_until"])
    for row in claims_data:
        ws_claims.append(row)

    ws_disc = wb.create_sheet(title="Required_Disclosures")
    ws_disc.append(["disclosure_id", "applicable_product_id", "disclosure_text", "applies_when", "applicable_market", "effective_from", "effective_until"])
    for row in disclosures_data:
        ws_disc.append(row)

    bio = io.BytesIO()
    wb.save(bio)
    bio.seek(0)
    return bio


def _create_products_excel_bytes(products_data):
    """Helper to generate in-memory valid Product Catalogue Excel workbook with all 15 required columns."""
    wb = Workbook()
    ws_prod = wb.active
    ws_prod.title = "Product_Catalogue"
    ws_prod.append([
        "product_id", "product_name", "product_category", "offering_type",
        "product_description", "variant_name", "sku", "pack_size", "pack_unit",
        "ingredients_components", "key_features", "specifications",
        "known_limitations", "applicable_market", "record_status"
    ])
    for row in products_data:
        ws_prod.append(row)

    bio = io.BytesIO()
    wb.save(bio)
    bio.seek(0)
    return bio


def test_a_confirmation_does_not_activate_changes(client, test_setup):
    """
    Scenario A: Confirming an Excel import inserts working database records,
    but does NOT alter governance evaluation results before explicit Knowledge Base activation.
    """
    db = test_setup["db"]
    org_id = test_setup["org_id"]
    reviewer_headers = test_setup["reviewer_headers"]
    creator_headers = test_setup["creator_headers"]
    content_version = test_setup["content_version"]
    v1_id = test_setup["v1_version_id"]

    # 1. Update draft body text to use wording from an existing approved claim ("essential nutrients")
    # In v1 manifest, "Packed with essential nutrients" is approved.
    content_version.body_text = "Valencia Orange is packed with essential nutrients for healthy lifestyle."
    db.commit()

    # Pre-import baseline governance run
    run_pre = governance_engine.evaluate_content_version(db=db, content_version=content_version)
    assert run_pre.knowledge_base_version_id == v1_id
    assert run_pre.baseline_status == "versioned"
    pre_prohibited_findings = [f for f in run_pre.findings if f.category == "prohibited_claim"]
    assert len(pre_prohibited_findings) == 0, "Pre-import copy should not violate prohibited claims"

    # 2. Stage an Excel import that marks this claim as PROHIBITED
    excel_bytes = _create_claims_excel_bytes(
        claims_data=[
            ["CLM-002", "ALL", "Packed with essential nutrients", "Prohibited", "Nutritional", "", "", "", "IN", "2026-01-01", "2026-12-31"]
        ],
        disclosures_data=[
            ["DISC-001", "ALL", "No added sugar. Contains natural sugars.", "packaging, promotional_content", "IN", "2026-01-01", "2026-12-31"]
        ]
    )

    res_upload = client.post(
        "/api/v1/knowledge/import/claims_and_disclosures/preview",
        headers=reviewer_headers,
        files={"file": ("claims.xlsx", excel_bytes.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
    )
    assert res_upload.status_code == 200
    print("PREVIEW ROW ERRORS:", [r.get("validation_errors") for r in res_upload.json().get("rows", [])])
    staged_id = res_upload.json()["id"]

    # 3. Confirm the staged import
    res_confirm = client.post(f"/api/v1/knowledge/import/{staged_id}/confirm", headers=reviewer_headers)
    if res_confirm.status_code != 200:
        print("CONFIRM ERROR DETAIL:", res_confirm.status_code, res_confirm.json())
    assert res_confirm.status_code == 200

    # 4. Verify working database records were updated
    db.expire_all()
    updated_claim = db.query(Claim).filter(Claim.organization_id == org_id, Claim.claim_id == "CLM-002").first()
    assert updated_claim.claim_status == "Prohibited", "Mutable table was updated on confirmation"

    # 5. Verify the active KnowledgeBaseVersion snapshot is STILL v1
    active_kb = db.query(OrganizationActiveKnowledgeBase).filter(
        OrganizationActiveKnowledgeBase.organization_id == org_id
    ).first()
    assert active_kb.active_version_id == v1_id, "Active KB pointer must NOT change on Excel confirmation"

    # 6. Run governance evaluation again
    run_post_confirm = governance_engine.evaluate_content_version(db=db, content_version=content_version)

    # 7. CRITICAL ASSERTION: The governance evaluation uses v1 snapshot, NOT the mutable table!
    assert run_post_confirm.knowledge_base_version_id == v1_id
    post_prohibited_findings = [f for f in run_post_confirm.findings if f.category == "prohibited_claim"]
    assert len(post_prohibited_findings) == 0, (
        "Governance results must NOT change after confirmation before explicit activation! "
        "The claim is Prohibited in mutable tables, but still Approved in v1 snapshot."
    )


def test_b_activation_makes_changes_effective(client, test_setup):
    """
    Scenario B: Changes become effective only after explicit Knowledge Base activation.
    """
    db = test_setup["db"]
    org_id = test_setup["org_id"]
    reviewer_headers = test_setup["reviewer_headers"]
    content_version = test_setup["content_version"]
    v1_id = test_setup["v1_version_id"]

    content_version.body_text = "Valencia Orange is packed with essential nutrients for healthy lifestyle."
    db.commit()

    # Update working table: mark CLM-002 as Prohibited
    claim = db.query(Claim).filter(Claim.organization_id == org_id, Claim.claim_id == "CLM-002").first()
    claim.claim_status = "Prohibited"
    db.commit()

    # Call POST /api/v1/knowledge/activate
    res_act = client.post(
        "/api/v1/knowledge/activate",
        headers=reviewer_headers,
        json={"activation_reason": "Promoting CLM-002 to prohibited status"}
    )
    assert res_act.status_code == 200
    v2_id = res_act.json()["version_id"]
    db.expire_all()
    assert v2_id != v1_id, "New version must be created on activation"

    # Active pointer now points to v2
    db.expire_all()
    active_kb = db.query(OrganizationActiveKnowledgeBase).filter(
        OrganizationActiveKnowledgeBase.organization_id == org_id
    ).first()
    assert active_kb.active_version_id == v2_id

    # Evaluate content version after activation
    run_post_act = governance_engine.evaluate_content_version(db=db, content_version=content_version)
    assert run_post_act.knowledge_base_version_id == v2_id

    # Prohibited claim finding is now triggered because v2 snapshot includes the prohibited status!
    prohibited_findings = [f for f in run_post_act.findings if f.category == "prohibited_claim"]
    assert len(prohibited_findings) > 0, "Prohibited claim must now be flagged after explicit activation"
    assert any("CLM-002" in f.source_citation for f in prohibited_findings)


def test_c_incremental_imports_remain_safe(client, test_setup):
    """
    Scenario C: Incremental imports remain safe. Records omitted from an incremental
    Excel upload remain in the mutable database and appear in subsequent snapshots.
    """
    db = test_setup["db"]
    org_id = test_setup["org_id"]
    reviewer_headers = test_setup["reviewer_headers"]

    # Count products before incremental upload
    initial_product_count = db.query(Product).filter(Product.organization_id == org_id).count()
    assert initial_product_count >= 6, "FreshSip baseline has at least 6 products"

    # Incremental Excel file containing only 1 new product (omitting all existing products)
    excel_bytes = _create_products_excel_bytes(
        products_data=[
            ["FS-PROD-999", "Mango Passion Fruit Punch", "Beverages", "Physical Product", "Tropical fruit press", "Original", "FS-MGO-999", 300, "ml", "Mango, passion fruit", "Real fruit", "100% natural", "None", "IN", "Active"]
        ]
    )

    res_upload = client.post(
        "/api/v1/knowledge/import/product_catalogue/preview",
        headers=reviewer_headers,
        files={"file": ("incremental.xlsx", excel_bytes.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
    )
    assert res_upload.status_code == 200
    print("PREVIEW ROW ERRORS:", [r.get("validation_errors") for r in res_upload.json().get("rows", [])])
    staged_id = res_upload.json()["id"]

    res_confirm = client.post(f"/api/v1/knowledge/import/{staged_id}/confirm", headers=reviewer_headers)
    if res_confirm.status_code != 200:
        print("CONFIRM ERROR DETAIL:", res_confirm.status_code, res_confirm.json())
    assert res_confirm.status_code == 200

    # Verify omitted products were NOT deleted
    db.expire_all()
    new_product_count = db.query(Product).filter(Product.organization_id == org_id).count()
    assert new_product_count == initial_product_count + 1

    # Activate new version
    res_act = client.post(
        "/api/v1/knowledge/activate",
        headers=reviewer_headers,
        json={"activation_reason": "Incremental addition of Mango Punch"}
    )
    assert res_act.status_code == 200
    v3_id = res_act.json()["version_id"]

    # Verify new snapshot contains ALL products (both previous 6+ and new 1)
    v3_ver = db.query(KnowledgeBaseVersion).filter(KnowledgeBaseVersion.id == v3_id).first()
    snapshot_products = v3_ver.manifest_data["products"]
    snapshot_pids = {p["product_id"] for p in snapshot_products}
    assert "FS-PROD-001" in snapshot_pids, "Existing product preserved in snapshot"
    assert "FS-PROD-999" in snapshot_pids, "New product included in snapshot"


def test_d_historical_version_preservation(client, test_setup):
    """
    Scenario D: Historical governance runs and rescoring jobs can reproduce their
    evaluation inputs against specific historical KnowledgeBaseVersion snapshots.
    """
    db = test_setup["db"]
    org_id = test_setup["org_id"]
    reviewer_headers = test_setup["reviewer_headers"]
    content_version = test_setup["content_version"]
    v1_id = test_setup["v1_version_id"]

    claim = db.query(Claim).filter(Claim.organization_id == org_id, Claim.claim_id == "CLM-002").first()
    content_version.body_text = f"Try our beverage: {claim.claim_text}"
    db.commit()

    # Update working table: mark CLM-002 as Prohibited and activate v2
    claim.claim_status = "Prohibited"
    db.commit()

    res_act = client.post(
        "/api/v1/knowledge/activate",
        headers=reviewer_headers,
        json={"activation_reason": "Promoting CLM-002 to prohibited status in v2"}
    )
    assert res_act.status_code == 200
    v2_id = res_act.json()["version_id"]
    db.expire_all()

    # 1. Run evaluation targeting historical v1_id explicitly
    historical_run = governance_engine.evaluate_content_version(
        db=db,
        content_version=content_version,
        knowledge_base_version_id=v1_id
    )
    assert historical_run.knowledge_base_version_id == v1_id
    # In v1, CLM-002 was Approved, so no prohibited claim finding!
    v1_prohibited = [f for f in historical_run.findings if f.category == "prohibited_claim"]
    assert len(v1_prohibited) == 0, "Historical evaluation against v1 must reproduce v1 results"

    # 2. Run evaluation without specifying version (uses active v2)
    active_run = governance_engine.evaluate_content_version(
        db=db,
        content_version=content_version
    )
    assert active_run.knowledge_base_version_id == v2_id
    active_prohibited = [f for f in active_run.findings if f.category == "prohibited_claim"]
    assert len(active_prohibited) > 0, "Current active evaluation must reflect current active snapshot"


def test_e_evaluation_path_consistency(client, test_setup):
    """
    Scenario E: Standard governance evaluation and /live-check produce consistent
    results against the active snapshot.
    """
    creator_headers = test_setup["creator_headers"]
    reviewer_headers = test_setup["reviewer_headers"]
    content_version = test_setup["content_version"]
    db = test_setup["db"]
    org_id = test_setup["org_id"]

    # Mark CLM-002 as Prohibited and activate
    claim = db.query(Claim).filter(Claim.organization_id == org_id, Claim.claim_id == "CLM-002").first()
    claim.claim_status = "Prohibited"
    db.commit()

    res_act = client.post(
        "/api/v1/knowledge/activate",
        headers=reviewer_headers,
        json={"activation_reason": "Activating prohibited claim"}
    )
    assert res_act.status_code == 200

    test_text = "Our juice is packed with essential nutrients."
    content_version.body_text = test_text
    db.commit()

    # 1. Standard governance run via API
    res_run = client.post(
        "/api/v1/governance/run",
        headers=creator_headers,
        json={"content_version_id": content_version.id}
    )
    assert res_run.status_code == 200
    run_data = res_run.json()

    # 2. Live-check via API
    res_live = client.post(
        "/api/v1/knowledge/live-check",
        headers=creator_headers,
        json={"body_text": test_text}
    )
    assert res_live.status_code == 200
    live_data = res_live.json()

    # Both recognize the prohibited claim infraction
    assert any(f["category"] == "prohibited_claim" or "essential nutrients" in f["explanation"].lower() for f in run_data["findings"])
    assert any(inf["category"] == "prohibited_claim" or "essential nutrients" in inf["explanation"].lower() for inf in live_data["infractions"])


def test_f_no_mixed_knowledge_sources(client, test_setup):
    """
    Scenario F: When an active snapshot exists, unactivated records in mutable tables
    are never used. No fallback to mutable tables for missing individual records.
    """
    db = test_setup["db"]
    org_id = test_setup["org_id"]
    content_version = test_setup["content_version"]

    # Directly insert an unactivated prohibited claim into mutable tables
    ghost_claim = Claim(
        organization_id=org_id,
        claim_id="CLM-GHOST-999",
        applicable_product_id="ALL",
        claim_text="Unactivated Phantom Statement",
        claim_status="Prohibited",
        claim_type="Marketing",
        applicable_market="IN",
        effective_from=datetime.utcnow().date()
    )
    db.add(ghost_claim)
    db.commit()

    # Put the phantom statement in the copy
    content_version.body_text = "Here is an Unactivated Phantom Statement in our new copy."
    db.commit()

    # Run governance evaluation
    run = governance_engine.evaluate_content_version(db=db, content_version=content_version)

    # ASSERTION: The ghost claim was NEVER activated into the active snapshot,
    # so it must NOT trigger any finding!
    ghost_findings = [f for f in run.findings if "CLM-GHOST-999" in (f.source_citation or "")]
    assert len(ghost_findings) == 0, (
        "Strict isolation violated: mutable database records must never leak into "
        "governance evaluations without explicit Knowledge Base activation!"
    )


def test_g_tenant_isolation_and_invalid_version_rejection(client, test_setup):
    """
    Scenario G: Security & Tenant Isolation.
    1. Specifying an invalid or foreign target_version_id raises ValueError and never falls back.
    2. API callers on /governance/run cannot bypass the active version by injecting version IDs.
    """
    db = test_setup["db"]
    org_id = test_setup["org_id"]
    creator_headers = test_setup["creator_headers"]
    content_version = test_setup["content_version"]
    v1_id = test_setup["v1_version_id"]

    # 1. Non-existent target_version_id raises ValueError
    with pytest.raises(ValueError, match="does not exist or does not belong to organization"):
        resolve_knowledge_base(db, org_id, target_version_id="non-existent-uuid-12345")

    # 2. Target version belonging to another organization raises ValueError
    fake_other_org_id = "00000000-0000-0000-0000-000000000000"
    with pytest.raises(ValueError, match="does not exist or does not belong to organization"):
        resolve_knowledge_base(db, fake_other_org_id, target_version_id=v1_id)

    # 3. API callers on POST /api/v1/governance/run cannot bypass the active version
    res_run = client.post(
        "/api/v1/governance/run",
        headers=creator_headers,
        json={
            "content_version_id": content_version.id,
            "knowledge_base_version_id": "non-existent-or-bypass-id"
        }
    )
    assert res_run.status_code == 200
    # The run executed against the active baseline, ignoring any injected version selection
    assert res_run.json()["knowledge_base_version_id"] == v1_id
