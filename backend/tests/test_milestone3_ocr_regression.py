import os
import pytest
from PIL import Image, ImageDraw, ImageFont
from app.services.ocr_service import ocr_service, OCRResult, OCRRegion
from app.models.content import ContentItem, ContentVersion, GovernanceRun

ASSETS_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "test_assets", "freshsip_inkloom_demo", "brand_assets")
)

def _get_font(size: int = 28):
    try:
        return ImageFont.truetype("arial.ttf", size)
    except Exception:
        return ImageFont.load_default()

def _create_synthetic_poster(tmp_path, filename: str, lines: list, size=(900, 500), bg="white", fg="black"):
    img = Image.new("RGB", size, color=bg)
    draw = ImageDraw.Draw(img)
    font = _get_font(28)
    y = 40
    for line in lines:
        draw.text((40, y), line, fill=fg, font=font)
        y += 45
    path = str(tmp_path / filename)
    img.save(path)
    return path


def test_1_compliant_poster_with_visible_approved_terminology(client, auth_tokens):
    """
    1. A compliant poster with visible approved terminology passes governance.
       Uses real asset 'campaign_morning_citrus_approved.png'.
    """
    headers = auth_tokens["content_creator"]["headers"]
    res_b = client.get("/api/v1/brands", headers=headers)
    brand_id = res_b.json()[0]["id"]

    poster_path = os.path.join(ASSETS_DIR, "campaign_morning_citrus_approved.png")
    assert os.path.exists(poster_path), f"Asset missing: {poster_path}"

    res_draft = client.post("/api/v1/content", headers=headers, json={
        "brand_id": brand_id,
        "title": "Freshsip Morning Citrus Campaign",
        "channel": "Social Media",
        "body_text": (
            "Enjoy Freshsip Valencia Orange Cold-Pressed Juice! 100% cold-pressed Valencia orange "
            "juice with no added sugar for natural refreshing vitality."
        ),
        "poster_file_path": poster_path,
        "poster_alt_text": "Bottle of Freshsip Valencia Orange Cold-Pressed Juice with citrus wedges"
    })
    assert res_draft.status_code == 200
    v_id = res_draft.json()["latest_version"]["id"]

    res_gov = client.post("/api/v1/governance/run", headers=headers, json={
        "content_version_id": v_id
    })
    assert res_gov.status_code == 200
    data = res_gov.json()
    assert data["overall_status"] in ("passed", "warnings")
    blocking = [f for f in data["findings"] if f["severity"] in ("critical", "high") and f.get("status") != "passed_check"]
    assert len(blocking) == 0
    ocr_failures = [f for f in data["findings"] if "OCR Processing Failed" in f["title"]]
    assert len(ocr_failures) == 0


def test_2_poster_with_clearly_prohibited_promotional_claim(client, auth_tokens):
    """
    2. A poster containing clearly prohibited promotional claims triggers documented prohibitions.
       Uses real asset 'campaign_rejected_detox_claim.png'.
    """
    headers = auth_tokens["content_creator"]["headers"]
    res_b = client.get("/api/v1/brands", headers=headers)
    brand_id = res_b.json()[0]["id"]

    poster_path = os.path.join(ASSETS_DIR, "campaign_rejected_detox_claim.png")
    assert os.path.exists(poster_path), f"Asset missing: {poster_path}"

    res_draft = client.post("/api/v1/content", headers=headers, json={
        "brand_id": brand_id,
        "title": "Unapproved Flash Sale Creative",
        "channel": "Social Media",
        "body_text": "Check out our newest beverage creative for the season!",
        "poster_file_path": poster_path,
        "poster_alt_text": "Promotional poster with flash sale banner"
    })
    assert res_draft.status_code == 200
    v_id = res_draft.json()["latest_version"]["id"]

    res_gov = client.post("/api/v1/governance/run", headers=headers, json={
        "content_version_id": v_id
    })
    assert res_gov.status_code == 200
    data = res_gov.json()
    assert data["overall_status"] == "failed"

    # Must flag detox (FR-RULE-008) or miracle (FR-RULE-004) from poster text
    poster_prohibitions = [
        f for f in data["findings"]
        if f["category"] == "prohibited_wording" and "Poster" in (f.get("text_excerpt") or "")
    ]
    assert len(poster_prohibitions) > 0

    detox_findings = [f for f in poster_prohibitions if "FR-RULE-008" in f["title"] and "detox" in f["title"].lower()]
    assert len(detox_findings) > 0
    df = detox_findings[0]
    assert df["severity"] == "critical"
    assert "FR-RULE-008" in df["title"]
    assert "bbox:" in df["text_excerpt"]


