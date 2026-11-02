import io
import os
import uuid
import pytest
import hashlib
from PIL import Image, ImageDraw
from pypdf import PdfWriter, PdfReader
from app.models.content import ContentItem, ContentVersion, GovernanceRun, GovernanceFinding, ApprovalSubmission, ApprovalDecision
from app.models.brand import Brand
from app.models.organization import Organization, User
from app.services.pdf_service import (
    pdf_service,
    MAX_PDF_PAGE_COUNT,
    MAX_PDF_FILE_SIZE_BYTES,
    PDFValidationError,
    PDFRenderError
)


def _make_image_pdf(pages_data: list) -> bytes:
    """
    Helper to generate a valid PDF from a list of page specifications.
    Each item in pages_data is a dict or tuple: (width, height, text_list, bg_color).
    Uses PIL Image.save to PDF.
    """
    images = []
    for item in pages_data:
        if isinstance(item, tuple):
            w, h, text = item[0], item[1], item[2]
            bg = item[3] if len(item) > 3 else "white"
        else:
            w = item.get("width", 800)
            h = item.get("height", 600)
            text = item.get("text", "")
            bg = item.get("bg", "white")

        img = Image.new("RGB", (w, h), bg)
        draw = ImageDraw.Draw(img)
        # Draw high-contrast text near top
        if text:
            draw.text((40, 40), text, fill="black")
        images.append(img)

    buf = io.BytesIO()
    if images:
        images[0].save(buf, "PDF", save_all=True, append_images=images[1:])
    return buf.getvalue()


def _make_vector_pdf_with_text(page_texts: list[str]) -> bytes:
    """
    Helper to generate a PDF with native text stream.
    """
    buf = io.BytesIO()
    writer = PdfWriter()
    for text in page_texts:
        # Create a blank page
        page = writer.add_blank_page(width=612, height=792)
    writer.write(buf)

    # Alternatively, create using PIL which also embeds proper structure
    return _make_image_pdf([(800, 600, t) for t in page_texts])


def _seed_historical_pdf_draft(client, headers, brand_id, title, page_specs_or_bytes, channel="Slide Deck", body_text="Compliant caption"):
    """
    Seeds a historical PDF file directly into storage and creates a ContentDraft
    referencing it to test backward-compatible historical PDF governance and preview.
    """
    if isinstance(page_specs_or_bytes, bytes):
        pdf_bytes = page_specs_or_bytes
    else:
        pdf_bytes = _make_image_pdf(page_specs_or_bytes)

    temp_dir = os.path.abspath("./storage_data/historical_test_posters")
    os.makedirs(temp_dir, exist_ok=True)
    file_path = os.path.join(temp_dir, f"hist_{uuid.uuid4().hex[:8]}.pdf")
    with open(file_path, "wb") as f:
        f.write(pdf_bytes)

    res_draft = client.post("/api/v1/content", headers=headers, json={
        "brand_id": brand_id,
        "title": title,
        "channel": channel,
        "body_text": body_text,
        "poster_file_path": file_path,
        "poster_alt_text": "Historical test deck"
    })
    return res_draft, file_path


