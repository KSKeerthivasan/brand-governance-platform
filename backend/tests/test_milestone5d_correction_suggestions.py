import io
import os
import pytest
from PIL import Image, ImageDraw
from app.models.content import ContentItem, ContentVersion, GovernanceRun, GovernanceFinding, CorrectionSuggestion, ApprovalSubmission
from app.models.audit import AuditEvent
from app.models.organization import Organization, User


def _make_test_pdf(pages: list) -> bytes:
    """Helper to generate a multi-page PDF in memory."""
    images = []
    for p in pages:
        w, h, text = p[0], p[1], p[2]
        img = Image.new("RGB", (w, h), "white")
        draw = ImageDraw.Draw(img)
        if text:
            draw.text((30, 30), text, fill="black")
        images.append(img)
    buf = io.BytesIO()
    if images:
        images[0].save(buf, "PDF", save_all=True, append_images=images[1:])
    return buf.getvalue()


# =========================================================================
# Test 1: Exact Terminology Replacement Preserving Surrounding Text
# =========================================================================
def test_1_exact_terminology_replacement_preserving_surrounding_text(client, auth_tokens):
    headers = auth_tokens["content_creator"]["headers"]

    res_b = client.get("/api/v1/brands", headers=headers)
    brand_id = res_b.json()[0]["id"]

    body = "Freshsip Valencia Orange is 100% sugar-free, perfectly chilled for your morning breakfast."
    res_create = client.post(
        "/api/v1/content",
        headers=headers,
        json={
            "brand_id": brand_id,
            "title": "Valencia Morning Promo",
            "channel": "Social Media",
            "body_text": body
        }
    )
    assert res_create.status_code == 200
    content_id = res_create.json()["id"]
    version_id = res_create.json()["latest_version"]["id"]

    # Run governance check
    res_run = client.post(
        "/api/v1/governance/run",
        headers=headers,
        json={"content_version_id": version_id}
    )
    assert res_run.status_code == 200
    findings = res_run.json()["findings"]
    sugar_finding = next(f for f in findings if "sugar" in f["title"].lower())
    assert sugar_finding is not None
    assert sugar_finding["suggestion"] is not None

    sug = sugar_finding["suggestion"]
    assert sug["can_auto_apply"] is True
    assert sug["target_type"] == "body_text"
    assert "no added sugar" in sug["proposed_text"].lower()

    # Accept the suggestion
    res_accept = client.post(
        f"/api/v1/governance/suggestions/{sug['id']}/accept",
        headers=headers
    )
    assert res_accept.status_code == 200
    acc_data = res_accept.json()
    assert acc_data["applied_to_text"] is True
    assert acc_data["new_version_num"] == 2

    # Fetch updated draft
    res_item = client.get(f"/api/v1/content/{content_id}", headers=headers)
    updated_body = res_item.json()["latest_version"]["body_text"]

    # Surrounding text preserved!
    assert "Freshsip Valencia Orange is" in updated_body
    assert "perfectly chilled for your morning breakfast." in updated_body
    assert "100% sugar-free" not in updated_body
    assert "no added sugar" in updated_body