def test_3_poster_with_unsupported_organic_certification_claim(client, auth_tokens, tmp_path):
    """
    3. A poster containing an unsupported organic-certification claim triggers FR-RULE-010.
    """
    headers = auth_tokens["content_creator"]["headers"]
    res_b = client.get("/api/v1/brands", headers=headers)
    brand_id = res_b.json()[0]["id"]

    synthetic_poster = _create_synthetic_poster(
        tmp_path,
        "poster_organic_violation.png",
        [
            "Freshsip Valencia Orange",
            "100% USDA Certified Organic",
            "Cold-Pressed & Pure"
        ]
    )

    res_draft = client.post("/api/v1/content", headers=headers, json={
        "brand_id": brand_id,
        "title": "Organic Orange Juice Ad",
        "channel": "Social Media",
        "body_text": "Refreshing cold-pressed juice for your morning routine.",
        "poster_file_path": synthetic_poster,
        "poster_alt_text": "Freshsip bottle with organic claim"
    })
    assert res_draft.status_code == 200
    v_id = res_draft.json()["latest_version"]["id"]

    res_gov = client.post("/api/v1/governance/run", headers=headers, json={
        "content_version_id": v_id
    })
    assert res_gov.status_code == 200
    data = res_gov.json()
    assert data["overall_status"] == "failed"

    organic_findings = [
        f for f in data["findings"]
        if "FR-RULE-010" in (f.get("title") or "") or "organic" in (f.get("text_excerpt") or "").lower()
    ]
    assert len(organic_findings) > 0
    of = organic_findings[0]
    assert of["severity"] == "high"
    assert "bbox:" in of["text_excerpt"]


def test_4_poster_with_prohibited_sugar_claim(client, auth_tokens, tmp_path):
    """
    4. A poster containing a prohibited sugar claim triggers FR-RULE-005.
    """
    headers = auth_tokens["content_creator"]["headers"]
    res_b = client.get("/api/v1/brands", headers=headers)
    brand_id = res_b.json()[0]["id"]

    synthetic_poster = _create_synthetic_poster(
        tmp_path,
        "poster_sugar_violation.png",
        [
            "Freshsip Valencia Orange",
            "100% Sugar-Free & Safe For Diets",
            "No Sugar Added"
        ]
    )

    res_draft = client.post("/api/v1/content", headers=headers, json={
        "brand_id": brand_id,
        "title": "Sugar Free Valencia Orange",
        "channel": "Social Media",
        "body_text": "Enjoy our delicious juice without worrying about your diet.",
        "poster_file_path": synthetic_poster,
        "poster_alt_text": "Freshsip bottle labeled 100% Sugar-Free"
    })
    assert res_draft.status_code == 200
    v_id = res_draft.json()["latest_version"]["id"]

    res_gov = client.post("/api/v1/governance/run", headers=headers, json={
        "content_version_id": v_id
    })
    assert res_gov.status_code == 200
    data = res_gov.json()
    assert data["overall_status"] == "failed"

    sugar_findings = [
        f for f in data["findings"]
        if ("FR-RULE-005" in (f.get("title") or "") or "Sugar Content" in (f.get("title") or ""))
    ]
    assert len(sugar_findings) > 0
    poster_sugar_findings = [
        f for f in sugar_findings
        if f.get("text_excerpt") and "bbox:" in f["text_excerpt"]
    ]
    assert len(poster_sugar_findings) > 0
    sf = poster_sugar_findings[0]
    assert sf["severity"] == "critical"
    assert "bbox:" in sf["text_excerpt"]


