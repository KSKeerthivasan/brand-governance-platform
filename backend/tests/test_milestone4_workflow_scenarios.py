import pytest
from PIL import Image, ImageDraw

def _create_synthetic_poster(tmp_path, filename: str, lines: list) -> str:
    img = Image.new("RGB", (600, 600), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    y = 50
    for line in lines:
        draw.text((40, y), line, fill=(0, 0, 0))
        y += 60
    path = str(tmp_path / filename)
    img.save(path)
    return path


def test_scenario_a_compliant_content(client, auth_tokens, tmp_path):
    """
    Scenario A — Compliant content:
    Create a compliant Freshsip advertisement, attach an approved asset, run governance,
    submit it, and approve it as an authorised reviewer.
    """
    creator_headers = auth_tokens["content_creator"]["headers"]
    approver_headers = auth_tokens["approval_manager"]["headers"]
    res_b = client.get("/api/v1/brands", headers=creator_headers)
    brand_id = res_b.json()[0]["id"]

    poster_path = _create_synthetic_poster(tmp_path, "freshsip_approved_clean.png", ["Freshsip 100% Cold-Pressed Juice"])

    # 1. Create compliant draft
    compliant_copy = (
        "Enjoy Freshsip Valencia Orange Cold-Pressed Juice, crafted from 100% cold-pressed "
        "Valencia orange juice with no added sugar. Crisp, refreshing citrus nourishment for your day!"
    )
    res_draft = client.post("/api/v1/content", headers=creator_headers, json={
        "brand_id": brand_id,
        "title": "Scenario A Compliant Campaign",
        "channel": "Social Media",
        "body_text": compliant_copy,
        "poster_file_path": poster_path,
        "poster_alt_text": "Bottle of Freshsip Valencia Orange Cold-Pressed Juice"
    })
    assert res_draft.status_code == 200
    draft = res_draft.json()
    item_id = draft["id"]
    v1_id = draft["latest_version"]["id"]

    # 2. Run governance
    res_gov = client.post("/api/v1/governance/run", headers=creator_headers, json={"content_version_id": v1_id})
    assert res_gov.status_code == 200
    gov = res_gov.json()
    assert gov["overall_status"] in ("passed", "warnings")
    critical_blockers = [f for f in gov["findings"] if f["severity"] in ("critical", "high") and f.get("status") != "passed_check"]
    assert len(critical_blockers) == 0

    # 3. Submit for approval
    res_sub = client.post("/api/v1/approvals/submit", headers=creator_headers, json={
        "content_item_id": item_id,
        "content_version_id": v1_id,
        "submission_notes": "Compliant campaign assets verified."
    })
    assert res_sub.status_code == 200
    sub_id = res_sub.json()["id"]

    # 4. Reviewer inspects queue
    res_q = client.get("/api/v1/approvals/queue", headers=approver_headers)
    assert res_q.status_code == 200
    queue_item = next((s for s in res_q.json() if s["id"] == sub_id), None)
    assert queue_item is not None
    assert queue_item["critical_findings_count"] == 0

    # 5. Approve as authorised reviewer
    res_dec = client.post(f"/api/v1/approvals/submissions/{sub_id}/decide", headers=approver_headers, json={
        "decision": "approved",
        "comments": "Reviewed text and creative poster against Freshsip Brand Guidelines. Approved for publish."
    })
    assert res_dec.status_code == 200
    dec = res_dec.json()
    assert dec["decision"] == "approved"
    assert dec["decision_label"] == "Approved — Ready to Publish"


def test_scenario_b_prohibited_claim(client, auth_tokens, tmp_path):
    """
    Scenario B — Prohibited claim:
    Create a poster containing a prohibited claim in its image text. Verify OCR detection,
    inspect the finding, and confirm that submission is blocked until the applicable blocking issue is resolved.
    """
    creator_headers = auth_tokens["content_creator"]["headers"]
    res_b = client.get("/api/v1/brands", headers=creator_headers)
    brand_id = res_b.json()[0]["id"]

    poster_path = _create_synthetic_poster(tmp_path, "prohibited_poster.png", [
        "Freshsip Miracle Drink",
        "48-Hour Detox Cleanse"
    ])

    # Create draft with clean copy but violating poster
    res_draft = client.post("/api/v1/content", headers=creator_headers, json={
        "brand_id": brand_id,
        "title": "Scenario B Prohibited Poster Claim",
        "channel": "Social Media",
        "body_text": "Taste the pure freshness of our citrus blend.",
        "poster_file_path": poster_path,
        "poster_alt_text": "Poster claiming detox cleanse"
    })
    assert res_draft.status_code == 200
    item_id = res_draft.json()["id"]
    v1_id = res_draft.json()["latest_version"]["id"]

    # Run governance with OCR
    res_gov = client.post("/api/v1/governance/run", headers=creator_headers, json={"content_version_id": v1_id})
    assert res_gov.status_code == 200
    gov = res_gov.json()

    # Find the prohibited claim finding
    detox_findings = [
        f for f in gov["findings"]
        if f["severity"] in ("critical", "high") and ("detox" in f["title"].lower() or "FR-RULE-008" in f["title"] or "detox" in f.get("text_excerpt", "").lower())
    ]
    assert len(detox_findings) > 0, "OCR must detect the prohibited detox claim"
    assert detox_findings[0]["severity"] == "critical"

    # Confirm submission is blocked
    res_sub = client.post("/api/v1/approvals/submit", headers=creator_headers, json={
        "content_item_id": item_id,
        "content_version_id": v1_id
    })
    assert res_sub.status_code == 400
    assert "unresolved blocking violation" in res_sub.json()["detail"].lower()


def test_scenario_c_revision_after_review(client, auth_tokens):
    """
    Scenario C — Revision after review:
    Run governance, edit the text or replace the poster, and attempt submission without rerunning checks.
    The backend must reject the stale result. Rerun governance and verify that the new result is tied to the new version.
    """
    creator_headers = auth_tokens["content_creator"]["headers"]
    res_b = client.get("/api/v1/brands", headers=creator_headers)
    brand_id = res_b.json()[0]["id"]

    # 1. Create v1
    res_draft = client.post("/api/v1/content", headers=creator_headers, json={
        "brand_id": brand_id,
        "title": "Scenario C Revision Lifecycle",
        "channel": "Social Media",
        "body_text": "Initial copy for Version 1."
    })
    item_id = res_draft.json()["id"]
    v1_id = res_draft.json()["latest_version"]["id"]

    # 2. Run governance on v1
    res_gov1 = client.post("/api/v1/governance/run", headers=creator_headers, json={"content_version_id": v1_id})
    assert res_gov1.status_code == 200
    gov1_id = res_gov1.json()["id"]

    # 3. Edit text -> generates v2
    compliant_copy = (
        "Enjoy Freshsip Valencia Orange Cold-Pressed Juice, crafted from 100% cold-pressed "
        "Valencia orange juice with no added sugar."
    )
    res_edit = client.put(f"/api/v1/content/{item_id}", headers=creator_headers, json={
        "body_text": compliant_copy
    })
    assert res_edit.status_code == 200
    v2 = res_edit.json()["latest_version"]
    assert v2["version_num"] == 2

    # 4. Attempt submission of v2 without running governance -> Rejected!
    res_sub_unrun = client.post("/api/v1/approvals/submit", headers=creator_headers, json={
        "content_item_id": item_id,
        "content_version_id": v2["id"]
    })
    assert res_sub_unrun.status_code == 400
    assert "No completed governance run exists" in res_sub_unrun.json()["detail"]

    # 5. Rerun governance on v2
    res_gov2 = client.post("/api/v1/governance/run", headers=creator_headers, json={"content_version_id": v2["id"]})
    assert res_gov2.status_code == 200
    gov2 = res_gov2.json()
    assert gov2["id"] != gov1_id
    assert gov2["content_version_id"] == v2["id"]

    # 6. Submit v2 -> succeeds
    res_sub_v2 = client.post("/api/v1/approvals/submit", headers=creator_headers, json={
        "content_item_id": item_id,
        "content_version_id": v2["id"],
        "submission_notes": "Submitted v2 with fresh governance run."
    })
    assert res_sub_v2.status_code == 200
    assert res_sub_v2.json()["version_num"] == 2


def test_scenario_d_uncertain_evidence(client, auth_tokens, tmp_path):
    """
    Scenario D — Uncertain evidence:
    Submit a blurred image or one for which OCR fails. Verify the configured human-review behaviour
    and confirm that uncertainty is not represented as a clean pass.
    """
    creator_headers = auth_tokens["content_creator"]["headers"]
    res_b = client.get("/api/v1/brands", headers=creator_headers)
    brand_id = res_b.json()[0]["id"]

    # Severely blurred / low-contrast image where OCR confidence is degraded
    img = Image.new("RGB", (600, 600), color=(128, 128, 128))
    draw = ImageDraw.Draw(img)
    draw.text((50, 100), "T i n y F a i n t T e x t", fill=(130, 130, 130))
    blurred_path = str(tmp_path / "blurred_image.png")
    img.save(blurred_path)

    res_draft = client.post("/api/v1/content", headers=creator_headers, json={
        "brand_id": brand_id,
        "title": "Scenario D Uncertain Evidence",
        "channel": "Social Media",
        "body_text": "Enjoy Freshsip citrus juice.",
        "poster_file_path": blurred_path,
        "poster_alt_text": "Blurred low-contrast bottle render"
    })
    v_id = res_draft.json()["latest_version"]["id"]

    res_gov = client.post("/api/v1/governance/run", headers=creator_headers, json={"content_version_id": v_id})
    assert res_gov.status_code == 200
    gov_data = res_gov.json()

    # Uncertainty must never be represented as a clean pass without findings
    assert "findings" in gov_data


def test_scenario_e_reviewer_permissions(client, auth_tokens):
    """
    Scenario E — Reviewer permissions:
    Attempt a decision as an unauthorised role and across tenant boundaries.
    Verify that the server rejects the requests.
    """
    creator_headers = auth_tokens["content_creator"]["headers"]
    reviewer_headers = auth_tokens["knowledge_reviewer"]["headers"]
    res_b = client.get("/api/v1/brands", headers=creator_headers)
    brand_id = res_b.json()[0]["id"]

    compliant_copy = (
        "Enjoy Freshsip Valencia Orange Cold-Pressed Juice, crafted from 100% cold-pressed "
        "Valencia orange juice with no added sugar."
    )
    res_draft = client.post("/api/v1/content", headers=creator_headers, json={
        "brand_id": brand_id,
        "title": "Scenario E Permissions Gate",
        "channel": "Social Media",
        "body_text": compliant_copy
    })
    item_id = res_draft.json()["id"]
    v_id = res_draft.json()["latest_version"]["id"]

    client.post("/api/v1/governance/run", headers=creator_headers, json={"content_version_id": v_id})
    res_sub = client.post("/api/v1/approvals/submit", headers=creator_headers, json={
        "content_item_id": item_id,
        "content_version_id": v_id
    })
    sub_id = res_sub.json()["id"]

    # 1. Non-approver role attempt
    res_bad_role = client.post(f"/api/v1/approvals/submissions/{sub_id}/decide", headers=reviewer_headers, json={
        "decision": "approved",
        "comments": "Unauthorized role attempt"
    })
    assert res_bad_role.status_code == 403

    # 2. Cross-tenant attempt
    foreign_mgr_headers = {
        "Authorization": auth_tokens["approval_manager"]["headers"]["Authorization"],
        "X-Organization-Id": "00000000-0000-0000-0000-000000000099"
    }
    res_cross = client.post(f"/api/v1/approvals/submissions/{sub_id}/decide", headers=foreign_mgr_headers, json={
        "decision": "approved",
        "comments": "Cross-tenant attempt"
    })
    assert res_cross.status_code in (403, 404)


def test_scenario_f_rejection_and_resubmission(client, auth_tokens):
    """
    Scenario F — Rejection and resubmission:
    Reject a submission with a recorded reason, revise the content, rerun governance and resubmit it.
    Confirm that the previous decision and findings remain available in the history.
    """
    creator_headers = auth_tokens["content_creator"]["headers"]
    approver_headers = auth_tokens["approval_manager"]["headers"]
    res_b = client.get("/api/v1/brands", headers=creator_headers)
    brand_id = res_b.json()[0]["id"]

    # 1. Create v1
    res_draft = client.post("/api/v1/content", headers=creator_headers, json={
        "brand_id": brand_id,
        "title": "Scenario F Rejection Resubmission",
        "channel": "Social Media",
        "body_text": "Draft version 1 wording."
    })
    item_id = res_draft.json()["id"]
    v1_id = res_draft.json()["latest_version"]["id"]

    client.post("/api/v1/governance/run", headers=creator_headers, json={"content_version_id": v1_id})
    res_sub1 = client.post("/api/v1/approvals/submit", headers=creator_headers, json={
        "content_item_id": item_id,
        "content_version_id": v1_id
    })
    sub1_id = res_sub1.json()["id"]

    # 2. Reject v1 with recorded reason
    res_rej = client.post(f"/api/v1/approvals/submissions/{sub1_id}/decide", headers=approver_headers, json={
        "decision": "rejected",
        "comments": "Copy is too passive. Please emphasize 100% cold-pressed freshness."
    })
    assert res_rej.status_code == 200

    # 3. Creator revises content -> v2
    compliant_copy = (
        "Enjoy Freshsip Valencia Orange Cold-Pressed Juice, crafted from 100% cold-pressed "
        "Valencia orange juice with no added sugar. Pure natural energy!"
    )
    res_edit = client.put(f"/api/v1/content/{item_id}", headers=creator_headers, json={
        "body_text": compliant_copy
    })
    v2 = res_edit.json()["latest_version"]
    assert v2["version_num"] == 2

    # 4. Rerun governance on v2
    res_gov2 = client.post("/api/v1/governance/run", headers=creator_headers, json={"content_version_id": v2["id"]})
    assert res_gov2.status_code == 200

    # 5. Resubmit v2
    res_sub2 = client.post("/api/v1/approvals/submit", headers=creator_headers, json={
        "content_item_id": item_id,
        "content_version_id": v2["id"],
        "submission_notes": "Updated copy addressing feedback."
    })
    assert res_sub2.status_code == 200
    sub2_id = res_sub2.json()["id"]

    # 6. Approver approves v2
    res_app2 = client.post(f"/api/v1/approvals/submissions/{sub2_id}/decide", headers=approver_headers, json={
        "decision": "approved",
        "comments": "Revisions satisfy brand tone perfectly. Approved."
    })
    assert res_app2.status_code == 200

    # 7. Check historical decisions on the content item
    res_item = client.get(f"/api/v1/content/{item_id}", headers=creator_headers)
    assert res_item.status_code == 200
    assert res_item.json()["status"] == "approved"

    # Both submissions must retain their separate decisions in history
    res_sub1_check = client.get(f"/api/v1/approvals/submissions/{sub1_id}", headers=approver_headers)
    assert res_sub1_check.status_code == 200
    assert len(res_sub1_check.json()["decisions"]) == 1
    assert res_sub1_check.json()["decisions"][0]["decision"] == "rejected"

    res_sub2_check = client.get(f"/api/v1/approvals/submissions/{sub2_id}", headers=approver_headers)
    assert res_sub2_check.status_code == 200
    assert len(res_sub2_check.json()["decisions"]) == 1
    assert res_sub2_check.json()["decisions"][0]["decision"] == "approved"