# =========================================================================
# Test 2: Required Disclosure Insertion Using Canonical Wording
# =========================================================================
def test_2_required_disclosure_insertion_using_canonical_wording(client, auth_tokens):
    headers = auth_tokens["content_creator"]["headers"]
    res_b = client.get("/api/v1/brands", headers=headers)
    brand_id = res_b.json()[0]["id"]

    # Garden Tomato Celery Press (FS-PROD-003) missing celery disclosure
    body = "Garden Tomato Celery Press is a savory vegetable juice blend crafted from vine tomatoes."
    res_create = client.post(
        "/api/v1/content",
        headers=headers,
        json={
            "brand_id": brand_id,
            "title": "Garden Tomato Celery Press Feature",
            "channel": "product_descriptions",
            "body_text": body
        }
    )
    assert res_create.status_code == 200
    content_id = res_create.json()["id"]
    version_id = res_create.json()["latest_version"]["id"]

    res_run = client.post(
        "/api/v1/governance/run",
        headers=headers,
        json={"content_version_id": version_id, "product_id": "FS-PROD-003"}
    )
    assert res_run.status_code == 200
    findings = res_run.json()["findings"]
    disclosure_finding = next((f for f in findings if "FR-RULE-014" in f["title"] or "celery" in f["title"].lower()), None)
    assert disclosure_finding is not None
    assert disclosure_finding["suggestion"] is not None

    sug = disclosure_finding["suggestion"]
    assert sug["correction_type"] == "mandatory_disclosure_insertion"
    assert "Contains Celery (14%)" in sug["proposed_text"]
    assert "Keep refrigerated" in sug["proposed_text"]

    # Accept insertion
    res_accept = client.post(f"/api/v1/governance/suggestions/{sug['id']}/accept", headers=headers)
    assert res_accept.status_code == 200
    assert res_accept.json()["applied_to_text"] is True

    # Check updated text
    res_item = client.get(f"/api/v1/content/{content_id}", headers=headers)
    new_text = res_item.json()["latest_version"]["body_text"]
    assert "Contains Celery (14%)" in new_text
    assert "Garden Tomato Celery Press is a savory vegetable juice" in new_text


# =========================================================================
# Test 3: Unsupported Claims Without Approved Replacement Never Receive Invented Facts
# =========================================================================
def test_3_unsupported_claims_without_approved_replacement_never_receive_invented_facts(client, auth_tokens):
    headers = auth_tokens["content_creator"]["headers"]
    res_b = client.get("/api/v1/brands", headers=headers)
    brand_id = res_b.json()[0]["id"]

    body = "Drinking Freshsip daily cures cardiovascular disease and reverses chronic depression in 30 days."
    res_create = client.post(
        "/api/v1/content",
        headers=headers,
        json={
            "brand_id": brand_id,
            "title": "Medical Claim Test",
            "channel": "Social Media",
            "body_text": body
        }
    )
    version_id = res_create.json()["latest_version"]["id"]

    res_run = client.post(
        "/api/v1/governance/run",
        headers=headers,
        json={"content_version_id": version_id}
    )
    findings = res_run.json()["findings"]
    med_finding = next(f for f in findings if f["category"] == "unsupported_claim" or "FR-RULE-007" in f["title"])
    assert med_finding is not None
    sug = med_finding["suggestion"]
    assert sug is not None

    # Must require manual review and NEVER invent clinical certifications or clinical cure claims!
    assert sug["can_auto_apply"] is False
    assert sug["confidence"] == "manual_review"
    assert "cannot be substantiated" in sug["explanation"].lower() or "remove" in sug["explanation"].lower()


# =========================================================================
# Test 4: Product and SKU Scoping for Suggestions
# =========================================================================
def test_4_product_and_sku_scoping_for_suggestions(client, auth_tokens):
    headers = auth_tokens["content_creator"]["headers"]
    res_b = client.get("/api/v1/brands", headers=headers)
    brand_id = res_b.json()[0]["id"]

    # SKU 1: Valencia Orange (FS-PROD-001) price mismatch (quoted ₹65, approved is ₹120)
    res1 = client.post(
        "/api/v1/content",
        headers=headers,
        json={
            "brand_id": brand_id,
            "title": "Valencia Orange Promo",
            "channel": "Social Media",
            "body_text": "Valencia Orange Cold-Pressed Juice available today for ₹65 only!"
        }
    )
    v1_id = res1.json()["latest_version"]["id"]
    run1 = client.post("/api/v1/governance/run", headers=headers, json={"content_version_id": v1_id, "product_id": "FS-PROD-001"})
    price_f1 = next((f for f in run1.json()["findings"] if "price" in f["title"].lower() or "mrp" in f["title"].lower() or "FR-RULE-015" in f["title"]), None)
    assert price_f1 is not None
    assert price_f1["suggestion"] is not None
    # For FS-PROD-001, approved price is ₹120
    assert "₹120" in price_f1["suggestion"]["proposed_text"]
    assert "₹95" not in price_f1["suggestion"]["proposed_text"]

    # SKU 3: Garden Tomato Celery (FS-PROD-003) price mismatch (approved price is ₹95)
    res2 = client.post(
        "/api/v1/content",
        headers=headers,
        json={
            "brand_id": brand_id,
            "title": "Garden Tomato Promo",
            "channel": "Social Media",
            "body_text": "Garden Tomato Celery Press on sale for ₹50!"
        }
    )
    v2_id = res2.json()["latest_version"]["id"]
    run2 = client.post("/api/v1/governance/run", headers=headers, json={"content_version_id": v2_id, "product_id": "FS-PROD-003"})
    price_f2 = next((f for f in run2.json()["findings"] if "price" in f["title"].lower() or "mrp" in f["title"].lower() or "FR-RULE-015" in f["title"]), None)
    assert price_f2 is not None
    assert price_f2["suggestion"] is not None
    # For FS-PROD-003, approved price is ₹95, NEVER ₹120
    assert "₹95" in price_f2["suggestion"]["proposed_text"]
    assert "₹120" not in price_f2["suggestion"]["proposed_text"]