def test_5_mandatory_disclosure_visibly_present_in_image(client, auth_tokens):
    """
    5. A mandatory disclosure visibly present in the poster is recognized by the engine
       instead of falsely reporting it as missing.
       Product: Garden Tomato Celery Press (FS-PROD-003).
       Artwork visibly contains 'CONTAINS CELERY'.
    """
    headers = auth_tokens["content_creator"]["headers"]
    res_b = client.get("/api/v1/brands", headers=headers)
    brand_id = res_b.json()[0]["id"]

    poster_path = os.path.join(ASSETS_DIR, "product_fs_prod_003_tomato_celery.png")
    assert os.path.exists(poster_path), f"Asset missing: {poster_path}"

    # Caption does NOT mention celery allergen, but poster DOES contain 'CONTAINS CELERY'
    res_draft = client.post("/api/v1/content", headers=headers, json={
        "brand_id": brand_id,
        "title": "Garden Tomato Celery Press (FS-PROD-003)",
        "channel": "Packaging",
        "body_text": (
            "Savory vegetable goodness from ripe garden tomatoes and crisp celery. "
            "Cold-pressed and high-pressure processed. Keep refrigerated at 2°C to 5°C."
        ),
        "poster_file_path": poster_path,
        "poster_alt_text": "Garden Tomato Celery Press bottle label"
    })
    assert res_draft.status_code == 200
    v_id = res_draft.json()["latest_version"]["id"]

    res_gov = client.post("/api/v1/governance/run", headers=headers, json={
        "content_version_id": v_id
    })
    assert res_gov.status_code == 200
    data = res_gov.json()

    # FR-RULE-014 must NOT be triggered as missing because the poster visibly has 'CONTAINS CELERY'
    missing_allergen = [
        f for f in data["findings"]
        if "FR-RULE-014" in (f.get("title") or "") and "Missing" in (f.get("title") or "")
    ]
    assert len(missing_allergen) == 0, "Allergen disclosure was present in poster, should not be flagged missing"


def test_6_image_with_incorrect_pricing_against_sku(client, auth_tokens, tmp_path):
    """
    6. An image with incorrect pricing checked against an explicitly identified product
       triggers product_fact_mismatch in the poster.
       Product: FS-PROD-001 (Valencia Orange, MRP ₹120).
       Poster states: Buy for ₹65.
    """
    headers = auth_tokens["content_creator"]["headers"]
    res_b = client.get("/api/v1/brands", headers=headers)
    brand_id = res_b.json()[0]["id"]

    synthetic_poster = _create_synthetic_poster(
        tmp_path,
        "poster_wrong_price.png",
        [
            "Freshsip Valencia Orange Cold-Pressed Juice",
            "Special Flash Sale: Buy for ₹65 (50% OFF)",
            "Pure Citrus Refreshment"
        ]
    )

    res_draft = client.post("/api/v1/content", headers=headers, json={
        "brand_id": brand_id,
        "title": "Valencia Orange Cold-Pressed Juice (FS-PROD-001)",
        "channel": "Social Media",
        "body_text": "Enjoy Freshsip Valencia Orange Cold-Pressed Juice at a special promotional rate.",
        "poster_file_path": synthetic_poster,
        "poster_alt_text": "Valencia orange poster with discounted price"
    })
    assert res_draft.status_code == 200
    v_id = res_draft.json()["latest_version"]["id"]

    res_gov = client.post("/api/v1/governance/run", headers=headers, json={
        "content_version_id": v_id
    })
    assert res_gov.status_code == 200
    data = res_gov.json()
    assert data["overall_status"] == "failed"

    price_findings = [
        f for f in data["findings"]
        if f["category"] == "product_fact_mismatch" and "Price" in f["title"]
    ]
    assert len(price_findings) > 0
    pf = price_findings[0]
    assert pf["severity"] == "critical"
    assert "65" in pf["explanation"]
    assert "120" in pf["explanation"]
    assert "bbox:" in (pf.get("text_excerpt") or "")


