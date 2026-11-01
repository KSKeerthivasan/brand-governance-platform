import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pytest
from app.models.organization import Organization, User, OrganizationMembership, OrganizationRole
from app.models.brand import Brand, BrandProfile, BrandColor
from app.models.product import Product
from app.models.claim import Claim, RequiredDisclosure
from app.models.knowledge import KnowledgeBaseVersion, OrganizationActiveKnowledgeBase, KnowledgeRule, KnowledgeFact
from app.models.content import ContentItem, ContentVersion, GovernanceRun, GovernanceFinding
from app.services.governance_engine import governance_engine
from app.services.suggestion_service import suggestion_service

def test_cross_organization_governance_and_suggestion_isolation(db_session=None):
    """
    Verifies that governance_engine and suggestion_service work with two organizations
    containing completely different brands, products, and claims with zero cross-tenant contamination.
    """
    from app.database import SessionLocal
    db = SessionLocal()

    try:
        # 1. Provision Organization 1: Solis Botanical Brews
        org_solis = db.query(Organization).filter(Organization.slug == "solis-botanical-brews").first()
        if not org_solis:
            org_solis = Organization(name="Solis Botanical Brews", slug="solis-botanical-brews")
            db.add(org_solis)
            db.flush()

        solis_brand = db.query(Brand).filter(Brand.organization_id == org_solis.id).first()
        if not solis_brand:
            solis_brand = Brand(organization_id=org_solis.id, name="Solis")
            db.add(solis_brand)
            db.flush()

        solis_profile = db.query(BrandProfile).filter(BrandProfile.organization_id == org_solis.id).first()
        if not solis_profile:
            solis_profile = BrandProfile(
                organization_id=org_solis.id,
                brand_name="Solis",
                brand_description="Artisanal herbal cold infusions and botanical teas.",
                approved_taglines=["Infused by Nature.", "Pure Botanicals."],
                brand_personality=["Sophisticated", "Zen", "Eco-conscious"],
                preferred_tone=["Calm", "Artisanal", "Mindful"],
                preferred_terminology=["Cold-infused", "Wildcrafted", "Botanical infusion"],
                prohibited_terminology=["Miracle drink", "Detox cure", "Toxic sludge"],
                writing_style="Poetic, artisanal and serene",
                primary_heading_font="Playfair Display",
                secondary_body_font="Inter"
            )
            db.add(solis_profile)
            db.flush()

        # Solis Products
        solis_prod = db.query(Product).filter(
            Product.organization_id == org_solis.id,
            Product.product_id == "SOL-PROD-001"
        ).first()
        if not solis_prod:
            solis_prod = Product(
                organization_id=org_solis.id,
                product_id="SOL-PROD-001",
                product_name="Hibiscus Rose Botanical Infusion",
                product_category="Herbal Infusion",
                offering_type="Physical Product",
                product_description="Cold-steeped wild hibiscus flowers with Damask rose water.",
                variant_name="300 mL Amber Bottle",
                sku="HR-300-BOT",
                pack_size=300.0,
                pack_unit="ml",
                applicable_market="India",
                record_status="Active"
            )
            db.add(solis_prod)
            db.flush()

        # Solis Claims
        solis_claim = db.query(Claim).filter(
            Claim.organization_id == org_solis.id,
            Claim.claim_id == "SOL-CLM-001"
        ).first()
        if not solis_claim:
            from datetime import date
            solis_claim = Claim(
                organization_id=org_solis.id,
                claim_id="SOL-CLM-001",
                claim_text="Sustainably wildcrafted hibiscus flowers from certified community reserves.",
                claim_type="Ingredient",
                claim_status="Approved",
                applicable_product_id="SOL-PROD-001",
                product_id=solis_prod.id,
                applicable_market="India",
                effective_from=date(2026, 1, 1)
            )
            db.add(solis_claim)
            db.flush()

        # Solis Rule
        solis_rule = db.query(KnowledgeRule).filter(
            KnowledgeRule.organization_id == org_solis.id,
            KnowledgeRule.rule_code == "SOL-RULE-001"
        ).first()
        if not solis_rule:
            solis_rule = KnowledgeRule(
                organization_id=org_solis.id,
                brand_id=solis_brand.id,
                rule_code="SOL-RULE-001",
                title="Corporate Entity Suffix Prohibition",
                rule_type="prohibition",
                pattern=r"Pvt\. Ltd\.|Pvt Ltd|Enterprises",
                explanation="Always use clean brand name 'Solis' rather than corporate legal entity registration.",
                severity="high",
                status="approved",
                scope="all_channels"
            )
            db.add(solis_rule)
            db.flush()

        db.commit()

        # 2. Get Organization 2: Freshsip
        org_freshsip = db.query(Organization).filter(Organization.slug == "freshsip").first()
        assert org_freshsip is not None, "Freshsip organization must exist"

        freshsip_prods = db.query(Product).filter(Product.organization_id == org_freshsip.id).all()
        freshsip_skus = {p.product_id for p in freshsip_prods}
        assert "FS-PROD-001" in freshsip_skus, "Freshsip must have FS-PROD-001"
        assert "SOL-PROD-001" not in freshsip_skus, "Freshsip must NOT contain Solis products"

        # 3. Test Dynamic Product Detection Isolation
        solis_text = "Try our Hibiscus Rose Botanical Infusion cold-steeped to perfection!"
        detected_under_solis = governance_engine.detect_product_context(
            text=solis_text,
            title="Solis Spring Campaign",
            products=[solis_prod]
        )
        assert detected_under_solis == ["SOL-PROD-001"], f"Expected ['SOL-PROD-001'], got {detected_under_solis}"

        detected_under_freshsip = governance_engine.detect_product_context(
            text=solis_text,
            title="Solis Spring Campaign",
            products=freshsip_prods
        )
        assert detected_under_freshsip == [], f"Freshsip products should NOT detect Solis SKU, got {detected_under_freshsip}"

        # 4. Test Content Item Governance Isolation
        # Create a Solis content item with corporate registration violation
        solis_user = db.query(User).filter(User.email == "creator@solis.demo").first()
        if not solis_user:
            solis_user = User(email="creator@solis.demo", full_name="Solis Creator", hashed_password="dummy")
            db.add(solis_user)
            db.flush()

        solis_item = ContentItem(
            organization_id=org_solis.id,
            brand_id=solis_brand.id,
            created_by=solis_user.id,
            title="Solis Botanical New Launch",
            channel="Social Media",
            current_version_num=1,
            status="draft"
        )
        db.add(solis_item)
        db.flush()

        solis_version = ContentVersion(
            content_item_id=solis_item.id,
            version_num=1,
            body_text="Solis Botanical Enterprises presents our new Hibiscus Rose Botanical Infusion. Drink fresh every day.",
            checksum=ContentVersion.calculate_checksum("Solis Botanical Enterprises presents our new Hibiscus Rose Botanical Infusion. Drink fresh every day."),
            created_by=solis_user.id
        )
        db.add(solis_version)
        db.commit()
        db.refresh(solis_version)

        # Run governance check for Solis
        gov_run_solis = governance_engine.evaluate_content_version(
            db=db,
            content_version=solis_version,
            executed_by_user_id=solis_user.id
        )

        assert gov_run_solis.organization_id == org_solis.id
        assert len(gov_run_solis.findings) > 0
        finding_solis = gov_run_solis.findings[0]

        # Verify source citation references Solis, NOT Freshsip!
        assert "Freshsip" not in (finding_solis.source_citation or ""), f"Found Freshsip in Solis citation: {finding_solis.source_citation}"
        assert "Solis" in (finding_solis.source_citation or ""), f"Expected Solis in citation: {finding_solis.source_citation}"

        # 5. Test Suggestion Generation Isolation
        suggestions_solis = suggestion_service.generate_suggestions_for_run(db=db, run=gov_run_solis)
        assert len(suggestions_solis) > 0
        sug_solis = suggestions_solis[0]

        # Suggestion evidence source must be Solis Brand Guidelines, NOT Freshsip!
        assert "Freshsip" not in (sug_solis.evidence_source or ""), f"Found Freshsip in Solis suggestion evidence: {sug_solis.evidence_source}"
        assert "Solis" in (sug_solis.evidence_source or ""), f"Expected Solis in suggestion evidence: {sug_solis.evidence_source}"
        assert "Solis" in sug_solis.proposed_text, f"Expected Solis in proposed text: {sug_solis.proposed_text}"

        print("\n[PASS]: Cross-organization governance and suggestion isolation verified successfully!")

    finally:
        db.close()

if __name__ == "__main__":
    test_cross_organization_governance_and_suggestion_isolation()
