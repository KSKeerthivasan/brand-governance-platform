import sys
import os
from datetime import datetime, timedelta

# Ensure backend root is on sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database import SessionLocal, engine, Base
from app.models.organization import Organization, User, OrganizationMembership, OrganizationRole
from app.models.brand import Brand
from app.models.knowledge import KnowledgeSource, KnowledgeRule, KnowledgeFact, BrandAsset
from app.models.content import ContentItem, ContentVersion, GovernanceRun, GovernanceFinding, ApprovalSubmission
from app.models.audit import AuditEvent
from app.services.auth import get_password_hash
from app.services.governance_engine import governance_engine
from app.services.audit import log_audit_event

def seed_freshsip_data(session=None):
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
                description="Organic sparkling botanicals and clean energy beverages (Fictional Demo Brand)"
            )
            db.add(brand)
            db.commit()
            db.refresh(brand)
            print(f"Created Brand: {brand.name}")

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

        # Seed Knowledge Source Container
        source = db.query(KnowledgeSource).filter(
            KnowledgeSource.organization_id == org.id,
            KnowledgeSource.filename == "freshsip_brand_guidelines.pdf"
        ).first()
        if not source:
            source = KnowledgeSource(
                organization_id=org.id,
                brand_id=brand.id,
                title="Freshsip Brand & Marketing Guidelines (Synthetic Demo)",
                source_type="pdf_brand_guidelines",
                filename="freshsip_brand_guidelines.pdf",
                file_path="./storage_data/freshsip/freshsip_brand_guidelines.pdf",
                file_size_bytes=425600,
                mime_type="application/pdf",
                version=1,
                status="reviewed",
                extracted_summary="Comprehensive guidelines on tone, prohibited medical terminology, mandatory organic badges, and product nutrition facts.",
                uploaded_by=user_map[OrganizationRole.KNOWLEDGE_REVIEWER].id
            )
            db.add(source)
            db.commit()
            db.refresh(source)

        # Seed Approved & Pending Knowledge Rules
        rules_data = [
            # Approved Rules
            ("prohibited_word", "Prohibited: 'miracle'", "miracle", "Consumer beverages must never claim miracle health outcomes.", "critical", "freshsip_brand_guidelines.pdf, p. 4", "approved"),
            ("prohibited_word", "Prohibited: 'cure'", "cure", "Consumer beverages must never be described as medical or clinical cures.", "critical", "freshsip_brand_guidelines.pdf, p. 4", "approved"),
            ("prohibited_word", "Prohibited: '100% chemical free'", "100% chemical free", "Scientifically inaccurate claim under advertising standards.", "critical", "freshsip_brand_guidelines.pdf, p. 5", "approved"),
            ("required_term", "Mandatory Term: 'Zero Added Sugar'", "Zero Added Sugar", "All promotional copy must explicitly state 'Zero Added Sugar'.", "warning", "freshsip_brand_guidelines.pdf, p. 8", "approved"),
            ("required_term", "Mandatory Term: 'USDA Certified Organic'", "USDA Certified Organic", "Certified status must be stated in main product communications.", "warning", "freshsip_brand_guidelines.pdf, p. 8", "approved"),
            # Pending Rule (To demonstrate human review queue)
            ("prohibited_word", "Candidate Prohibited: 'unmatched'", "unmatched", "Candidate extracted rule: Avoid unsubstantiated superiority adjectives.", "info", "freshsip_brand_guidelines.pdf, p. 11", "pending_review"),
        ]

        for r_type, title, pat, expl, sev, cite, stat in rules_data:
            existing_rule = db.query(KnowledgeRule).filter(
                KnowledgeRule.organization_id == org.id,
                KnowledgeRule.pattern == pat
            ).first()
            if not existing_rule:
                rule_obj = KnowledgeRule(
                    organization_id=org.id,
                    brand_id=brand.id,
                    source_id=source.id,
                    rule_type=r_type,
                    title=title,
                    pattern=pat,
                    explanation=expl,
                    severity=sev,
                    source_citation=cite,
                    status=stat,
                    reviewed_by=user_map[OrganizationRole.KNOWLEDGE_REVIEWER].id if stat == "approved" else None,
                    reviewed_at=datetime.utcnow() if stat == "approved" else None
                )
                db.add(rule_obj)
        db.commit()

        # Seed Product Facts
        facts_data = [
            # Approved Facts
            ("Freshsip Sparkling Citrus", "nutrition", "sugar", "0g added sugar", "freshsip_product_knowledge.pdf, p. 2", "approved", None),
            ("Freshsip Sparkling Citrus", "nutrition", "calories", "15 calories", "freshsip_product_knowledge.pdf, p. 2", "approved", None),
            ("Freshsip Sparkling Citrus", "certification", "organic_certification", "USDA Certified Organic", "freshsip_product_knowledge.pdf, p. 1", "approved", None),
            ("Freshsip Sparkling Citrus", "ingredient", "caffeine", "45mg green tea caffeine", "freshsip_product_knowledge.pdf, p. 2", "approved", None),
            # Pending Fact (Unapproved claim)
            ("Freshsip Sparkling Citrus", "claim", "immunity", "triples natural immune defense", "freshsip_product_knowledge.pdf, p. 7", "pending_review", None),
            # Expired Fact
            ("Freshsip Sparkling Citrus", "pricing", "launch_discount", "50% early bird special", "freshsip_product_knowledge.pdf, p. 12", "expired", datetime.utcnow() - timedelta(days=30)),
        ]

        for p_name, cat, k, v, cite, stat, until in facts_data:
            existing_fact = db.query(KnowledgeFact).filter(
                KnowledgeFact.organization_id == org.id,
                KnowledgeFact.fact_key == k
            ).first()
            if not existing_fact:
                fact_obj = KnowledgeFact(
                    organization_id=org.id,
                    brand_id=brand.id,
                    source_id=source.id,
                    product_name=p_name,
                    category=cat,
                    fact_key=k,
                    fact_value=v,
                    source_citation=cite,
                    status=stat,
                    valid_until=until,
                    reviewed_by=user_map[OrganizationRole.KNOWLEDGE_REVIEWER].id if stat == "approved" else None,
                    reviewed_at=datetime.utcnow() if stat == "approved" else None
                )
                db.add(fact_obj)
        db.commit()

        # Seed Brand Assets
        assets_data = [
            ("Freshsip Primary Logo", "logo", "./storage_data/freshsip/logo.png", 1080, 1080, "1:1", "RGB", 24, "approved"),
            ("Freshsip Sparkling Citrus Can", "product_image", "./storage_data/freshsip/citrus_can.png", 1200, 1200, "1:1", "RGB", 16, "approved"),
            ("Summer Campaign Banner", "campaign_creative", "./storage_data/freshsip/summer_banner.png", 1200, 675, "16:9", "RGB", 16, "pending_review"),
        ]
        for a_name, a_type, f_path, w, h, ratio, mode, clr, stat in assets_data:
            existing_asset = db.query(BrandAsset).filter(
                BrandAsset.organization_id == org.id,
                BrandAsset.asset_name == a_name
            ).first()
            if not existing_asset:
                asset_obj = BrandAsset(
                    organization_id=org.id,
                    brand_id=brand.id,
                    source_id=source.id,
                    asset_name=a_name,
                    asset_type=a_type,
                    file_path=f_path,
                    mime_type="image/png",
                    width=w,
                    height=h,
                    aspect_ratio=ratio,
                    color_mode=mode,
                    min_clearance_px=clr,
                    status=stat,
                    reviewed_by=user_map[OrganizationRole.KNOWLEDGE_REVIEWER].id if stat == "approved" else None,
                    reviewed_at=datetime.utcnow() if stat == "approved" else None
                )
                db.add(asset_obj)
        db.commit()

        # Seed Sample Draft with Deterministic Findings for Chris Creator
        sample_title = "Summer Energy Campaign Launch"
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

            # Draft text with deterministic findings:
            # - Prohibited: 'miracle'
            # - Prohibited: 'cures'
            # - Product mismatch: '20g sugar' vs approved '0g added sugar'
            # - Unsupported claim: 'guaranteed rapid weight loss'
            # - Missing mandatory: 'Zero Added Sugar'
            draft_text = (
                "Introducing Freshsip Sparkling Citrus! It's a miracle afternoon pick-me-up that cures all fatigue. "
                "Packed with clean taste, 20g sugar, and guaranteed rapid weight loss results! "
                "Crafted with USDA Certified Organic botanicals."
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

            # Pre-evaluate governance run so findings are immediately visible in the demo
            gov_run = governance_engine.evaluate_content_version(
                db=db,
                content_version=version,
                executed_by_user_id=user_map[OrganizationRole.CONTENT_CREATOR].id
            )
            print(f"Created Sample Draft with {gov_run.findings_count} governance findings (Status: {gov_run.overall_status})")

            log_audit_event(
                db=db,
                organization_id=org.id,
                user_id=user_map[OrganizationRole.CONTENT_CREATOR].id,
                event_type="DEMO_SEEDED",
                entity_type="organization",
                entity_id=org.id,
                summary="Seeded synthetic Freshsip demo organization, approved knowledge base, and sample marketing draft",
                details={"status": "ready"}
            )

        print("\n=== SUCCESS: Freshsip synthetic demo data seeded successfully! ===")
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