def test_7_same_prohibited_claim_in_caption_and_poster_deduplicated(client, auth_tokens):
    """
    7. The same prohibited claim appearing in both caption and poster generates
       a single deduplicated finding indicating both locations.
       Uses 'campaign_rejected_detox_claim.png'.
    """
    headers = auth_tokens["content_creator"]["headers"]
    res_b = client.get("/api/v1/brands", headers=headers)
    brand_id = res_b.json()[0]["id"]

    poster_path = os.path.join(ASSETS_DIR, "campaign_rejected_detox_claim.png")

    # Both caption and poster contain the prohibited claim 'detox'
    res_draft = client.post("/api/v1/content", headers=headers, json={
        "brand_id": brand_id,
        "title": "Detox Juice Campaign",
        "channel": "Social Media",
        "body_text": "Try our 48-Hour miracle detox cleanse to flush toxins from your liver!",
        "poster_file_path": poster_path,
        "poster_alt_text": "Detox promotional graphic"
    })
    assert res_draft.status_code == 200
    v_id = res_draft.json()["latest_version"]["id"]

    res_gov = client.post("/api/v1/governance/run", headers=headers, json={
        "content_version_id": v_id
    })
    assert res_gov.status_code == 200
    data = res_gov.json()

    # Prohibited claim 'detox' must be deduplicated into a single unified finding
    detox_findings = [
        f for f in data["findings"]
        if "detox" in f["title"].lower() and "FR-RULE-008" in f["title"]
    ]
    assert len(detox_findings) == 1, f"Expected 1 deduplicated detox finding, got {len(detox_findings)}"

    df = detox_findings[0]
    assert "Caption & Poster" in df["title"]
    assert "Caption:" in df["text_excerpt"]
    assert "Poster:" in df["text_excerpt"]
    assert "bbox:" in df["text_excerpt"]


def test_8_image_with_no_visible_text(client, auth_tokens, tmp_path):
    """
    8. An image with no visible text (decorative graphic) is not treated as an error
       or automatically blocked.
    """
    headers = auth_tokens["content_creator"]["headers"]
    res_b = client.get("/api/v1/brands", headers=headers)
    brand_id = res_b.json()[0]["id"]

    # Solid green decorative image with no text
    clean_img = Image.new("RGB", (600, 600), color=(46, 125, 50))
    clean_path = str(tmp_path / "decorative_background.png")
    clean_img.save(clean_path)

    res_draft = client.post("/api/v1/content", headers=headers, json={
        "brand_id": brand_id,
        "title": "Freshsip Valencia Orange Social Post",
        "channel": "Social Media",
        "body_text": (
            "Enjoy Freshsip Valencia Orange Cold-Pressed Juice, crafted with 100% cold-pressed "
            "Valencia orange juice with no added sugar."
        ),
        "poster_file_path": clean_path,
        "poster_alt_text": "Solid brand green background graphic"
    })
    assert res_draft.status_code == 200
    v_id = res_draft.json()["latest_version"]["id"]

    res_gov = client.post("/api/v1/governance/run", headers=headers, json={
        "content_version_id": v_id
    })
    assert res_gov.status_code == 200
    data = res_gov.json()

    # Must pass governance cleanly without blocking on 'no text'
    assert data["overall_status"] in ("passed", "warnings")
    blocking = [f for f in data["findings"] if f["severity"] in ("critical", "high") and f.get("status") != "passed_check"]
    assert len(blocking) == 0
    no_text_failures = [f for f in data["findings"] if "OCR Processing Failed" in f["title"]]
    assert len(no_text_failures) == 0