# =========================================================================
# Test 5: Tone or Messaging Suggestions Preserving Intended Factual Meaning
# =========================================================================
def test_5_tone_or_messaging_suggestions_preserving_intended_factual_meaning(client, auth_tokens):
    headers = auth_tokens["content_creator"]["headers"]
    res_b = client.get("/api/v1/brands", headers=headers)
    brand_id = res_b.json()[0]["id"]

    body = "Your daily diet is silently poisoning your organs with toxic sludge—drink Freshsip before it is too late!"
    res_create = client.post(
        "/api/v1/content",
        headers=headers,
        json={
            "brand_id": brand_id,
            "title": "Alarmist Ad Headline",
            "channel": "Social Media",
            "body_text": body
        }
    )
    version_id = res_create.json()["latest_version"]["id"]
    run = client.post("/api/v1/governance/run", headers=headers, json={"content_version_id": version_id})
    tone_finding = next((f for f in run.json()["findings"] if "FR-RULE-002" in f["title"] or "fear" in f["title"].lower()), None)
    assert tone_finding is not None
    assert tone_finding["suggestion"] is not None

    sug = tone_finding["suggestion"]
    assert sug["correction_type"] == "tone_refinement"
    assert "refreshing" in sug["proposed_text"].lower()
    assert "Section B: Tone of Voice" in sug["evidence_source"]


# =========================================================================
# Test 6: Suggestions Linked to Finding, Content Version, Checksum and PDF Page
# =========================================================================
def test_6_suggestions_linked_to_finding_version_checksum_and_pdf_page(client, auth_tokens):
    headers = auth_tokens["content_creator"]["headers"]
    res_b = client.get("/api/v1/brands", headers=headers)
    brand_id = res_b.json()[0]["id"]

    # 2-page PDF where Page 2 contains prohibited sugar-free claim
    pdf_bytes = _make_test_pdf([
        (800, 600, "Page 1: Freshsip Deck"),
        (800, 600, "Page 2: Freshsip Valencia 100% sugar-free juice")
    ])

    res_upload = client.post(
        "/api/v1/content/upload-poster",
        headers=headers,
        files={"file": ("page_test.pdf", io.BytesIO(pdf_bytes), "application/pdf")}
    )
    poster_path = res_upload.json()["file_path"]

    res_create = client.post(
        "/api/v1/content",
        headers=headers,
        json={
            "brand_id": brand_id,
            "title": "Deck with Sugar Free Page",
            "channel": "Social Media",
            "body_text": "Deck presentation caption.",
            "poster_file_path": poster_path
        }
    )
    version = res_create.json()["latest_version"]

    run = client.post("/api/v1/governance/run", headers=headers, json={"content_version_id": version["id"]})
    findings = run.json()["findings"]
    p2_finding = next((f for f in findings if f["page_number"] == 2 and "sugar" in f["title"].lower()), None)
    assert p2_finding is not None
    assert p2_finding["suggestion"] is not None

    sug = p2_finding["suggestion"]
    assert sug["finding_id"] == p2_finding["id"]
    assert sug["content_version_id"] == version["id"]
    assert sug["source_checksum"] == version["checksum"]
    assert sug["target_type"] == "pdf_page"
    assert sug["page_number"] == 2
    assert sug["can_auto_apply"] is False  # Cannot auto-apply to flattened PDF!


