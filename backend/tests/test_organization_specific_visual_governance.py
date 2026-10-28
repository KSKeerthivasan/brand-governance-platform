import os
import pytest
from PIL import Image
from app.models.organization import Organization, User, OrganizationMembership, OrganizationRole
from app.models.brand import Brand
from app.models.knowledge import KnowledgeRule, KnowledgeFact, BrandAsset
from app.models.content import ContentItem, ContentVersion
from app.services.governance_engine import governance_engine
from app.services.image_governance import image_governance

def test_missing_palette_returns_unable_to_verify_without_freshsip_fallback(db_session=None):
    """
    Verify that an organization without approved color rules returns 'unable_to_verify'
    rather than silently falling back to Freshsip's Forest Green and Citrus Orange.
    """
    from app.database import SessionLocal
    db = SessionLocal()
    try:
        # Create a new isolated organization
        org = Organization(name="Verdant Tea Co.", slug="verdant-tea")
        db.add(org)
        db.flush()

        brand = Brand(organization_id=org.id, name="Verdant Pure")
        db.add(brand)
        db.flush()

        # Create a test poster image (solid blue)
        test_img_path = "./test_verdant_poster.png"
        img = Image.new("RGB", (1080, 1080), color="#1E3A8A")
        img.save(test_img_path)

        # Evaluate poster with NO approved color rules
        findings = image_governance.evaluate_poster_for_governance(
            file_path=test_img_path,
            channel="Instagram Post",
            alt_text="Verdant Pure iced tea bottle on a wooden outdoor table",
            org_id=org.id,
            db=db,
            brand_id=brand.id
        )

        color_findings = [f for f in findings if f.category == "colour"]
        assert len(color_findings) == 1
        cf = color_findings[0]
        assert cf.status == "unable_to_verify"
        assert "Unable to verify against the supplied guidelines; needs user review" in cf.explanation
        assert "No approved brand color palette rules found" in cf.explanation
        # Ensure Freshsip colors are NOT in the finding
        assert "Forest Green" not in cf.explanation
        assert "#1B4332" not in cf.explanation

        # Logo finding: since no approved logo is uploaded, must also return unable_to_verify
        logo_findings = [f for f in findings if f.category == "logo"]
        assert len(logo_findings) == 1
        lf = logo_findings[0]
        assert lf.status == "unable_to_verify"
        assert "Unable to verify against the supplied guidelines; needs user review" in lf.explanation

    finally:
        db.rollback()
        db.close()
        if os.path.exists("./test_verdant_poster.png"):
            os.remove("./test_verdant_poster.png")


def test_organization_approved_color_palette_is_used():
    """
    Verify that when an organization defines its own approved brand colors,
    the poster is evaluated against those exact colors.
    """
    from app.database import SessionLocal
    db = SessionLocal()
    try:
        org = Organization(name="Azure Spirits Co.", slug="azure-spirits")
        db.add(org)
        db.flush()

        brand = Brand(organization_id=org.id, name="Azure Botanicals")
        db.add(brand)
        db.flush()

        # Define custom approved color rule for Azure Spirits
        color_rule = KnowledgeRule(
            organization_id=org.id,
            brand_id=brand.id,
            rule_type="image_standard",
            rule_code="AZ-RULE-005",
            title="Azure Brand Color Palette Guidelines",
            pattern="Deep Sapphire #0F172A and Bright Cerulean #0284C7",
            explanation="Approved brand palette requires Deep Sapphire (#0F172A) and Bright Cerulean (#0284C7).",
            severity="warning",
            source_citation="Azure Spirits Guidelines v1.0, p. 14",
            status="approved"
        )
        db.add(color_rule)
        db.flush()

        # Create a poster matching Azure's approved Cerulean color
        test_img_path = "./test_azure_poster.png"
        img = Image.new("RGB", (1080, 1080), color="#0284C7")
        img.save(test_img_path)

        findings = image_governance.evaluate_poster_for_governance(
            file_path=test_img_path,
            channel="Instagram Post",
            alt_text="Azure Botanicals chilled craft bottle with water droplets",
            org_id=org.id,
            db=db,
            brand_id=brand.id
        )

        color_findings = [f for f in findings if f.category == "colour"]
        assert len(color_findings) == 1
        cf = color_findings[0]
        assert cf.status == "passed_check"
        assert "Approved Brand Palette Alignment Verified" in cf.title
        assert "#0284C7" in cf.explanation
        assert cf.source_citation == "Azure Spirits Guidelines v1.0, p. 14"
        assert cf.matched_rule_id == color_rule.id

    finally:
        db.rollback()
        db.close()
        if os.path.exists("./test_azure_poster.png"):
            os.remove("./test_azure_poster.png")