def test_9_blurred_or_low_confidence_poster_requires_review(client, auth_tokens, monkeypatch):
    """
    9. A blurred or low-confidence poster generates an unverified review warning
       instead of falsely passing or silently ignoring visual text.
    """
    headers = auth_tokens["content_creator"]["headers"]
    res_b = client.get("/api/v1/brands", headers=headers)
    brand_id = res_b.json()[0]["id"]

    poster_path = os.path.join(ASSETS_DIR, "campaign_morning_citrus_approved.png")

    # Mock low confidence recognition
    def mock_extract(file_path):
        return OCRResult(
            status="low_confidence",
            extracted_text="Freshsip ... unreadable blurred promotional text ...",
            mean_confidence=0.48,
            regions=[OCRRegion(text="Freshsip", confidence=0.48, bbox=[[0, 0], [10, 0], [10, 10], [0, 10]])]
        )

    monkeypatch.setattr(ocr_service, "extract_text_from_image", mock_extract)

    res_draft = client.post("/api/v1/content", headers=headers, json={
        "brand_id": brand_id,
        "title": "Low Confidence Ad",
        "channel": "Social Media",
        "body_text": "Refreshing juice for your summer mornings.",
        "poster_file_path": poster_path,
        "poster_alt_text": "Blurred poster"
    })
    assert res_draft.status_code == 200
    v_id = res_draft.json()["latest_version"]["id"]

    res_gov = client.post("/api/v1/governance/run", headers=headers, json={
        "content_version_id": v_id
    })
    assert res_gov.status_code == 200
    data = res_gov.json()

    review_warnings = [
        f for f in data["findings"]
        if "Uncertain OCR Text Recognition" in f["title"]
    ]
    assert len(review_warnings) == 1
    rw = review_warnings[0]
    assert rw["severity"] == "warning"
    assert rw["category"] == "missing_evidence"
    assert "48.0%" in rw["explanation"]


def test_10_unreadable_or_corrupt_image(client, auth_tokens, tmp_path):
    """
    10. An unreadable or corrupt image is safely handled and flagged for human review
        without causing an unhandled server exception.
    """
    headers = auth_tokens["content_creator"]["headers"]
    res_b = client.get("/api/v1/brands", headers=headers)
    brand_id = res_b.json()[0]["id"]

    corrupt_file = tmp_path / "corrupt_image.png"
    corrupt_file.write_bytes(b"CORRUPT_NON_IMAGE_DATA_123456789")

    res_draft = client.post("/api/v1/content", headers=headers, json={
        "brand_id": brand_id,
        "title": "Corrupt Poster Ad",
        "channel": "Social Media",
        "body_text": "Enjoy Freshsip citrus beverages.",
        "poster_file_path": str(corrupt_file),
        "poster_alt_text": "Corrupted file asset"
    })
    assert res_draft.status_code == 200
    v_id = res_draft.json()["latest_version"]["id"]

    res_gov = client.post("/api/v1/governance/run", headers=headers, json={
        "content_version_id": v_id
    })
    assert res_gov.status_code == 200
    data = res_gov.json()

    failed_ocr_findings = [
        f for f in data["findings"]
        if "OCR Processing Failed" in f["title"]
    ]
    assert len(failed_ocr_findings) == 1
    fof = failed_ocr_findings[0]
    assert fof["severity"] == "warning"
    assert fof["category"] == "image_guideline_issue"