# =========================================================================
# Test 7: Stale Suggestions Rejected After Content or Checksum Changes
# =========================================================================
def test_7_stale_suggestions_rejected_after_content_or_checksum_changes(client, auth_tokens):
    headers = auth_tokens["content_creator"]["headers"]
    res_b = client.get("/api/v1/brands", headers=headers)
    brand_id = res_b.json()[0]["id"]

    res_create = client.post(
        "/api/v1/content",
        headers=headers,
        json={
            "brand_id": brand_id,
            "title": "Stale Suggestion Draft",
            "channel": "Social Media",
            "body_text": "Valencia Orange 100% sugar-free bottle."
        }
    )
    content_id = res_create.json()["id"]
    v1_id = res_create.json()["latest_version"]["id"]

    # Run governance to generate suggestion on v1
    run = client.post("/api/v1/governance/run", headers=headers, json={"content_version_id": v1_id})
    sug = run.json()["findings"][0]["suggestion"]
    assert sug is not None

    # Now edit draft to create v2 (modifying checksum)
    client.put(
        f"/api/v1/content/{content_id}",
        headers=headers,
        json={
            "body_text": "Valencia Orange 100% sugar-free bottle updated manually."
        }
    )

    # Attempt to accept suggestion that belonged to v1
    res_accept = client.post(
        f"/api/v1/governance/suggestions/{sug['id']}/accept",
        headers=headers
    )
    # Must reject stale suggestion with 409 Conflict!
    assert res_accept.status_code == 409
    assert "stale" in res_accept.json()["detail"].lower()


# =========================================================================
# Test 8: Explicit Acceptance and Rejection Behaviour
# =========================================================================
def test_8_explicit_acceptance_and_rejection_behaviour(client, auth_tokens):
    headers = auth_tokens["content_creator"]["headers"]
    res_b = client.get("/api/v1/brands", headers=headers)
    brand_id = res_b.json()[0]["id"]

    body = "Freshsip Valencia Orange is 100% sugar-free."
    res_create = client.post(
        "/api/v1/content",
        headers=headers,
        json={
            "brand_id": brand_id,
            "title": "Accept Reject Draft",
            "channel": "Social Media",
            "body_text": body
        }
    )
    content_id = res_create.json()["id"]
    version_id = res_create.json()["latest_version"]["id"]

    run = client.post("/api/v1/governance/run", headers=headers, json={"content_version_id": version_id})
    sug = run.json()["findings"][0]["suggestion"]

    # Reject suggestion
    res_reject = client.post(f"/api/v1/governance/suggestions/{sug['id']}/reject", headers=headers)
    assert res_reject.status_code == 200
    assert res_reject.json()["status"] == "rejected"

    # Verify content remains unchanged
    res_item = client.get(f"/api/v1/content/{content_id}", headers=headers)
    assert res_item.json()["latest_version"]["body_text"] == body
    assert res_item.json()["current_version_num"] == 1