def test_logo_matching_requires_approved_status_and_enforces_brand_isolation():
    """
    Verify:
    1. Pending/unapproved logo asset is NOT matched (returns unable_to_verify).
    2. Once approved, logo matching uses the organization's approved logo.
    3. Logo rule is dynamically cited rather than hardcoded to FR-RULE-017.
    """
    from app.database import SessionLocal
    db = SessionLocal()
    try:
        org = Organization(name="Horizon Roasters", slug="horizon-roasters")
        db.add(org)
        db.flush()

        brand_a = Brand(organization_id=org.id, name="Horizon Coffee")
        brand_b = Brand(organization_id=org.id, name="Zenith Teas")
        db.add_all([brand_a, brand_b])
        db.flush()

        # Create logo image file
        logo_img_path = "./test_horizon_logo.png"
        logo_img = Image.new("RGB", (100, 100), color="#F59E0B")
        logo_img.save(logo_img_path)

        # Upload as BrandAsset with status='pending_review' for Brand A
        pending_logo = BrandAsset(
            organization_id=org.id,
            brand_id=brand_a.id,
            asset_name="horizon_logo.png",
            asset_type="logo",
            file_path=logo_img_path,
            mime_type="image/png",
            status="pending_review"  # Not yet approved!
        )
        db.add(pending_logo)
        db.flush()

        # Create a poster containing the logo
        poster_img_path = "./test_horizon_poster.png"
        poster_img = Image.new("RGB", (1080, 1080), color="#1E293B")
        poster_img.paste(logo_img, (50, 50))
        poster_img.save(poster_img_path)

        # 1. Evaluate Brand A with pending logo: should be unable_to_verify because logo is not approved
        findings_pending = image_governance.evaluate_poster_for_governance(
            file_path=poster_img_path,
            channel="Instagram Post",
            alt_text="Fresh dark roast bag beside steaming ceramic mug",
            org_id=org.id,
            db=db,
            brand_id=brand_a.id
        )
        lf_pending = [f for f in findings_pending if f.category == "logo"][0]
        assert lf_pending.status == "unable_to_verify"
        assert "No approved official brand logo reference asset is uploaded" in lf_pending.explanation

        # 2. Approve the logo asset and add an organization-specific logo policy
        pending_logo.status = "approved"
        logo_rule = KnowledgeRule(
            organization_id=org.id,
            brand_id=brand_a.id,
            rule_type="asset_policy",
            rule_code="HZ-RULE-009",
            title="Horizon Official Logo Placement",
            pattern="Horizon Brand Logo",
            explanation="Must display the approved Horizon emblem on all digital posts.",
            source_citation="Horizon Brand Manual 2026, p. 8",
            status="approved"
        )
        db.add(logo_rule)
        db.flush()

        # Re-evaluate Brand A: should now detect the logo
        findings_approved = image_governance.evaluate_poster_for_governance(
            file_path=poster_img_path,
            channel="Instagram Post",
            alt_text="Fresh dark roast bag beside steaming ceramic mug",
            org_id=org.id,
            db=db,
            brand_id=brand_a.id
        )
        lf_approved = [f for f in findings_approved if f.category == "logo"][0]
        assert lf_approved.status == "passed_check"
        assert "Official Brand Logo Placement Verified" in lf_approved.title
        assert lf_approved.source_citation == "Horizon Brand Manual 2026, p. 8"
        assert lf_approved.matched_rule_id == logo_rule.id

        # 3. Brand Isolation: Evaluate Brand B (Zenith Teas)
        # Brand B does NOT have an approved logo, so it must return unable_to_verify
        findings_brand_b = image_governance.evaluate_poster_for_governance(
            file_path=poster_img_path,
            channel="Instagram Post",
            alt_text="Fresh green tea leaves in porcelain bowl",
            org_id=org.id,
            db=db,
            brand_id=brand_b.id
        )
        lf_brand_b = [f for f in findings_brand_b if f.category == "logo"][0]
        assert lf_brand_b.status == "unable_to_verify"
        assert "No approved official brand logo reference asset is uploaded" in lf_brand_b.explanation

    finally:
        db.rollback()
        db.close()
        for p in ["./test_horizon_logo.png", "./test_horizon_poster.png"]:
            if os.path.exists(p):
                os.remove(p)