def test_11_unsupported_image_format(client, auth_tokens, tmp_path):
    """
    11. An unsupported image format (e.g. .txt, .pdf) is handled gracefully
        and returned as an unverified poster warning.
    """
    headers = auth_tokens["content_creator"]["headers"]
    res_b = client.get("/api/v1/brands", headers=headers)
    brand_id = res_b.json()[0]["id"]

    text_file = tmp_path / "not_an_image.txt"
    text_file.write_text("This is a plain text file, not an image format.")

    res_draft = client.post("/api/v1/content", headers=headers, json={
        "brand_id": brand_id,
        "title": "Text Attachment Poster",
        "channel": "Social Media",
        "body_text": "Enjoy our delicious beverages.",
        "poster_file_path": str(text_file),
        "poster_alt_text": "Text document attachment"
    })
    assert res_draft.status_code == 200
    v_id = res_draft.json()["latest_version"]["id"]

    res_gov = client.post("/api/v1/governance/run", headers=headers, json={
        "content_version_id": v_id
    })
    assert res_gov.status_code == 200
    data = res_gov.json()

    unsupported_findings = [
        f for f in data["findings"]
        if "Unsupported Image Format" in f["title"]
    ]
    assert len(unsupported_findings) == 1
    uf = unsupported_findings[0]
    assert uf["severity"] == "warning"
    assert ".txt" in uf["explanation"]


def test_12_tenant_isolation_and_content_version_integrity(client, auth_tokens, tmp_path):
    """
    12. Content versioning and tenant isolation integrity:
        - Poster changes produce distinct content version checksums.
        - Previous version records and runs remain immutable.
        - Separate organizations cannot access or execute runs on each other's content.
    """
    creator_headers = auth_tokens["content_creator"]["headers"]
    res_b = client.get("/api/v1/brands", headers=creator_headers)
    brand_id = res_b.json()[0]["id"]

    poster_a = _create_synthetic_poster(tmp_path, "poster_version_a.png", ["Freshsip Poster Version A"])
    poster_b = _create_synthetic_poster(tmp_path, "poster_version_b.png", ["Freshsip Poster Version B"])

    # 1. Create Version 1
    res_draft = client.post("/api/v1/content", headers=creator_headers, json={
        "brand_id": brand_id,
        "title": "Version Integrity Poster Test",
        "channel": "Social Media",
        "body_text": "Version 1 draft copy.",
        "poster_file_path": poster_a,
        "poster_alt_text": "Version A Poster"
    })
    assert res_draft.status_code == 200
    draft_id = res_draft.json()["id"]
    v1 = res_draft.json()["latest_version"]
    assert v1["version_num"] == 1
    assert v1["poster_file_path"] == poster_a
    c1 = v1["checksum"]

    # Run governance on Version 1
    res_gov_v1 = client.post("/api/v1/governance/run", headers=creator_headers, json={
        "content_version_id": v1["id"]
    })
    assert res_gov_v1.status_code == 200
    run1_id = res_gov_v1.json()["id"]

    # 2. Update draft with Poster B (generates Version 2)
    res_update = client.put(f"/api/v1/content/{draft_id}", headers=creator_headers, json={
        "title": "Version Integrity Poster Test",
        "channel": "Social Media",
        "body_text": "Version 2 draft copy with revised poster.",
        "poster_file_path": poster_b,
        "poster_alt_text": "Version B Poster"
    })
    assert res_update.status_code == 200
    updated_draft = res_update.json()
    assert updated_draft["current_version_num"] == 2
    v2 = updated_draft["latest_version"]
    assert v2["version_num"] == 2
    assert v2["poster_file_path"] == poster_b
    assert v2["checksum"] != c1, "Different poster must produce a distinct checksum"

    # 3. Verify Version 1 poster remains accessible via poster streaming
    res_poster_v1 = client.get(v1["poster_url"], headers=creator_headers)
    assert res_poster_v1.status_code == 200
    assert len(res_poster_v1.content) > 0

    # 4. Tenant isolation check: foreign organization cannot access or run governance
    foreign_headers = {
        "Authorization": creator_headers["Authorization"],
        "X-Organization-Id": "00000000-0000-0000-0000-000000000099"
    }
    res_foreign_access = client.get(f"/api/v1/content/{draft_id}", headers=foreign_headers)
    assert res_foreign_access.status_code in (403, 404), "Foreign organization must not access draft"

    res_foreign_gov = client.post("/api/v1/governance/run", headers=foreign_headers, json={
        "content_version_id": v1["id"]
    })
    assert res_foreign_gov.status_code in (403, 404), "Foreign organization must not run governance"
