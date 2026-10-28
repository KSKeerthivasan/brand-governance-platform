import sys
import os
import csv
from datetime import datetime, timedelta
from typing import Optional

# Ensure backend root is on sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.config import settings
from app.database import SessionLocal, engine, Base
from app.models.organization import Organization, User, OrganizationMembership, OrganizationRole
from app.models.brand import Brand
from app.models.knowledge import KnowledgeSource, KnowledgeRule, KnowledgeFact, BrandAsset
from app.models.content import ContentItem, ContentVersion, GovernanceRun, GovernanceFinding, ApprovalSubmission
from app.models.audit import AuditEvent
from app.services.auth import get_password_hash
from app.services.governance_engine import governance_engine
from app.services.audit import log_audit_event

def get_test_assets_path() -> str:
    """Returns absolute path to test_assets/freshsip_inkloom_demo."""
    candidate = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "test_assets", "freshsip_inkloom_demo")
    if os.path.exists(candidate):
        return candidate
    return "./test_assets/freshsip_inkloom_demo"

# Explicit pattern keywords for canonical rules to ensure precise regex matching
RULE_PATTERN_MAP = {
    "FR-RULE-001": r"Pvt\. Ltd\.|Pvt Ltd|Apollo Wellness|Pvt\. Limited",
    "FR-RULE-002": "toxic sludge, poisoning your organs, flush the guilt away, dead food, body-shaming",
    "FR-RULE-003": "hyper-baric non-thermal, bioactive phytonutrient, cellular bioavailability",
    "FR-RULE-004": "miracle juice, miracle, magic elixir, liquid medicine, superfood cure-all, cure-all, magic potion",
    "FR-RULE-005": "sugar-free, zero sugar, 100% sugar-free, 0% sugar, diabetic-safe sugar",
    "FR-RULE-006": "100% raw, completely unprocessed, unprocessed, untreated farm juice",
    "FR-RULE-007": "cures, cure, cures diabetes, lowers blood pressure, treats cancer, prevents infection, clinical therapy",
    "FR-RULE-008": "detox, cleanses liver, flushes toxins, flush toxins, burn fat, belly fat, weight loss, boost immunity, boosts immunity",
    "FR-RULE-009": "rich in iron, 200% daily Vitamin C, 150% of your daily Vitamin, mega-doses of natural enzymes",
    "FR-RULE-010": "100% natural, certified organic, pesticide-free, chemical-free, farm-certified, USDA Organic, USDA Certified Organic",
    "FR-RULE-011": "India's healthiest juice, India's #1, purest juice in India, fresher than any other brand",
    "FR-RULE-012": "doctor recommended, Mumbai cardiologists, National Nutrition Award, clinical-grade",
    "FR-RULE-013": "carbon-neutral, zero-emissions, 100% eco-friendly, planet-saving, 100% recycled glass, ocean-rescued eco-glass",
    "FR-RULE-014": "100% allergen-free",
    "FR-RULE-015": "500 mL, ₹60",
    "FR-RULE-016": "50% OFF, FLAT 50% OFF, FLASH SALE, promo code, only 10 bottles left, only 5 bottles left, DETOX50",
    "FR-RULE-017": "campaign_rejected_detox_claim.png",
    "FR-RULE-018": "pending_review, expired, not_provided",
    "FR-RULE-019": "unaccompanied regional script",
    "FR-RULE-020": "2025 Summer Trio Tasting Pack, Summer Trio Tasting Pack",
    "FR-RULE-021": "competitor price comparison table",
}

RULE_PAGE_MAP = {
    "FR-RULE-001": 1,
    "FR-RULE-002": 2,
    "FR-RULE-003": 2,
    "FR-RULE-004": 3,
    "FR-RULE-005": 3,
    "FR-RULE-006": 3,
    "FR-RULE-007": 3,
    "FR-RULE-008": 3,
    "FR-RULE-009": 3,
    "FR-RULE-010": 4,
    "FR-RULE-011": 4,
    "FR-RULE-012": 4,
    "FR-RULE-013": 4,
    "FR-RULE-014": 5,
    "FR-RULE-015": 5,
    "FR-RULE-016": 5,
    "FR-RULE-017": 6,
    "FR-RULE-018": 7,
    "FR-RULE-019": 3,
    "FR-RULE-020": 5,
    "FR-RULE-021": 7,
}