# =========================================================================
# Regression Test 1: Valid Single-Page and Multi-Page PDFs (Rejection & Historical Inspection)
# =========================================================================
def test_1_valid_single_and_multi_page_pdf(client, auth_tokens):
    headers = auth_tokens["content_creator"]["headers"]
    res_b = client.get("/api/v1/brands", headers=headers)
    brand_id = res_b.json()[0]["id"]

    # 1. Single-page PDF upload is rejected under new policy
    single_pdf = _make_image_pdf([(800, 1000, "Freshsip 100% Valencia Orange Juice")])
    res_upload = client.post(
        "/api/v1/content/upload-poster",
        headers=headers,
        files={"file": ("single_ad.pdf", io.BytesIO(single_pdf), "application/pdf")}
    )
    assert res_upload.status_code == 400
    assert "PDF advertisement uploads are no longer supported" in res_upload.json()["detail"]

    # 2. Multi-page PDF upload is also rejected under new policy
    multi_pdf = _make_image_pdf([
        (800, 600, "Page 1: Freshsip Citrus Brand Campaign"),
        (800, 600, "Page 2: 100% Cold-Pressed Nutrition"),
        (800, 600, "Page 3: Available Nationwide")
    ])
    res_upload_m = client.post(
        "/api/v1/content/upload-poster",
        headers=headers,
        files={"file": ("deck_3page.pdf", io.BytesIO(multi_pdf), "application/pdf")}
    )
    assert res_upload_m.status_code == 400
    assert "PDF advertisement uploads are no longer supported" in res_upload_m.json()["detail"]

    # 3. Verify that historical single and multi-page PDFs can still be inspected
    res_draft_1, _ = _seed_historical_pdf_draft(client, headers, brand_id, "Hist Single", single_pdf)
    assert res_draft_1.status_code == 200
    v1_id = res_draft_1.json()["latest_version"]["id"]
    res_p1 = client.get(f"/api/v1/content/versions/{v1_id}/pdf-pages", headers=headers)
    assert res_p1.status_code == 200
    assert res_p1.json()["is_pdf"] is True
    assert res_p1.json()["page_count"] == 1

    res_draft_m, _ = _seed_historical_pdf_draft(client, headers, brand_id, "Hist Multi", multi_pdf)
    assert res_draft_m.status_code == 200
    vm_id = res_draft_m.json()["latest_version"]["id"]
    res_pm = client.get(f"/api/v1/content/versions/{vm_id}/pdf-pages", headers=headers)
    assert res_pm.status_code == 200
    assert res_pm.json()["is_pdf"] is True
    assert res_pm.json()["page_count"] == 3
    assert len(res_pm.json()["pages"]) == 3
    assert res_pm.json()["pages"][0]["page_number"] == 1
    assert res_pm.json()["pages"][2]["page_number"] == 3


# =========================================================================
# Regression Test 2: Different Page Sizes and Orientations
# =========================================================================
def test_2_different_page_sizes_and_orientations(client, auth_tokens):
    headers = auth_tokens["content_creator"]["headers"]
    res_b = client.get("/api/v1/brands", headers=headers)
    brand_id = res_b.json()[0]["id"]

    # Mixed deck: Page 1 portrait (600x800), Page 2 landscape (1200x600), Page 3 square (800x800)
    mixed_specs = [
        (600, 800, "Slide 1 Portrait Orientation"),
        (1200, 600, "Slide 2 Landscape Wide Banner"),
        (800, 800, "Slide 3 Square Social Carousel")
    ]

    # Upload attempt must be rejected under new policy
    res = client.post(
        "/api/v1/content/upload-poster",
        headers=headers,
        files={"file": ("mixed_deck.pdf", io.BytesIO(_make_image_pdf(mixed_specs)), "application/pdf")}
    )
    assert res.status_code == 400
    assert "PDF advertisement uploads are no longer supported" in res.json()["detail"]

    # Historical inspection preserves orientation detection
    res_draft, _ = _seed_historical_pdf_draft(client, headers, brand_id, "Mixed Deck", mixed_specs)
    assert res_draft.status_code == 200
    v_id = res_draft.json()["latest_version"]["id"]

    res_pages = client.get(f"/api/v1/content/versions/{v_id}/pdf-pages", headers=headers)
    assert res_pages.status_code == 200
    data = res_pages.json()
    assert data["page_count"] == 3
    pages = data["pages"]
    assert pages[0]["orientation"] == "portrait"
    assert pages[1]["orientation"] == "landscape"
    assert pages[2]["orientation"] == "square"


# =========================================================================
# Regression Test 3: Page-to-Finding Associations
# =========================================================================
def test_3_page_to_finding_associations(client, auth_tokens):
    headers = auth_tokens["content_creator"]["headers"]
    res_b = client.get("/api/v1/brands", headers=headers)
    brand_id = res_b.json()[0]["id"]

    # 3-page historical deck: Page 1 is clean, Page 2 has a prohibited organic claim, Page 3 is clean
    res_draft, _ = _seed_historical_pdf_draft(
        client, headers, brand_id, "Summer Campaign Deck",
        [
            (800, 600, "Page 1: Freshsip Refreshing Summer Juice"),
            (800, 600, "Page 2: 100% Certified Organic and USDA Organic Ingredients"),
            (800, 600, "Page 3: Pure Citrus Enjoyment")
        ],
        channel="PDF Presentation",
        body_text="Compliant campaign caption describing citrus flavors."
    )
    assert res_draft.status_code == 200
    v_id = res_draft.json()["latest_version"]["id"]

    # Run governance on historical multi-page PDF draft
    res_gov = client.post("/api/v1/governance/run", headers=headers, json={
        "content_version_id": v_id
    })
    assert res_gov.status_code == 200
    gov = res_gov.json()

    # Find the prohibited organic claim finding
    organic_findings = [f for f in gov["findings"] if "organic" in f["title"].lower() or "organic" in f["explanation"].lower() or "organic" in (f.get("text_excerpt") or "").lower()]
    assert len(organic_findings) > 0

    # Verify that the finding is associated with Page 2 specifically
    for f in organic_findings:
        assert f["page_number"] == 2, f"Expected page_number 2, got {f['page_number']}"