# =========================================================================
# Test 9: Correct Version Creation, Checksum Refresh and Governance Invalidation
# =========================================================================
def test_9_correct_version_creation_checksum_refresh_and_governance_invalidation(client, auth_tokens):
    headers = auth_tokens["content_creator"]["headers"]
    res_b = client.get("/api/v1/brands", headers=headers)
    brand_id = res_b.json()[0]["id"]

    res_create = client.post(
        "/api/v1/content",
        headers=headers,
        json={
            "brand_id": brand_id,
            "title": "Version Invalidation Test",
            "channel": "Social Media",
            "body_text": "Valencia Orange is 100% sugar-free beverage."
        }
    )
    content_id = res_create.json()["id"]
    v1 = res_create.json()["latest_version"]

    run1 = client.post("/api/v1/governance/run", headers=headers, json={"content_version_id": v1["id"]})
    sug = run1.json()["findings"][0]["suggestion"]

    # Accept suggestion
    res_acc = client.post(f"/api/v1/governance/suggestions/{sug['id']}/accept", headers=headers)
    assert res_acc.status_code == 200
    v2_num = res_acc.json()["new_version_num"]
    v2_id = res_acc.json()["new_version_id"]
    assert v2_num == 2

    # Verify item status is draft and version checksum is refreshed
    res_item = client.get(f"/api/v1/content/{content_id}", headers=headers)
    item_data = res_item.json()
    assert item_data["status"] == "draft"
    assert item_data["current_version_num"] == 2
    assert item_data["latest_version"]["checksum"] != v1["checksum"]

    # Latest governance run on new version does NOT exist yet (404 invalidated!)
    res_latest = client.get(f"/api/v1/governance/runs/{v2_id}/latest", headers=headers)
    assert res_latest.status_code == 404


# =========================================================================
# Test 10: Governance Re-evaluation After an Applied Correction
# =========================================================================
def test_10_governance_re_evaluation_after_an_applied_correction(client, auth_tokens):
    headers = auth_tokens["content_creator"]["headers"]
    res_b = client.get("/api/v1/brands", headers=headers)
    brand_id = res_b.json()[0]["id"]

    res_create = client.post(
        "/api/v1/content",
        headers=headers,
        json={
            "brand_id": brand_id,
            "title": "Re-evaluation Draft",
            "channel": "Social Media",
            "body_text": "Freshsip Valencia Orange is 100% sugar-free with no added preservatives."
        }
    )
    v1_id = res_create.json()["latest_version"]["id"]
    run1 = client.post("/api/v1/governance/run", headers=headers, json={"content_version_id": v1_id})
    sug = run1.json()["findings"][0]["suggestion"]

    # Apply correction
    res_acc = client.post(f"/api/v1/governance/suggestions/{sug['id']}/accept", headers=headers)
    v2_id = res_acc.json()["new_version_id"]

    # Re-evaluate governance on v2
    run2 = client.post("/api/v1/governance/run", headers=headers, json={"content_version_id": v2_id})
    assert run2.status_code == 200
    findings2 = run2.json()["findings"]

    # The sugar-free finding is now resolved!
    sugar_findings = [f for f in findings2 if "sugar" in f["title"].lower() and f["severity"] == "critical"]
    assert len(sugar_findings) == 0


# =========================================================================
# Test 11: New or Remaining Violations After a Correction Remain Visible
# =========================================================================
def test_11_new_or_remaining_violations_after_a_correction_remain_visible(client, auth_tokens):
    headers = auth_tokens["content_creator"]["headers"]
    res_b = client.get("/api/v1/brands", headers=headers)
    brand_id = res_b.json()[0]["id"]

    # Content has TWO distinct violations:
    # 1. 100% sugar-free (FR-RULE-005)
    # 2. Cures cancer (FR-RULE-007)
    body = "Freshsip Valencia Orange is 100% sugar-free. Cures cancer naturally!"
    res_create = client.post(
        "/api/v1/content",
        headers=headers,
        json={
            "brand_id": brand_id,
            "title": "Dual Violation Draft",
            "channel": "Social Media",
            "body_text": body
        }
    )
    v1_id = res_create.json()["latest_version"]["id"]
    run1 = client.post("/api/v1/governance/run", headers=headers, json={"content_version_id": v1_id})
    findings1 = run1.json()["findings"]
    assert len(findings1) >= 2

    sugar_sug = next(f["suggestion"] for f in findings1 if "sugar" in f["title"].lower())

    # Apply only the sugar correction
    res_acc = client.post(f"/api/v1/governance/suggestions/{sugar_sug['id']}/accept", headers=headers)
    v2_id = res_acc.json()["new_version_id"]

    # Re-run governance on v2
    run2 = client.post("/api/v1/governance/run", headers=headers, json={"content_version_id": v2_id})
    findings2 = run2.json()["findings"]

    # Disease claim MUST still remain visible as a critical blocker!
    cancer_finding = next((f for f in findings2 if "cancer" in f["title"].lower() or "medical" in f["title"].lower() or "FR-RULE-007" in f["title"]), None)
    assert cancer_finding is not None
    assert cancer_finding["severity"] == "critical"