def check_production_seed_guard():
    """
    Guards against seeding synthetic demo accounts or benchmark test data in production.
    Raises RuntimeError before any database session or table mutation can occur.
    """
    env = (os.environ.get("ENVIRONMENT") or getattr(settings, "ENVIRONMENT", "") or "").strip().lower()
    if env == "production":
        error_msg = (
            "SECURITY ERROR: Demo seeding is strictly prohibited in production environments.\n"
            "Pre-populated demo accounts and synthetic baseline data cannot be seeded into production.\n"
            "To provision an initial organization and administrator safely, use the provisioning command:\n"
            "  python provision_admin.py --org-name <NAME> --org-slug <SLUG> --admin-email <EMAIL> --admin-name <NAME>"
        )
        print(f"\n[BLOCKED] {error_msg}\n", file=sys.stderr)
        raise RuntimeError(error_msg)

def seed_freshsip_data(session=None):
    check_production_seed_guard()
    print("Initializing database tables...")
    Base.metadata.create_all(bind=engine)
    db = session or SessionLocal()
    close_db = session is None

    try:
        print("Checking if Freshsip organization already exists...")
        org = db.query(Organization).filter(Organization.slug == "freshsip").first()
        if not org:
            org = Organization(
                name="Freshsip Beverage Co.",
                slug="freshsip"
            )
            db.add(org)
            db.commit()
            db.refresh(org)
            print(f"Created Organization: {org.name} ({org.id})")
        else:
            print(f"Organization exists: {org.name}")

        # Seed Brand
        brand = db.query(Brand).filter(Brand.organization_id == org.id, Brand.name == "Freshsip").first()
        if not brand:
            brand = Brand(
                organization_id=org.id,
                name="Freshsip",
                description="Bottled fruit juices, vegetable juices, and fruit-and-vegetable juice blends with transparent ingredient labeling (Fictional Demo Brand)"
            )
            db.add(brand)
            db.commit()
            db.refresh(brand)
            print(f"Created Brand: {brand.name}")
        else:
            brand.description = "Bottled fruit juices, vegetable juices, and fruit-and-vegetable juice blends with transparent ingredient labeling (Fictional Demo Brand)"
            db.commit()

        # Seed Users
        demo_password = get_password_hash("Freshsip2026!")
        users_config = [
            ("admin@freshsip.demo", "Alice Administrator", OrganizationRole.ORG_ADMIN),
            ("reviewer@freshsip.demo", "Rachel Reviewer", OrganizationRole.KNOWLEDGE_REVIEWER),
            ("creator@freshsip.demo", "Chris Creator", OrganizationRole.CONTENT_CREATOR),
            ("approver@freshsip.demo", "Marcus Manager", OrganizationRole.APPROVAL_MANAGER),
        ]

        user_map = {}
        for email, full_name, role in users_config:
            user = db.query(User).filter(User.email == email).first()
            if not user:
                user = User(
                    email=email,
                    hashed_password=demo_password,
                    full_name=full_name,
                    is_active=True
                )
                db.add(user)
                db.commit()
                db.refresh(user)
                print(f"Created User: {user.full_name} ({user.email})")

            # Check membership
            mem = db.query(OrganizationMembership).filter(
                OrganizationMembership.organization_id == org.id,
                OrganizationMembership.user_id == user.id
            ).first()
            if not mem:
                mem = OrganizationMembership(
                    organization_id=org.id,
                    user_id=user.id,
                    role=role
                )
                db.add(mem)
                db.commit()
            user_map[role] = user

        # Seed Canonical Knowledge Sources
        source_guidelines = db.query(KnowledgeSource).filter(
            KnowledgeSource.organization_id == org.id,
            KnowledgeSource.filename == "freshsip_brand_guidelines.pdf"
        ).first()
        if not source_guidelines:
            source_guidelines = KnowledgeSource(
                organization_id=org.id,
                brand_id=brand.id,
                title="Freshsip Brand & Marketing Guidelines (Canonical v1.0)",
                source_type="pdf_brand_guidelines",
                filename="freshsip_brand_guidelines.pdf",
                file_path="./storage_data/freshsip/freshsip_brand_guidelines.pdf",
                file_size_bytes=1343613,
                mime_type="application/pdf",
                version=1,
                status="reviewed",
                extracted_summary="Canonical Freshsip brand guidelines: tone of voice, 21 numbered rules (FR-RULE-001 to 021), no-added-sugar standards, prohibited organic/medical claims, pack sizes and verified specifications.",
                uploaded_by=user_map[OrganizationRole.KNOWLEDGE_REVIEWER].id
            )
            db.add(source_guidelines)
            db.commit()
            db.refresh(source_guidelines)
        else:
            source_guidelines.title = "Freshsip Brand & Marketing Guidelines (Canonical v1.0)"
            source_guidelines.extracted_summary = "Canonical Freshsip brand guidelines: tone of voice, 21 numbered rules (FR-RULE-001 to 021), no-added-sugar standards, prohibited organic/medical claims, pack sizes and verified specifications."
            db.commit()

        source_pkb = db.query(KnowledgeSource).filter(
            KnowledgeSource.organization_id == org.id,
            KnowledgeSource.filename == "freshsip_product_knowledge.pdf"
        ).first()
        if not source_pkb:
            source_pkb = KnowledgeSource(
                organization_id=org.id,
                brand_id=brand.id,
                title="Freshsip Product Knowledge & Claim Compendium (Canonical v1.0)",
                source_type="pdf_product_knowledge",
                filename="freshsip_product_knowledge.pdf",
                file_path="./storage_data/freshsip/freshsip_product_knowledge.pdf",
                file_size_bytes=1257990,
                mime_type="application/pdf",
                version=1,
                status="reviewed",
                extracted_summary="Canonical Freshsip product knowledge: 6 SKUs (FS-PROD-001 to FS-PROD-006), standardized nutrition per 100 mL, 250 mL glass bottles, and claim substantiation compendium.",
                uploaded_by=user_map[OrganizationRole.KNOWLEDGE_REVIEWER].id
            )
            db.add(source_pkb)
            db.commit()
            db.refresh(source_pkb)

        # -------------------------------------------------------------
        # STEP 3A: DEPRECATE CONTRADICTORY RULES (Preserving Audit Trails)
        # -------------------------------------------------------------
        contradictory_rules = db.query(KnowledgeRule).filter(
            KnowledgeRule.organization_id == org.id,
            KnowledgeRule.pattern.in_(["USDA Certified Organic", "Zero Added Sugar"])
        ).all()
        for c_rule in contradictory_rules:
            if c_rule.status != "deprecated":
                c_rule.status = "deprecated"
                c_rule.is_corrected = True
                c_rule.review_notes = (
                    "Deprecated in Milestone 1: Directly contradicted authoritative brand guidelines. "
                    "USDA Certified Organic is strictly prohibited by FR-RULE-010 (Section D, p. 4). "
                    "Zero Added Sugar is restricted by FR-RULE-005 (Section C, p. 3) which requires 'No Added Sugar'."
                )
                print(f"Deprecated contradictory rule: {c_rule.title} (ID: {c_rule.id})")
        db.commit()

        # -------------------------------------------------------------
        # STEP 3B: DEPRECATE NON-CANONICAL PRODUCT FACTS ("Freshsip Sparkling Citrus")
        # -------------------------------------------------------------
        ghost_facts = db.query(KnowledgeFact).filter(
            KnowledgeFact.organization_id == org.id,
            KnowledgeFact.product_name == "Freshsip Sparkling Citrus"
        ).all()
        for g_fact in ghost_facts:
            if g_fact.status != "deprecated":
                g_fact.status = "deprecated"
                g_fact.review_notes = (
                    "Deprecated in Milestone 1: Replaced by canonical catalogue SKUs (FS-PROD-001 through FS-PROD-006) "
                    "from freshsip_products.csv."
                )
                print(f"Deprecated non-canonical product fact: {g_fact.fact_key} (ID: {g_fact.id})")
        db.commit()

        # -------------------------------------------------------------
        # STEP 3C: POPULATE CANONICAL RULES (FR-RULE-001 to FR-RULE-021)
        # -------------------------------------------------------------
        assets_dir = get_test_assets_path()
        rules_csv_path = os.path.join(assets_dir, "brand_rules.csv")
        
        if os.path.exists(rules_csv_path):
            with open(rules_csv_path, mode="r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    r_code = row["rule_id"]
                    pattern = RULE_PATTERN_MAP.get(r_code, row["rule_name"])
                    p_num = RULE_PAGE_MAP.get(r_code, 1)
                    r_type = row["rule_type"]
                    # Map canonical types: prohibition -> prohibition, restriction -> restriction, etc.
                    mapped_type = "prohibition" if r_type == "prohibition" else (
                        "restriction" if r_type == "restriction" else (
                            "escalation" if r_type == "escalation" else "requirement"
                        )
                    )

                    existing = db.query(KnowledgeRule).filter(
                        KnowledgeRule.organization_id == org.id,
                        KnowledgeRule.rule_code == r_code
                    ).first()

                    if not existing:
                        rule_obj = KnowledgeRule(
                            organization_id=org.id,
                            brand_id=brand.id,
                            source_id=source_guidelines.id,
                            rule_code=r_code,
                            title=row["rule_name"],
                            rule_type=mapped_type,
                            pattern=pattern,
                            explanation=f"{row['rule_text']} {row['explanation']}",
                            severity=row["severity"],
                            source_citation=f"freshsip_brand_guidelines.pdf, {row['source_section']}, p. {p_num}",
                            status=row["status"],
                            source_status=row["status"],
                            context_condition=row["condition"],
                            scope=row.get("scope", "all_channels"),
                            enforcement_action=row["action_on_match"],
                            rationale=row["explanation"],
                            examples_bad=row.get("example_bad"),
                            examples_good=row.get("example_good"),
                            page_number=p_num,
                            evidence_passage=row["rule_text"],
                            evidence_validation="verified_exact",
                            is_corrected=False,
                            reviewed_by=user_map[OrganizationRole.KNOWLEDGE_REVIEWER].id if row["status"] == "approved" else None,
                            reviewed_at=datetime.utcnow() if row["status"] == "approved" else None
                        )
                        db.add(rule_obj)
                    else:
                        existing.title = row["rule_name"]
                        existing.rule_type = mapped_type
                        existing.pattern = pattern
                        existing.explanation = f"{row['rule_text']} {row['explanation']}"
                        existing.severity = row["severity"]
                        existing.source_citation = f"freshsip_brand_guidelines.pdf, {row['source_section']}, p. {p_num}"
                        existing.status = row["status"]
                        existing.source_status = row["status"]
                        existing.context_condition = row["condition"]
                        existing.scope = row.get("scope", "all_channels")
                        existing.enforcement_action = row["action_on_match"]
                        existing.rationale = row["explanation"]
                        existing.examples_bad = row.get("example_bad")
                        existing.examples_good = row.get("example_good")
                        existing.page_number = p_num
                        existing.evidence_passage = row["rule_text"]
                        existing.evidence_validation = "verified_exact"
            db.commit()
            print("Canonical brand rules populated/updated successfully (21 rules).")

        # -------------------------------------------------------------
        # STEP 3D: POPULATE CANONICAL PRODUCTS & FACTS (freshsip_products.csv)
        # -------------------------------------------------------------
        products_csv_path = os.path.join(assets_dir, "freshsip_products.csv")
        if os.path.exists(products_csv_path):
            with open(products_csv_path, mode="r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    p_id = row["product_id"]
                    p_name = row["product_name"]

                    facts_to_upsert = [
                        ("sugar", row["added_sugar_status"], "nutrition", f"freshsip_product_knowledge.pdf, Section 2 ({p_id}), p. 2"),
                        ("calories", f"{row['nutrition_values']} (Energy kcal)", "nutrition", f"freshsip_product_knowledge.pdf, Section 2 ({p_id}), p. 2"),
                        ("price_inr", f"₹{row['approved_price_inr']} MRP (250 mL glass bottle)", "pricing", f"freshsip_product_knowledge.pdf, Section 2 ({p_id}), p. 2"),
                        ("ingredients", row["ingredients"], "ingredient", f"freshsip_product_knowledge.pdf, Section 2 ({p_id}), p. 2"),
                        ("processing_method", row["processing_method"], "specification", f"freshsip_product_knowledge.pdf, Section 2 ({p_id}), p. 2"),
                        ("allergen_information", row["allergen_information"], "specification", f"freshsip_product_knowledge.pdf, Section 2 ({p_id}), p. 2"),
                        ("pack_size_ml", f"{row['pack_size_ml']} mL", "specification", f"freshsip_product_knowledge.pdf, Section 2 ({p_id}), p. 2"),
                        ("shelf_life", row["shelf_life"], "specification", f"freshsip_product_knowledge.pdf, Section 2 ({p_id}), p. 2"),
                    ]

                    for f_key, f_val, f_cat, f_cite in facts_to_upsert:
                        existing = db.query(KnowledgeFact).filter(
                            KnowledgeFact.organization_id == org.id,
                            KnowledgeFact.product_id == p_id,
                            KnowledgeFact.fact_key == f_key
                        ).first()

                        if not existing:
                            fact_obj = KnowledgeFact(
                                organization_id=org.id,
                                brand_id=brand.id,
                                source_id=source_pkb.id,
                                product_id=p_id,
                                product_name=p_name,
                                category=f_cat,
                                fact_key=f_key,
                                fact_value=f_val,
                                source_citation=f_cite,
                                status=row["status"],
                                source_status=row["status"],
                                value_status="explicitly_stated" if f_val != "not_provided" else "missing_not_provided",
                                page_number=2,
                                evidence_validation="verified_exact",
                                reviewed_by=user_map[OrganizationRole.KNOWLEDGE_REVIEWER].id if row["status"] == "approved" else None,
                                reviewed_at=datetime.utcnow() if row["status"] == "approved" else None
                            )
                            db.add(fact_obj)
                        else:
                            existing.product_name = p_name
                            existing.fact_value = f_val
                            existing.category = f_cat
                            existing.source_citation = f_cite
                            existing.status = row["status"]
                            existing.source_status = row["status"]
                            existing.value_status = "explicitly_stated" if f_val != "not_provided" else "missing_not_provided"
            db.commit()
            print("Canonical product facts populated/updated successfully (6 SKUs).")

        # -------------------------------------------------------------
        # STEP 3E: POPULATE CANONICAL CLAIMS (freshsip_approved_claims.csv)
        # -------------------------------------------------------------
        claims_csv_path = os.path.join(assets_dir, "freshsip_approved_claims.csv")
        if os.path.exists(claims_csv_path):
            with open(claims_csv_path, mode="r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    c_id = row["claim_id"]
                    p_id = row["product_id"]

                    valid_from = None
                    valid_until = None
                    if row["valid_from"] and row["valid_from"] != "not_established":
                        try:
                            valid_from = datetime.strptime(row["valid_from"], "%Y-%m-%d")
                        except Exception:
                            pass
                    if row["valid_until"] and row["valid_until"] not in ("not_established", "not_applicable"):
                        try:
                            valid_until = datetime.strptime(row["valid_until"], "%Y-%m-%d")
                        except Exception:
                            pass

                    existing = db.query(KnowledgeFact).filter(
                        KnowledgeFact.organization_id == org.id,
                        KnowledgeFact.fact_key == c_id
                    ).first()

                    if not existing:
                        claim_fact = KnowledgeFact(
                            organization_id=org.id,
                            brand_id=brand.id,
                            source_id=source_pkb.id,
                            product_id=p_id,
                            product_name=p_id,
                            category=row["claim_category"],
                            fact_key=c_id,
                            fact_value=row["claim_text"],
                            source_citation=f"freshsip_approved_claims.csv, {row['evidence_reference']}",
                            supporting_evidence=row["evidence_summary"],
                            status=row["claim_status"],
                            source_status=row["claim_status"],
                            valid_from=valid_from,
                            valid_until=valid_until,
                            value_status="explicitly_stated" if row["claim_status"] == "approved" else "external_reference_needed",
                            reviewed_by=user_map[OrganizationRole.KNOWLEDGE_REVIEWER].id if row["claim_status"] == "approved" else None,
                            reviewed_at=datetime.utcnow() if row["claim_status"] == "approved" else None
                        )
                        db.add(claim_fact)
                    else:
                        existing.fact_value = row["claim_text"]
                        existing.category = row["claim_category"]
                        existing.status = row["claim_status"]
                        existing.source_status = row["claim_status"]
                        existing.source_citation = f"freshsip_approved_claims.csv, {row['evidence_reference']}"
                        existing.supporting_evidence = row["evidence_summary"]
                        existing.valid_from = valid_from
                        existing.valid_until = valid_until
            db.commit()
            print("Canonical claims populated/updated successfully (13 claims).")

        # -------------------------------------------------------------
        # STEP 3F: POPULATE CANONICAL ASSETS (asset_manifest.csv)
        # -------------------------------------------------------------
        assets_csv_path = os.path.join(assets_dir, "asset_manifest.csv")
        if os.path.exists(assets_csv_path):
            with open(assets_csv_path, mode="r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    a_name = row["asset_name"]
                    a_type = row["asset_type"]
                    f_name = row["filename"]
                    stat = row["approval_status"]
                    f_path = f"./storage_data/freshsip/{f_name}"

                    existing = db.query(BrandAsset).filter(
                        BrandAsset.organization_id == org.id,
                        BrandAsset.asset_name == a_name
                    ).first()

                    if not existing:
                        asset_obj = BrandAsset(
                            organization_id=org.id,
                            brand_id=brand.id,
                            source_id=source_guidelines.id,
                            asset_name=a_name,
                            asset_type=a_type,
                            file_path=f_path,
                            mime_type=row.get("mime_type", "image/png"),
                            width=1080 if "logo" in a_type else 1200,
                            height=1080 if "logo" in a_type else (1200 if a_type == "product_image" else 675),
                            aspect_ratio="1:1" if "logo" in a_type or a_type == "product_image" else "16:9",
                            color_mode="RGB",
                            min_clearance_px=25,
                            status=stat,
                            reviewed_by=user_map[OrganizationRole.KNOWLEDGE_REVIEWER].id if stat == "approved" else None,
                            reviewed_at=datetime.utcnow() if stat == "approved" else None
                        )
                        db.add(asset_obj)
                    else:
                        existing.status = stat
                        existing.asset_type = a_type
            db.commit()
            print("Canonical brand assets populated/updated successfully (14 assets).")

        # -------------------------------------------------------------
        # STEP 3G: SEED CANONICAL COMPLIANT DEMO DRAFT
        # -------------------------------------------------------------
        sample_title = "Valencia Orange Morning Refresh Campaign"
        existing_draft = db.query(ContentItem).filter(
            ContentItem.organization_id == org.id,
            ContentItem.title == sample_title
        ).first()

        if not existing_draft:
            content_item = ContentItem(
                organization_id=org.id,
                brand_id=brand.id,
                created_by=user_map[OrganizationRole.CONTENT_CREATOR].id,
                title=sample_title,
                channel="Social Media",
                current_version_num=1,
                status="draft"
            )
            db.add(content_item)
            db.flush()

            # Canonical compliant marketing copy:
            # - Exact SKU name: Valencia Orange Cold-Pressed Juice
            # - Approved disclosure: 'no added sugar'
            # - Approved MRP: ₹120 in 250 mL glass bottle
            # - Zero prohibited claims, zero unestablished micronutrients
            draft_text = (
                "Start your morning with Freshsip Valencia Orange Cold-Pressed Juice! "
                "Crafted from 100% pressed Valencia oranges and High-Pressure Processed (HPP) with no added sugar. "
                "Packaged in a convenient 250 mL glass bottle at MRP ₹120."
            )

            version = ContentVersion(
                content_item_id=content_item.id,
                version_num=1,
                body_text=draft_text,
                checksum=ContentVersion.calculate_checksum(draft_text),
                created_by=user_map[OrganizationRole.CONTENT_CREATOR].id
            )
            db.add(version)
            db.commit()
            db.refresh(version)

            # Pre-evaluate governance run
            gov_run = governance_engine.evaluate_content_version(
                db=db,
                content_version=version,
                executed_by_user_id=user_map[OrganizationRole.CONTENT_CREATOR].id
            )
            print(f"Created Canonical Sample Draft with {gov_run.findings_count} governance findings (Status: {gov_run.overall_status})")

            log_audit_event(
                db=db,
                organization_id=org.id,
                user_id=user_map[OrganizationRole.CONTENT_CREATOR].id,
                event_type="CANONICAL_BASELINE_SEEDED",
                entity_type="organization",
                entity_id=org.id,
                summary="Seeded canonical Freshsip baseline: 21 brand rules, 6 SKUs, 13 claims, and compliant sample draft",
                details={"status": "ready", "version": "1.0"}
            )

        print("\n=== SUCCESS: Freshsip canonical baseline seeded successfully! ===")
        print("Demo Credentials:")
        print("  Password for all: Freshsip2026!")
        print("  Org Admin:          admin@freshsip.demo")
        print("  Knowledge Reviewer: reviewer@freshsip.demo")
        print("  Content Creator:    creator@freshsip.demo")
        print("  Approval Manager:   approver@freshsip.demo\n")

    finally:
        if close_db:
            db.close()

if __name__ == "__main__":
    seed_freshsip_data()