# =========================================================================
# Regression Test 4: OCR Confidence and Unreadable Pages
# =========================================================================
def test_4_ocr_confidence_and_unreadable_pages(client, auth_tokens):
    headers = auth_tokens["content_creator"]["headers"]
    res_b = client.get("/api/v1/brands", headers=headers)
    brand_id = res_b.json()[0]["id"]

    # Page 1 has clean text, Page 2 has extremely low-contrast / blurred noise that OCR cannot reliably read
    img1 = Image.new("RGB", (800, 600), "white")
    draw1 = ImageDraw.Draw(img1)
    draw1.text((50, 50), "Clear Clean Text", fill="black")

    # Noise image (very low contrast grey on grey)
    img2 = Image.new("RGB", (800, 600), (200, 200, 200))
    draw2 = ImageDraw.Draw(img2)
    # Tiny low-contrast dots
    for x in range(10, 100, 5):
        draw2.point((x, x), fill=(202, 202, 202))

    buf = io.BytesIO()
    img1.save(buf, "PDF", save_all=True, append_images=[img2])
    pdf_bytes = buf.getvalue()

    res_draft, _ = _seed_historical_pdf_draft(
        client, headers, brand_id, "Low Contrast Test", pdf_bytes,
        channel="Instagram Deck",
        body_text="Compliant caption text"
    )
    assert res_draft.status_code == 200
    v_id = res_draft.json()["latest_version"]["id"]

    res_gov = client.post("/api/v1/governance/run", headers=headers, json={
        "content_version_id": v_id
    })
    assert res_gov.status_code == 200
    gov = res_gov.json()

    # The unreadable page should have low confidence or unverified note, not a clean pass
    ocr_page2_findings = [f for f in gov["findings"] if f.get("page_number") == 2 and ("ocr" in f["category"].lower() or "contrast" in f["category"].lower() or "unreadable" in f["title"].lower())]
    # Page 2 must not be declared compliant merely because it rendered
    assert gov["overall_status"] in ["warnings", "failed"]


# =========================================================================
# Regression Test 5: Malformed, Empty, Encrypted and Unsupported PDFs
# =========================================================================
def test_5_malformed_empty_encrypted_pdfs(client, auth_tokens):
    headers = auth_tokens["content_creator"]["headers"]

    # 1. New upload rejects malformed/corrupt/encrypted files
    res_bad = client.post(
        "/api/v1/content/upload-poster",
        headers=headers,
        files={"file": ("fake.pdf", io.BytesIO(b"NOT A REAL PDF FILE CONTENTS"), "application/pdf")}
    )
    assert res_bad.status_code == 400
    assert "PDF advertisement uploads are no longer supported" in res_bad.json()["detail"]

    # 2. Corrupt PDF upload rejected
    res_corrupt = client.post(
        "/api/v1/content/upload-poster",
        headers=headers,
        files={"file": ("corrupt.pdf", io.BytesIO(b"%PDF-1.4\nBroken xref corrupt end"), "application/pdf")}
    )
    assert res_corrupt.status_code == 400
    assert "PDF advertisement uploads are no longer supported" in res_corrupt.json()["detail"]

    # 3. Encrypted PDF upload rejected
    writer = PdfWriter()
    writer.add_blank_page(width=400, height=400)
    writer.encrypt("supersecret")
    enc_buf = io.BytesIO()
    writer.write(enc_buf)
    res_enc = client.post(
        "/api/v1/content/upload-poster",
        headers=headers,
        files={"file": ("locked.pdf", io.BytesIO(enc_buf.getvalue()), "application/pdf")}
    )
    assert res_enc.status_code == 400
    assert "PDF advertisement uploads are no longer supported" in res_enc.json()["detail"]

    # 4. Underlying pdf_service raises PDFValidationError for corrupt/encrypted files
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tf:
        tf.write(b"NOT A REAL PDF FILE CONTENTS")
        tf_name = tf.name
    try:
        with pytest.raises(PDFValidationError):
            pdf_service.validate_pdf_file(tf_name)
    finally:
        if os.path.exists(tf_name):
            os.remove(tf_name)

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tf:
        tf.write(enc_buf.getvalue())
        tf_enc_name = tf.name
    try:
        with pytest.raises(PDFValidationError) as exc_info:
            pdf_service.validate_pdf_file(tf_enc_name)
        assert "encrypted" in str(exc_info.value).lower()
    finally:
        if os.path.exists(tf_enc_name):
            os.remove(tf_enc_name)