# =========================================================================
# Test 12: Critical Blockers and Approval Gates Remain Intact
# =========================================================================
def test_12_critical_blockers_and_approval_gates_remain_intact(client, auth_tokens):
    creator_headers = auth_tokens["content_creator"]["headers"]
    res_b = client.get("/api/v1/brands", headers=creator_headers)
    brand_id = res_b.json()[0]["id"]

    body = "Freshsip Valencia Orange is 100% sugar-free and zero sugar drink."
    res_create = client.post(
        "/api/v1/content",
        headers=creator_headers,
        json={
            "brand_id": brand_id,
            "title": "Blocker Approval Gate Test",
            "channel": "Social Media",
            "body_text": body
        }
    )
    content_id = res_create.json()["id"]
    v1_id = res_create.json()["latest_version"]["id"]

    # Run governance check
    client.post("/api/v1/governance/run", headers=creator_headers, json={"content_version_id": v1_id})

    # Submitting with uncorrected critical blocker MUST FAIL (HTTP 400)
    res_sub = client.post(
        "/api/v1/approvals/submit",
        headers=creator_headers,
        json={
            "content_item_id": content_id,
            "content_version_id": v1_id,
            "submission_notes": "Trying to bypass approval gate"
        }
    )
    assert res_sub.status_code == 400
    assert "critical" in res_sub.json()["detail"].lower()


# =========================================================================
# Test 13: PDF and Raster Suggestions Not Falsely Claiming to Modify Artwork
# =========================================================================
def test_13_pdf_and_raster_suggestions_not_falsely_claiming_to_modify_artwork(client, auth_tokens):
    headers = auth_tokens["content_creator"]["headers"]
    res_b = client.get("/api/v1/brands", headers=headers)
    brand_id = res_b.json()[0]["id"]

    # Create low-contrast raster image
    img = Image.new("RGB", (600, 600), "#777777")
    draw = ImageDraw.Draw(img)
    draw.text((50, 50), "Low contrast grey text", fill="#888888")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    raw_bytes = buf.getvalue()

    res_upload = client.post(
        "/api/v1/content/upload-poster",
        headers=headers,
        files={"file": ("low_contrast.png", io.BytesIO(raw_bytes), "image/png")}
    )
    poster_path = res_upload.json()["file_path"]

    res_create = client.post(
        "/api/v1/content",
        headers=headers,
        json={
            "brand_id": brand_id,
            "title": "Artwork Contrast Test",
            "channel": "Social Media",
            "body_text": "Compliant caption copy.",
            "poster_file_path": poster_path
        }
    )
    v1 = res_create.json()["latest_version"]

    run = client.post("/api/v1/governance/run", headers=headers, json={"content_version_id": v1["id"]})
    findings = run.json()["findings"]
    vis_finding = next((f for f in findings if f["category"] in ("image_guideline_issue", "contrast", "accessibility", "dimensions") or "contrast" in f["title"].lower()), None)
    assert vis_finding is not None
    sug = vis_finding["suggestion"]
    assert sug is not None

    # Must specify non-editable artwork guidance
    assert sug["can_auto_apply"] is False
    assert sug["target_type"] == "poster_image"

    # Accepting guidance acknowledges intent without mutating the file
    res_acc = client.post(f"/api/v1/governance/suggestions/{sug['id']}/accept", headers=headers)
    assert res_acc.status_code == 200
    assert res_acc.json()["applied_to_text"] is False
    assert "authoring software" in res_acc.json()["message"]

    # File remains intact (not mutated)
    from app.services.storage import storage_service
    local_poster = storage_service.get_file_path_for_processing(poster_path)
    with open(local_poster, "rb") as f:
        assert f.read() == raw_bytes


