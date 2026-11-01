import os
import sys
import json
import hashlib
from datetime import datetime, date
from typing import Dict, Any, List

# Ensure backend root is on sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from app.config import settings
from app.models.organization import Organization, User, OrganizationRole
from app.models.brand import Brand, BrandProfile, BrandColor
from app.models.product import Product
from app.models.claim import Claim, RequiredDisclosure
from app.models.knowledge import (
    KnowledgeBaseVersion,
    OrganizationActiveKnowledgeBase,
    BrandAsset,
)
from app.models.content import GovernanceRun

def seed_freshsip_structured_entities(db, org, user_id=None):
    print(f"Seeding structured entities for {org.name} ({org.id})...")

    # ---------------------------------------------------------------------
    # 1. SEED BRAND PROFILE (Input 1 - Sections A, B, D, E)
    # ---------------------------------------------------------------------
    brand_profile = db.query(BrandProfile).filter(BrandProfile.organization_id == org.id).first()
    if not brand_profile:
        brand_profile = BrandProfile(
            organization_id=org.id,
            brand_name="Freshsip",
            brand_description="A fruit beverage brand focused on refreshing, cold-pressed fruit drinks and fruit-and-vegetable juice blends with transparent ingredient labeling.",
            approved_taglines=["Drink Fresh. Live Bold.", "Pure Fruit. Pure Life."],
            brand_personality=["Friendly", "Energetic", "Trustworthy", "Fresh"],
            preferred_tone=["Positive", "Conversational", "Enthusiastic", "Transparent"],
            tones_to_avoid=["Aggressive", "Arrogant", "Fear-inducing", "Pseudoscientific"],
            preferred_terminology=["Fresh", "Cold-Pressed", "Fruit beverage", "Refreshing", "No Added Sugar", "High-Pressure Processed"],
            prohibited_terminology=["Miracle drink", "Guaranteed cure", "Toxic sludge", "Zero sugar", "100% Raw"],
            writing_style="Simple and conversational",
            approved_languages=["en", "hi", "ta"],
            primary_heading_font="Montserrat",
            secondary_body_font="Open Sans",
            additional_approved_fonts=["Lato"],
            typography_instructions="Use bold heading styles and clean, legible body text. Ensure headline-to-body contrast and hierarchy.",
            visual_style=["Minimalist", "Fresh", "Modern"],
            preferred_imagery_style=["Natural lighting", "Real product photography", "Vibrant colors"],
            preferred_backgrounds=["Clean", "Light", "Nature-inspired"],
            visual_styles_to_avoid=["Cluttered layouts", "Excessive effects", "Dark aggressive themes"],
            logo_usage_instructions="Do not stretch, rotate, recolor, or crowd the official brand logo. Maintain minimum 20px clear space."
        )
        db.add(brand_profile)
        db.commit()
        db.refresh(brand_profile)
        print(f"[PASS]: Created Freshsip BrandProfile ({brand_profile.id})")
    else:
        print(f"[INFO]: BrandProfile already exists ({brand_profile.id})")

    # ---------------------------------------------------------------------
    # 2. SEED BRAND COLOR PALETTE (Input 1 - Section C)
    # ---------------------------------------------------------------------
    canonical_colors = [
        ("Forest Green", "Green", "Primary", "#186B42", 24, 107, 66),
        ("Mango Yellow", "Yellow", "Secondary", "#FFC928", 255, 201, 40),
        ("White", "Neutral", "Background", "#FFFFFF", 255, 255, 255),
        ("Charcoal", "Neutral", "Text", "#282828", 40, 40, 40),
        ("Light Green", "Green", "Accent", "#A8D5B5", 168, 213, 181),
    ]

    for c_name, c_fam, c_role, hex_v, r, g, b in canonical_colors:
        existing_col = db.query(BrandColor).filter(
            BrandColor.organization_id == org.id,
            BrandColor.brand_profile_id == brand_profile.id,
            BrandColor.colour_name == c_name
        ).first()

        if not existing_col:
            col_obj = BrandColor(
                organization_id=org.id,
                brand_profile_id=brand_profile.id,
                colour_name=c_name,
                colour_family=c_fam,
                colour_role=c_role,
                hex_value=hex_v,
                rgb_r=r,
                rgb_g=g,
                rgb_b=b
            )
            db.add(col_obj)
    db.commit()
    print(f"[PASS]: Seeded {len(canonical_colors)} canonical brand colors for Freshsip")

    # ---------------------------------------------------------------------
    # 3. SEED PRODUCT CATALOGUE (Input 2 - 15 Columns)
    # ---------------------------------------------------------------------
    canonical_products = [
        {
            "product_id": "FS-PROD-001",
            "product_name": "Valencia Orange Cold-Pressed Juice",
            "product_category": "Fruit Juice",
            "offering_type": "Physical Product",
            "product_description": "Single-ingredient cold-pressed juice pressed from ripe Valencia oranges (100%), High-Pressure Processed (HPP) without heat pasteurization.",
            "variant_name": "250 mL Glass Bottle",
            "sku": "VO-250-HPP",
            "pack_size": 250.0,
            "pack_unit": "ml",
            "ingredients_components": "Valencia Orange Juice (100%)",
            "key_features": "100% Pressed Oranges; High-Pressure Processed (HPP); No Added Preservatives",
            "specifications": "250 mL glass bottle; Cold-pressed",
            "known_limitations": "Keep refrigerated at 2°C to 5°C. Consume within 24 hours of opening.",
            "applicable_market": "India",
            "record_status": "Active"
        },
        {
            "product_id": "FS-PROD-002",
            "product_name": "Pink Guava Pomegranate Nectar",
            "product_category": "Fruit Juice",
            "offering_type": "Physical Product",
            "product_description": "A rich fruit juice blend combining pink guava puree (60%) and pressed pomegranate juice (40%), gently flash pasteurized.",
            "variant_name": "250 mL Glass Bottle",
            "sku": "PG-250-FP",
            "pack_size": 250.0,
            "pack_unit": "ml",
            "ingredients_components": "Pink Guava Puree (60%), Pomegranate Juice (40%)",
            "key_features": "Flash Pasteurized; No Added Sugar; Real Fruit Pulp",
            "specifications": "250 mL glass bottle",
            "known_limitations": "Store in a cool dry place. Refrigerate at 2°C to 5°C after opening.",
            "applicable_market": "India",
            "record_status": "Active"
        },
        {
            "product_id": "FS-PROD-003",
            "product_name": "Garden Tomato Celery Press",
            "product_category": "Vegetable Juice",
            "offering_type": "Physical Product",
            "product_description": "A crisp, savory cold-pressed vegetable juice blend crafted from vine tomatoes (82%), celery stalks (14%), lemon juice, and Pink Himalayan Salt.",
            "variant_name": "250 mL Glass Bottle",
            "sku": "TC-250-HPP",
            "pack_size": 250.0,
            "pack_unit": "ml",
            "ingredients_components": "Tomato Juice (82%), Celery Juice (14%), Lemon Juice (3.7%), Pink Himalayan Salt (0.3%)",
            "key_features": "Savory vegetable blend; High-Pressure Processed (HPP)",
            "specifications": "250 mL glass bottle; Cold-pressed",
            "known_limitations": "Contains Celery (14%). Keep refrigerated at 2°C to 5°C.",
            "applicable_market": "India",
            "record_status": "Active"
        },
        {
            "product_id": "FS-PROD-004",
            "product_name": "Spiced Carrot Beetroot Press",
            "product_category": "Vegetable Juice",
            "offering_type": "Physical Product",
            "product_description": "An earthy vegetable juice blend combining orange carrots (65%), ruby beetroot (30%), ginger juice (3%), and Kala Namak (0.2%).",
            "variant_name": "250 mL Glass Bottle",
            "sku": "CB-250-FP",
            "pack_size": 250.0,
            "pack_unit": "ml",
            "ingredients_components": "Carrot Juice (65%), Beetroot Juice (30%), Ginger Juice (3%), Lemon Juice (1.8%), Black Salt (0.2%)",
            "key_features": "Earthy root vegetable blend; Flash pasteurized",
            "specifications": "250 mL glass bottle",
            "known_limitations": "Store in a cool dry place. Refrigerate after opening.",
            "applicable_market": "India",
            "record_status": "Active"
        },
        {
            "product_id": "FS-PROD-005",
            "product_name": "Green Orchard Cucumber Spinach Blend",
            "product_category": "Fruit-and-Vegetable Blend",
            "offering_type": "Physical Product",
            "product_description": "A refreshing fruit-and-vegetable juice blend made from green apples (55%), cucumber (28%), baby spinach (15%), and lemon juice (2%).",
            "variant_name": "250 mL Glass Bottle",
            "sku": "CS-250-HPP",
            "pack_size": 250.0,
            "pack_unit": "ml",
            "ingredients_components": "Green Apple Juice (55%), Cucumber Juice (28%), Spinach Juice (15%), Lemon Juice (2%)",
            "key_features": "Green cold-pressed blend; High-Pressure Processed (HPP)",
            "specifications": "250 mL glass bottle; Cold-pressed",
            "known_limitations": "Keep refrigerated at 2°C to 5°C. Consume within 24 hours of opening.",
            "applicable_market": "India",
            "record_status": "Active"
        },
        {
            "product_id": "FS-PROD-006",
            "product_name": "Citrus Carrot Ginger Blend",
            "product_category": "Fruit-and-Vegetable Blend",
            "offering_type": "Physical Product",
            "product_description": "A zesty golden blend pairing Valencia orange juice (50%), sweet carrot juice (45%), fresh ginger (3.5%), and lemon (1.5%).",
            "variant_name": "250 mL Glass Bottle",
            "sku": "CG-250-HPP",
            "pack_size": 250.0,
            "pack_unit": "ml",
            "ingredients_components": "Valencia Orange Juice (50%), Carrot Juice (45%), Ginger Juice (3.5%), Lemon Juice (1.5%)",
            "key_features": "Zesty citrus-carrot blend; High-Pressure Processed (HPP)",
            "specifications": "250 mL glass bottle; Cold-pressed",
            "known_limitations": "Keep refrigerated at 2°C to 5°C. Consume within 24 hours of opening.",
            "applicable_market": "India",
            "record_status": "Active"
        }
    ]

    product_id_map: Dict[str, str] = {}
    for p_data in canonical_products:
        p_sku = p_data["product_id"]
        prod_row = db.query(Product).filter(
            Product.organization_id == org.id,
            Product.product_id == p_sku
        ).first()

        if not prod_row:
            prod_row = Product(
                organization_id=org.id,
                **p_data
            )
            db.add(prod_row)
            db.flush()
        product_id_map[p_sku] = prod_row.id

    db.commit()
    print(f"[PASS]: Seeded {len(canonical_products)} canonical products into products table")

    # ---------------------------------------------------------------------
    # 4. SEED CLAIMS REGISTER (Input 3 - 11 Columns)
    # ---------------------------------------------------------------------
    canonical_claims = [
        {
            "claim_id": "CLM-001",
            "applicable_product_id": "FS-PROD-001",
            "claim_text": "Made from 100% cold-pressed Valencia orange juice with no added sugar and no added preservatives.",
            "claim_type": "Ingredient",
            "claim_status": "Approved",
            "approved_variations": "Contains 100% pressed Valencia oranges; 100% orange juice with zero added sugar",
            "restricted_conditions": None,
            "prohibited_variations": "Made with 100% organic oranges; Cures Vitamin C deficiency",
            "applicable_market": "India",
            "effective_from": date(2026, 1, 1),
            "effective_until": date(2027, 12, 31)
        },
        {
            "claim_id": "CLM-002",
            "applicable_product_id": "FS-PROD-002",
            "claim_text": "Crafted from 60% pink guava puree and 40% pomegranate juice, flash pasteurized with no added sugar.",
            "claim_type": "Ingredient",
            "claim_status": "Approved",
            "approved_variations": "60% pink guava and 40% pomegranate nectar with no added sugar",
            "restricted_conditions": None,
            "prohibited_variations": "100% raw juice; Unpasteurized nectar",
            "applicable_market": "India",
            "effective_from": date(2026, 1, 1),
            "effective_until": date(2027, 12, 31)
        },
        {
            "claim_id": "CLM-003",
            "applicable_product_id": "FS-PROD-003",
            "claim_text": "Savory cold-pressed vegetable blend made with 82% tomato juice and 14% celery juice, containing 22 kcal per 100 mL.",
            "claim_type": "Nutritional",
            "claim_status": "Approved",
            "approved_variations": "Cold-pressed tomato and celery juice with 22 calories per 100 mL",
            "restricted_conditions": None,
            "prohibited_variations": "Flushes toxins from liver; Miracle vegetable cure",
            "applicable_market": "India",
            "effective_from": date(2026, 1, 1),
            "effective_until": date(2027, 12, 31)
        },
        {
            "claim_id": "CLM-004",
            "applicable_product_id": "FS-PROD-001",
            "claim_text": "No Added Sugar",
            "claim_type": "Nutritional",
            "claim_status": "Restricted",
            "approved_variations": "Zero added sugar",
            "restricted_conditions": "Mandatory disclosure: Must prominently state that the beverage contains naturally occurring fruit sugars.",
            "prohibited_variations": "Sugar Free; 0% Sugar; Safe for all diabetics without restriction",
            "applicable_market": "India",
            "effective_from": date(2026, 1, 1),
            "effective_until": date(2027, 12, 31)
        },
        {
            "claim_id": "CLM-ALL-001",
            "applicable_product_id": "ALL",
            "claim_text": "Refreshing fruit and vegetable juices bottled in recyclable glass with transparent labeling.",
            "claim_type": "Quality",
            "claim_status": "Approved",
            "approved_variations": "Bottled in glass with transparent ingredients; Refreshing honest fruit drinks",
            "restricted_conditions": None,
            "prohibited_variations": "India's #1 Purest Juice; Clinically superior to all other brands",
            "applicable_market": "India",
            "effective_from": date(2026, 1, 1),
            "effective_until": None
        },
        {
            "claim_id": "CLM-ALL-002",
            "applicable_product_id": "ALL",
            "claim_text": "Cures diabetes, detoxifies liver, and melts belly fat naturally.",
            "claim_type": "Health",
            "claim_status": "Prohibited",
            "approved_variations": None,
            "restricted_conditions": None,
            "prohibited_variations": "Cures chronic disease; Natural medicine; Liquid cure-all; Burns visceral fat",
            "applicable_market": "India",
            "effective_from": date(2026, 1, 1),
            "effective_until": None
        }
    ]

    for c_data in canonical_claims:
        c_code = c_data["claim_id"]
        app_sku = c_data["applicable_product_id"]
        surrogate_pid = product_id_map.get(app_sku) if app_sku != "ALL" else None

        existing_claim = db.query(Claim).filter(
            Claim.organization_id == org.id,
            Claim.claim_id == c_code
        ).first()

        if not existing_claim:
            claim_obj = Claim(
                organization_id=org.id,
                product_id=surrogate_pid,
                **c_data
            )
            db.add(claim_obj)

    db.commit()
    print(f"[PASS]: Seeded {len(canonical_claims)} canonical claims into claims table")

    # ---------------------------------------------------------------------
    # 5. SEED REQUIRED DISCLOSURES (Optional Sheet - 7 Columns)
    # ---------------------------------------------------------------------
    canonical_disclosures = [
        {
            "disclosure_id": "DISC-001",
            "disclosure_text": "Contains naturally occurring fruit and vegetable sugars. Not a low-calorie food.",
            "applicable_product_id": "ALL",
            "applicable_market": "India",
            "applies_when": "When promotional content mentions 'No Added Sugar' or 'Zero Added Sugar'.",
            "effective_from": date(2026, 1, 1),
            "effective_until": None
        },
        {
            "disclosure_id": "DISC-002",
            "disclosure_text": "Allergen Warning: Contains Celery (14%). Manufactured on equipment processing celery stalks.",
            "applicable_product_id": "FS-PROD-003",
            "applicable_market": "India",
            "applies_when": "When marketing Garden Tomato Celery Press across any channel.",
            "effective_from": date(2026, 1, 1),
            "effective_until": None
        }
    ]

    for d_data in canonical_disclosures:
        d_code = d_data["disclosure_id"]
        app_sku = d_data["applicable_product_id"]
        surrogate_pid = product_id_map.get(app_sku) if app_sku != "ALL" else None

        existing_disc = db.query(RequiredDisclosure).filter(
            RequiredDisclosure.organization_id == org.id,
            RequiredDisclosure.disclosure_id == d_code
        ).first()

        if not existing_disc:
            disc_obj = RequiredDisclosure(
                organization_id=org.id,
                product_id=surrogate_pid,
                **d_data
            )
            db.add(disc_obj)

    db.commit()
    print(f"[PASS]: Seeded {len(canonical_disclosures)} required disclosures")

    # ---------------------------------------------------------------------
    # 6. ASSEMBLE IMMUTABLE KNOWLEDGE BASE MANIFEST (v1.0)
    # ---------------------------------------------------------------------
    colors_snapshot = [
        {"name": c.colour_name, "family": c.colour_family, "role": c.colour_role, "hex": c.hex_value, "rgb": [c.rgb_r, c.rgb_g, c.rgb_b]}
        for c in db.query(BrandColor).filter(BrandColor.organization_id == org.id).all()
    ]
    products_snapshot = [
        {"product_id": p.product_id, "name": p.product_name, "category": p.product_category, "sku": p.sku, "price_inr": float(p.pack_size or 0)}
        for p in db.query(Product).filter(Product.organization_id == org.id).all()
    ]
    claims_snapshot = [
        {"claim_id": c.claim_id, "applicable_product_id": c.applicable_product_id, "claim_text": c.claim_text, "status": c.claim_status, "type": c.claim_type}
        for c in db.query(Claim).filter(Claim.organization_id == org.id).all()
    ]
    disclosures_snapshot = [
        {"disclosure_id": d.disclosure_id, "applicable_product_id": d.applicable_product_id, "text": d.disclosure_text, "applies_when": d.applies_when}
        for d in db.query(RequiredDisclosure).filter(RequiredDisclosure.organization_id == org.id).all()
    ]

    manifest_dict = {
        "version_num": 1,
        "organization_id": org.id,
        "organization_slug": org.slug,
        "brand_profile": {
            "brand_name": brand_profile.brand_name,
            "description": brand_profile.brand_description,
            "personality": brand_profile.brand_personality,
            "preferred_tone": brand_profile.preferred_tone,
            "tones_to_avoid": brand_profile.tones_to_avoid,
            "preferred_terminology": brand_profile.preferred_terminology,
            "prohibited_terminology": brand_profile.prohibited_terminology,
            "heading_font": brand_profile.primary_heading_font,
            "body_font": brand_profile.secondary_body_font,
            "languages": brand_profile.approved_languages
        },
        "brand_colors": colors_snapshot,
        "products": products_snapshot,
        "claims": claims_snapshot,
        "required_disclosures": disclosures_snapshot,
        "created_at": datetime.utcnow().isoformat()
    }

    manifest_json = json.dumps(manifest_dict, sort_keys=True)
    manifest_sha256 = hashlib.sha256(manifest_json.encode("utf-8")).hexdigest()

    kb_v1 = db.query(KnowledgeBaseVersion).filter(
        KnowledgeBaseVersion.organization_id == org.id,
        KnowledgeBaseVersion.version_num == 1
    ).first()

    if not kb_v1:
        kb_v1 = KnowledgeBaseVersion(
            organization_id=org.id,
            version_num=1,
            manifest_sha256=manifest_sha256,
            manifest_data=manifest_dict,
            activated_by=user_id,
            activation_reason="Initial canonical Freshsip knowledge base activation (v1.0 baseline)"
        )
        db.add(kb_v1)
        db.commit()
        db.refresh(kb_v1)
        print(f"[PASS]: Created KnowledgeBaseVersion v1 with SHA-256: {manifest_sha256[:16]}...")
    else:
        print(f"[INFO]: KnowledgeBaseVersion v1 already exists ({kb_v1.id})")

    # ---------------------------------------------------------------------
    # 7. UPDATE ACTIVE KNOWLEDGE BASE POINTER
    # ---------------------------------------------------------------------
    active_kb = db.query(OrganizationActiveKnowledgeBase).filter(
        OrganizationActiveKnowledgeBase.organization_id == org.id
    ).first()

    if not active_kb:
        active_kb = OrganizationActiveKnowledgeBase(
            organization_id=org.id,
            active_version_id=kb_v1.id,
            activated_by=user_id
        )
        db.add(active_kb)
    else:
        active_kb.active_version_id = kb_v1.id
        active_kb.activated_at = datetime.utcnow()
    db.commit()
    print(f"[PASS]: Set OrganizationActiveKnowledgeBase for Freshsip to version {kb_v1.version_num}")

    # ---------------------------------------------------------------------
    # 8. ASSOCIATE HISTORICAL FRESHSIP RUNS
    # ---------------------------------------------------------------------
    runs_updated = db.query(GovernanceRun).filter(
        GovernanceRun.organization_id == org.id,
        GovernanceRun.baseline_status == "legacy_unversioned"
    ).update(
        {
            "knowledge_base_version_id": kb_v1.id,
            "baseline_status": "seeded_baseline_v1"
        },
        synchronize_session=False
    )
    db.commit()
    print(f"[PASS]: Associated {runs_updated} historical Freshsip governance runs with v1 manifest baseline")
    return kb_v1

def run_seed_structured_entities():
    print("Connecting to database for Task 1.2 structured seed migration...")
    engine = create_engine(settings.DATABASE_URL)
    Session = sessionmaker(bind=engine)
    db = Session()
    try:
        org = db.query(Organization).filter(Organization.slug == "freshsip").first()
        if not org:
            print("ERROR: Freshsip organization not found! Run base seed first.")
            return
        reviewer_user = db.query(User).filter(User.email == "reviewer@freshsip.demo").first()
        admin_user = db.query(User).filter(User.email == "admin@freshsip.demo").first()
        user_id = (reviewer_user or admin_user).id if (reviewer_user or admin_user) else None

        seed_freshsip_structured_entities(db, org, user_id)
        print("\n========================================================")
        print("TASK 1.2 STRUCTURED SEED MIGRATION COMPLETED SUCCESSFULLY!")
        print("========================================================")
    finally:
        db.close()

if __name__ == "__main__":
    run_seed_structured_entities()