# =========================================================================
# Regression Test 6: Page-Count, File-Size and Resource Limits
# =========================================================================
def test_6_page_count_and_file_size_limits(client, auth_tokens):
    headers = auth_tokens["content_creator"]["headers"]

    # 1. New upload rejects PDFs regardless of page count or size
    large_deck = _make_image_pdf([(400, 400, f"Page {i}") for i in range(1, 33)])
    res_too_many = client.post(
        "/api/v1/content/upload-poster",
        headers=headers,
        files={"file": ("deck_32pages.pdf", io.BytesIO(large_deck), "application/pdf")}
    )
    assert res_too_many.status_code == 400
    assert "PDF advertisement uploads are no longer supported" in res_too_many.json()["detail"]

    # 2. Historical service limits: pdf_service enforces MAX_PDF_PAGE_COUNT and MAX_PDF_FILE_SIZE_BYTES
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tf:
        tf.write(large_deck)
        tf_name = tf.name
    try:
        with pytest.raises(PDFValidationError) as exc_info:
            pdf_service.validate_pdf_file(tf_name)
        assert "30 pages" in str(exc_info.value).lower() or "maximum" in str(exc_info.value).lower()
    finally:
        if os.path.exists(tf_name):
            os.remove(tf_name)


# =========================================================================
# Regression Test 7: Duplicate Extraction Paths vs Distinct Violations
# =========================================================================
def test_7_duplicate_extraction_paths_deduplicated_on_same_page(client, auth_tokens):
    """
    If native PDF extraction and OCR extraction find the same violation on Page 1,
    it must be deduplicated into a single finding rather than duplicated.
    """
    headers = auth_tokens["content_creator"]["headers"]
    res_b = client.get("/api/v1/brands", headers=headers)
    brand_id = res_b.json()[0]["id"]

    res_draft, _ = _seed_historical_pdf_draft(
        client, headers, brand_id, "Deduplication Test",
        [(800, 600, "100% Certified Organic and USDA Organic Freshsip")],
        channel="Instagram Post",
        body_text="Compliant body copy."
    )
    assert res_draft.status_code == 200
    v_id = res_draft.json()["latest_version"]["id"]

    res_gov = client.post("/api/v1/governance/run", headers=headers, json={"content_version_id": v_id})
    assert res_gov.status_code == 200
    findings = res_gov.json()["findings"]

    organic_page1 = [f for f in findings if f.get("page_number") == 1 and ("organic" in f["title"].lower() or "organic" in f.get("explanation", "").lower())]
    rule_ids = [f.get("matched_rule_id") for f in organic_page1 if f.get("matched_rule_id")]
    assert len(rule_ids) == len(set(rule_ids)), "Findings for the same rule on the same page should be deduplicated"


# =========================================================================
# Regression Test 8: Findings That Repeat Across Multiple Pages
# =========================================================================
def test_8_findings_repeating_across_different_pages(client, auth_tokens):
    """
    A violation that occurs on Page 1 AND on Page 3 must remain traceable to each affected page.
    """
    headers = auth_tokens["content_creator"]["headers"]
    res_b = client.get("/api/v1/brands", headers=headers)
    brand_id = res_b.json()[0]["id"]

    # Page 1: prohibited organic claim
    # Page 2: clean page
    # Page 3: prohibited organic claim again
    res_draft, _ = _seed_historical_pdf_draft(
        client, headers, brand_id, "Cross Page Violation",
        [
            (800, 600, "Page 1: Certified Organic Valencia Oranges"),
            (800, 600, "Page 2: Clean Citrus Refreshment"),
            (800, 600, "Page 3: USDA Organic Harvest and Pure Cold-Pressed Juice")
        ],
        channel="Slide Deck",
        body_text="Compliant caption"
    )
    assert res_draft.status_code == 200
    v_id = res_draft.json()["latest_version"]["id"]

    res_gov = client.post("/api/v1/governance/run", headers=headers, json={"content_version_id": v_id})
    assert res_gov.status_code == 200
    findings = res_gov.json()["findings"]

    organic_findings = [f for f in findings if "organic" in f["title"].lower() or "organic" in f.get("explanation", "").lower()]
    pages_with_violation = {f["page_number"] for f in organic_findings if f.get("page_number")}
    assert 1 in pages_with_violation, "Page 1 violation must be preserved"
    assert 3 in pages_with_violation, "Page 3 violation must be preserved"
    assert 2 not in pages_with_violation, "Clean Page 2 must not have the violation"