# =========================================================================
# Test 14: Tenant Isolation, Role Enforcement and Suggestion Audit History
# =========================================================================
def test_14_tenant_isolation_role_enforcement_and_audit_history(client, auth_tokens, db_session):
    creator_headers = auth_tokens["content_creator"]["headers"]
    reviewer_headers = auth_tokens["knowledge_reviewer"]["headers"]
    res_b = client.get("/api/v1/brands", headers=creator_headers)
    brand_id = res_b.json()[0]["id"]

    res_create = client.post(
        "/api/v1/content",
        headers=creator_headers,
        json={
            "brand_id": brand_id,
            "title": "Audit and Tenant Draft",
            "channel": "Social Media",
            "body_text": "Freshsip 100% sugar-free juice."
        }
    )
    v_id = res_create.json()["latest_version"]["id"]
    run = client.post("/api/v1/governance/run", headers=creator_headers, json={"content_version_id": v_id})
    sug = run.json()["findings"][0]["suggestion"]
    sug_id = sug["id"]

    # 1. Role enforcement: reviewer cannot accept creator's suggestion
    res_rev = client.post(f"/api/v1/governance/suggestions/{sug_id}/accept", headers=reviewer_headers)
    assert res_rev.status_code == 403

    # 2. Tenant isolation: invalid org headers rejected
    fake_headers = {"Authorization": creator_headers["Authorization"], "X-Organization-Id": "00000000-0000-0000-0000-000000000000"}
    res_fake = client.get(f"/api/v1/governance/suggestions/{sug_id}", headers=fake_headers)
    assert res_fake.status_code in (403, 404)

    # 3. Accept suggestion and verify audit event recorded
    res_acc = client.post(f"/api/v1/governance/suggestions/{sug_id}/accept", headers=creator_headers)
    assert res_acc.status_code == 200

    audit_events = client.get("/api/v1/audit?limit=10", headers=creator_headers).json()
    sug_event = next((e for e in audit_events if e["event_type"] == "SUGGESTION_ACCEPTED"), None)
    assert sug_event is not None
    assert sug_event["entity_id"] == sug_id


# =========================================================================
# Test 15: Existing Text, Image, PDF, Accessibility and Analytics Workflows
# =========================================================================
def test_15_existing_text_image_pdf_accessibility_and_analytics_workflows(client, auth_tokens):
    headers = auth_tokens["content_creator"]["headers"]
    admin_headers = auth_tokens["org_admin"]["headers"]
    res_b = client.get("/api/v1/brands", headers=headers)
    brand_id = res_b.json()[0]["id"]

    # 1. Text-only draft still passes cleanly when compliant
    res_clean = client.post(
        "/api/v1/content",
        headers=headers,
        json={
            "brand_id": brand_id,
            "title": "Compliant Text Post",
            "channel": "Social Media",
            "body_text": "Made from 100% cold-pressed Valencia orange juice with no added sugar and no added preservatives."
        }
    )
    v_clean = res_clean.json()["latest_version"]["id"]
    run_clean = client.post("/api/v1/governance/run", headers=headers, json={"content_version_id": v_clean})
    assert run_clean.status_code == 200
    assert run_clean.json()["overall_status"] in ("passed", "warnings")

    # 2. Analytics overview (Milestone 5B) remains functional
    res_analytics = client.get("/api/v1/analytics/overview", headers=admin_headers)
    assert res_analytics.status_code == 200
    data = res_analytics.json()
    assert "total_runs" in data
    assert "findings_by_severity" in data

    # 3. Ambiguity report / signals remains functional
    res_amb = client.get("/api/v1/analytics/ambiguity-signals", headers=admin_headers)
    assert res_amb.status_code == 200