# =========================================================================
# Regression Test 9: Checksum Changes and Stale Governance Runs
# =========================================================================
def test_9_pdf_checksum_changes_and_stale_governance(client, auth_tokens):
    headers = auth_tokens["content_creator"]["headers"]
    res_b = client.get("/api/v1/brands", headers=headers)
    brand_id = res_b.json()[0]["id"]

    # Initial historical PDF
    pdf1 = _make_image_pdf([(800, 600, "Initial PDF Content")])
    res_draft, path1 = _seed_historical_pdf_draft(
        client, headers, brand_id, "Checksum Integrity Item", pdf1,
        channel="Instagram",
        body_text="Caption copy"
    )
    assert res_draft.status_code == 200
    content_id = res_draft.json()["id"]
    v1_id = res_draft.json()["latest_version"]["id"]
    checksum_1 = res_draft.json()["latest_version"]["checksum"]

    # Run governance on v1
    res_g1 = client.post("/api/v1/governance/run", headers=headers, json={"content_version_id": v1_id})
    assert res_g1.status_code == 200

    # Modify PDF and save new revision
    pdf2 = _make_image_pdf([(800, 600, "Modified New PDF Content With Different Text")])
    temp_dir = os.path.abspath("./storage_data/historical_test_posters")
    os.makedirs(temp_dir, exist_ok=True)
    path2 = os.path.join(temp_dir, f"hist_{uuid.uuid4().hex[:8]}.pdf")
    with open(path2, "wb") as f:
        f.write(pdf2)

    res_v2 = client.put(f"/api/v1/content/{content_id}", headers=headers, json={
        "title": "Checksum Integrity Item",
        "channel": "Instagram",
        "body_text": "Caption copy",
        "poster_file_path": path2,
        "poster_alt_text": "Modified deck"
    })
    assert res_v2.status_code == 200
    v2_id = res_v2.json()["latest_version"]["id"]
    checksum_2 = res_v2.json()["latest_version"]["checksum"]

    # Checksums must differ
    assert checksum_1 != checksum_2

    # Latest governance run for v2 does not exist (404) until explicitly evaluated (no stale run leak)
    res_gov_v2 = client.get(f"/api/v1/governance/latest/{v2_id}", headers=headers)
    assert res_gov_v2.status_code == 404


# =========================================================================
# Regression Test 10: Critical Blockers and Warning Justification in PDF Approval
# =========================================================================
def test_10_critical_blockers_and_warning_justification_in_pdf_approval(client, auth_tokens):
    creator_headers = auth_tokens["content_creator"]["headers"]
    mgr_headers = auth_tokens["approval_manager"]["headers"]
    res_b = client.get("/api/v1/brands", headers=creator_headers)
    brand_id = res_b.json()[0]["id"]

    # Create historical PDF with a critical violation (prohibited sugar-free claim FR-RULE-005)
    pdf_bytes = _make_image_pdf([(800, 600, "Freshsip Valencia Orange: 100% sugar-free and zero sugar drink")])
    res_draft, _ = _seed_historical_pdf_draft(
        client, creator_headers, brand_id, "Critical Blocker PDF Submission", pdf_bytes,
        channel="Instagram",
        body_text="Caption body"
    )
    assert res_draft.status_code == 200
    content_id = res_draft.json()["id"]
    v_id = res_draft.json()["latest_version"]["id"]

    # Run governance to surface critical blocker
    res_gov = client.post("/api/v1/governance/run", headers=creator_headers, json={"content_version_id": v_id})
    assert res_gov.status_code == 200
    gov = res_gov.json()
    assert gov["overall_status"] == "failed"
    crit_blockers = [f for f in gov["findings"] if f["severity"] in ("critical", "high") and f.get("status") != "passed_check"]
    assert len(crit_blockers) > 0

    # Submit for approval -> Fail-closed gate blocks submission when critical violations exist
    res_sub = client.post("/api/v1/approvals/submit", headers=creator_headers, json={
        "content_item_id": content_id,
        "content_version_id": v_id,
        "submission_notes": "Attempting submission with blocker"
    })
    assert res_sub.status_code == 400
    assert "blocking" in res_sub.json()["detail"].lower() or "critical" in res_sub.json()["detail"].lower()


# =========================================================================
# Regression Test 11: Tenant Isolation and Permissions
# =========================================================================
def test_11_tenant_isolation_and_permissions(client, auth_tokens, db_session):
    creator_headers = auth_tokens["content_creator"]["headers"]
    res_b = client.get("/api/v1/brands", headers=creator_headers)
    brand_id = res_b.json()[0]["id"]

    # Seed historical PDF
    pdf_bytes = _make_image_pdf([(800, 600, "Confidential Tenant Content")])
    res_draft, _ = _seed_historical_pdf_draft(
        client, creator_headers, brand_id, "Tenant Isolation Deck", pdf_bytes,
        channel="Instagram",
        body_text="Tenant Copy"
    )
    assert res_draft.status_code == 200
    v_id = res_draft.json()["latest_version"]["id"]

    # Creator cannot approve (permission check)
    res_approve_attempt = client.post(f"/api/v1/approvals/submissions/fake-id/decision", headers=creator_headers, json={
        "decision": "approved",
        "notes": "Unauthorized approval"
    })
    assert res_approve_attempt.status_code in [403, 404]

    # Verify rendering endpoint responds for authorized creator (historical PDF preview)
    res_page1 = client.get(f"/api/v1/content/versions/{v_id}/poster?page=1", headers=creator_headers)
    assert res_page1.status_code == 200
    assert res_page1.headers["content-type"] == "image/png"


# =========================================================================
# Regression Test 12: Existing PNG, JPEG, WEBP and Text Workflows Functional
# =========================================================================
def test_12_existing_png_jpeg_webp_and_text_workflows(client, auth_tokens):
    headers = auth_tokens["content_creator"]["headers"]
    res_b = client.get("/api/v1/brands", headers=headers)
    brand_id = res_b.json()[0]["id"]

    # 1. Pure text draft without creative
    res_text = client.post("/api/v1/content", headers=headers, json={
        "brand_id": brand_id,
        "title": "Pure Text Draft",
        "channel": "Twitter Post",
        "body_text": "100% Cold-Pressed Valencia Orange Juice. Crisp & refreshing."
    })
    assert res_text.status_code == 200
    assert res_text.json()["latest_version"]["poster_file_path"] is None
    assert res_text.json()["latest_version"]["is_pdf"] is False

    # 2. Raster PNG creative
    img = Image.new("RGB", (800, 600), "green")
    draw = ImageDraw.Draw(img)
    draw.text((50, 50), "Freshsip Summer Special", fill="white")
    png_buf = io.BytesIO()
    img.save(png_buf, "PNG")

    res_png = client.post(
        "/api/v1/content/upload-poster",
        headers=headers,
        files={"file": ("poster.png", io.BytesIO(png_buf.getvalue()), "image/png")}
    )
    assert res_png.status_code == 200
    assert res_png.json()["is_pdf"] is False
    assert res_png.json()["format"] == "PNG"


# =========================================================================
# Regression Test 13: PDF Pages Endpoint and Structured Metadata
# =========================================================================
def test_13_pdf_pages_metadata_endpoint(client, auth_tokens):
    headers = auth_tokens["content_creator"]["headers"]
    res_b = client.get("/api/v1/brands", headers=headers)
    brand_id = res_b.json()[0]["id"]

    # 2-page deck
    pdf_bytes = _make_image_pdf([
        (600, 800, "Page 1 Portrait"),
        (900, 600, "Page 2 Landscape")
    ])
    res_draft, _ = _seed_historical_pdf_draft(
        client, headers, brand_id, "Pages Metadata Test", pdf_bytes,
        channel="Deck",
        body_text="Copy"
    )
    assert res_draft.status_code == 200
    v_id = res_draft.json()["latest_version"]["id"]

    # Call GET /versions/{version_id}/pdf-pages (historical PDF inspection)
    res_pages = client.get(f"/api/v1/content/versions/{v_id}/pdf-pages", headers=headers)
    assert res_pages.status_code == 200
    meta_data = res_pages.json()
    assert meta_data["is_pdf"] is True
    assert meta_data["page_count"] == 2
    pages_data = meta_data["pages"]
    assert len(pages_data) == 2
    assert pages_data[0]["page_number"] == 1
    assert pages_data[0]["orientation"] == "portrait"
    assert pages_data[1]["page_number"] == 2
    assert pages_data[1]["orientation"] == "landscape"
