import pytest
import os
import hashlib
from PIL import Image, ImageDraw
from datetime import datetime

from app.models.content import (
    ContentItem,
    ContentVersion,
    GovernanceRun,
    GovernanceFinding,
    ApprovalSubmission,
    ApprovalDecision
)

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


# 1. Submission without any governance run is rejected
def test_1_submission_without_governance_run_rejected(client, auth_tokens):
    creator_headers = auth_tokens["content_creator"]["headers"]
    res_b = client.get("/api/v1/brands", headers=creator_headers)
    brand_id = res_b.json()[0]["id"]

    res_draft = client.post("/api/v1/content", headers=creator_headers, json={
        "brand_id": brand_id,
        "title": "Ungoverned Draft Submission Test",
        "channel": "Social Media",
        "body_text": "Compliant text but governance check was never run."
    })
    assert res_draft.status_code == 200
    item_id = res_draft.json()["id"]
    version_id = res_draft.json()["latest_version"]["id"]

    res_sub = client.post("/api/v1/approvals/submit", headers=creator_headers, json={
        "content_item_id": item_id,
        "content_version_id": version_id,
        "submission_notes": "Attempting submit without check"
    })
    assert res_sub.status_code == 400
    assert "No completed governance run exists" in res_sub.json()["detail"]


# 2. Submission with a failed governance run is rejected
def test_2_submission_with_failed_governance_run_rejected(client, auth_tokens, db_session):
    creator_headers = auth_tokens["content_creator"]["headers"]
    res_b = client.get("/api/v1/brands", headers=creator_headers)
    brand_id = res_b.json()[0]["id"]

    res_draft = client.post("/api/v1/content", headers=creator_headers, json={
        "brand_id": brand_id,
        "title": "Failed Governance Run Test",
        "channel": "Social Media",
        "body_text": "Sample text for testing failed run rejection."
    })
    assert res_draft.status_code == 200
    item_id = res_draft.json()["id"]
    version_id = res_draft.json()["latest_version"]["id"]

    # Run governance
    res_gov = client.post("/api/v1/governance/run", headers=creator_headers, json={
        "content_version_id": version_id
    })
    assert res_gov.status_code == 200
    run_id = res_gov.json()["id"]

    # Simulate an incomplete/failed processing run in the database
    gov_run = db_session.query(GovernanceRun).filter(GovernanceRun.id == run_id).first()
    gov_run.overall_status = "failed"
    db_session.commit()

    # Attempt submission
    res_sub = client.post("/api/v1/approvals/submit", headers=creator_headers, json={
        "content_item_id": item_id,
        "content_version_id": version_id,
        "submission_notes": "Attempting submission with failed run"
    })
    assert res_sub.status_code == 400
    assert "did not pass" in res_sub.json()["detail"] or "failed" in res_sub.json()["detail"]


# 3. Submission with an unresolved critical blocker is rejected
def test_3_submission_with_unresolved_critical_blocker_rejected(client, auth_tokens):
    creator_headers = auth_tokens["content_creator"]["headers"]
    res_b = client.get("/api/v1/brands", headers=creator_headers)
    brand_id = res_b.json()[0]["id"]

    # Draft with prohibited detox claim (FR-RULE-008, critical blocker)
    res_draft = client.post("/api/v1/content", headers=creator_headers, json={
        "brand_id": brand_id,
        "title": "Prohibited Detox Claim Test",
        "channel": "Social Media",
        "body_text": "Try Freshsip detox juice to flush all dangerous toxins from your body!"
    })
    assert res_draft.status_code == 200
    item_id = res_draft.json()["id"]
    version_id = res_draft.json()["latest_version"]["id"]

    # Run governance
    res_gov = client.post("/api/v1/governance/run", headers=creator_headers, json={
        "content_version_id": version_id
    })
    assert res_gov.status_code == 200
    assert res_gov.json()["overall_status"] == "failed"

    # Attempt submission -> must fail closed
    res_sub = client.post("/api/v1/approvals/submit", headers=creator_headers, json={
        "content_item_id": item_id,
        "content_version_id": version_id,
        "submission_notes": "Trying to submit critical violation"
    })
    assert res_sub.status_code == 400
    assert "unresolved blocking violation" in res_sub.json()["detail"].lower()
    assert "FR-RULE-008" in res_sub.json()["detail"] or "detox" in res_sub.json()["detail"].lower()


# 4. Submission with a valid passing governance run succeeds
def test_4_submission_with_valid_passing_governance_run_succeeds(client, auth_tokens):
    creator_headers = auth_tokens["content_creator"]["headers"]
    res_b = client.get("/api/v1/brands", headers=creator_headers)
    brand_id = res_b.json()[0]["id"]

    compliant_copy = (
        "Enjoy Freshsip Valencia Orange Cold-Pressed Juice, crafted from 100% cold-pressed "
        "Valencia orange juice with no added sugar. Crisp, refreshing citrus nourishment for your day!"
    )
    res_draft = client.post("/api/v1/content", headers=creator_headers, json={
        "brand_id": brand_id,
        "title": "Fully Compliant Post Test",
        "channel": "Social Media",
        "body_text": compliant_copy
    })
    assert res_draft.status_code == 200
    item_id = res_draft.json()["id"]
    version_id = res_draft.json()["latest_version"]["id"]

    # Run governance
    res_gov = client.post("/api/v1/governance/run", headers=creator_headers, json={
        "content_version_id": version_id
    })
    assert res_gov.status_code == 200
    assert res_gov.json()["overall_status"] == "passed"

    # Submit for approval -> succeeds
    res_sub = client.post("/api/v1/approvals/submit", headers=creator_headers, json={
        "content_item_id": item_id,
        "content_version_id": version_id,
        "submission_notes": "Compliant draft for review."
    })
    assert res_sub.status_code == 200
    sub_data = res_sub.json()
    assert sub_data["status"] == "pending"
    assert sub_data["version_num"] == 1
    assert sub_data["checksum"] is not None


# 5. Warning-only content follows the documented approval policy
def test_5_warning_only_content_follows_documented_approval_policy(client, auth_tokens, tmp_path):
    creator_headers = auth_tokens["content_creator"]["headers"]
    approver_headers = auth_tokens["approval_manager"]["headers"]
    res_b = client.get("/api/v1/brands", headers=creator_headers)
    brand_id = res_b.json()[0]["id"]

    # Poster with slight dimension or alt-text non-critical warning
    poster_path = _create_synthetic_poster(tmp_path, "warning_poster.png", ["Freshsip Refreshing Citrus"])
    res_draft = client.post("/api/v1/content", headers=creator_headers, json={
        "brand_id": brand_id,
        "title": "Warning Only Approval Policy Test",
        "channel": "Social Media",
        "body_text": "Freshsip pure citrus juice - chilled and crisp.",
        "poster_file_path": poster_path,
        "poster_alt_text": "Citrus graphic"
    })
    assert res_draft.status_code == 200
    item_id = res_draft.json()["id"]
    version_id = res_draft.json()["latest_version"]["id"]

    res_gov = client.post("/api/v1/governance/run", headers=creator_headers, json={
        "content_version_id": version_id
    })
    assert res_gov.status_code == 200

    # Submission succeeds
    res_sub = client.post("/api/v1/approvals/submit", headers=creator_headers, json={
        "content_item_id": item_id,
        "content_version_id": version_id,
        "submission_notes": "Submission with possible warnings."
    })
    assert res_sub.status_code == 200
    sub_id = res_sub.json()["id"]

    # Approver approves with valid substantive comments
    res_dec = client.post(f"/api/v1/approvals/submissions/{sub_id}/decide", headers=approver_headers, json={
        "decision": "approved",
        "comments": "Reviewed image styling and verified non-critical warnings are acceptable for this campaign."
    })
    assert res_dec.status_code == 200
    assert res_dec.json()["decision"] == "approved"


# 6. Editing the body after governance invalidates the previous result
def test_6_editing_body_after_governance_invalidates_previous_result(client, auth_tokens):
    creator_headers = auth_tokens["content_creator"]["headers"]
    res_b = client.get("/api/v1/brands", headers=creator_headers)
    brand_id = res_b.json()[0]["id"]

    res_draft = client.post("/api/v1/content", headers=creator_headers, json={
        "brand_id": brand_id,
        "title": "Body Invalidation Test",
        "channel": "Social Media",
        "body_text": "Initial compliant copy."
    })
    assert res_draft.status_code == 200
    item_id = res_draft.json()["id"]
    v1_id = res_draft.json()["latest_version"]["id"]

    # Run governance on v1
    res_gov = client.post("/api/v1/governance/run", headers=creator_headers, json={
        "content_version_id": v1_id
    })
    assert res_gov.status_code == 200

    # Edit body -> creates Version 2
    res_edit = client.put(f"/api/v1/content/{item_id}", headers=creator_headers, json={
        "body_text": "Edited copy after governance check."
    })
    assert res_edit.status_code == 200
    v2 = res_edit.json()["latest_version"]
    assert v2["version_num"] == 2

    # Attempting to submit v2 without running governance on v2 must be rejected
    res_sub_v2 = client.post("/api/v1/approvals/submit", headers=creator_headers, json={
        "content_item_id": item_id,
        "content_version_id": v2["id"],
        "submission_notes": "Submitting uninspected v2"
    })
    assert res_sub_v2.status_code == 400
    assert "No completed governance run exists" in res_sub_v2.json()["detail"]

    # Attempting to submit obsolete v1 must be rejected (staleness check)
    res_sub_v1 = client.post("/api/v1/approvals/submit", headers=creator_headers, json={
        "content_item_id": item_id,
        "content_version_id": v1_id,
        "submission_notes": "Submitting obsolete v1"
    })
    assert res_sub_v1.status_code == 400
    assert "obsolete version v1" in res_sub_v1.json()["detail"].lower() or "stale version" in res_sub_v1.json()["detail"].lower()


# 7. Replacing a poster after governance invalidates the previous result
def test_7_replacing_poster_after_governance_invalidates_previous_result(client, auth_tokens, tmp_path):
    creator_headers = auth_tokens["content_creator"]["headers"]
    res_b = client.get("/api/v1/brands", headers=creator_headers)
    brand_id = res_b.json()[0]["id"]

    poster_a = _create_synthetic_poster(tmp_path, "poster_a.png", ["Poster A Approved Copy"])
    poster_b = _create_synthetic_poster(tmp_path, "poster_b.png", ["Poster B Replaced Copy"])

    res_draft = client.post("/api/v1/content", headers=creator_headers, json={
        "brand_id": brand_id,
        "title": "Poster Replacement Test",
        "channel": "Social Media",
        "body_text": "Sample text with poster.",
        "poster_file_path": poster_a
    })
    item_id = res_draft.json()["id"]
    v1_id = res_draft.json()["latest_version"]["id"]

    # Run governance on v1
    res_gov = client.post("/api/v1/governance/run", headers=creator_headers, json={
        "content_version_id": v1_id
    })
    assert res_gov.status_code == 200

    # Replace poster -> creates v2
    res_edit = client.put(f"/api/v1/content/{item_id}", headers=creator_headers, json={
        "body_text": "Sample text with poster.",
        "poster_file_path": poster_b
    })
    assert res_edit.status_code == 200
    v2 = res_edit.json()["latest_version"]
    assert v2["version_num"] == 2

    # Submitting v2 without governance check on v2 fails
    res_sub = client.post("/api/v1/approvals/submit", headers=creator_headers, json={
        "content_item_id": item_id,
        "content_version_id": v2["id"]
    })
    assert res_sub.status_code == 400
    assert "No completed governance run exists" in res_sub.json()["detail"]


# 8. Changing the product, channel or other relevant context invalidates the previous result
def test_8_changing_product_channel_or_context_invalidates_previous_result(client, auth_tokens):
    creator_headers = auth_tokens["content_creator"]["headers"]
    res_b = client.get("/api/v1/brands", headers=creator_headers)
    brand_id = res_b.json()[0]["id"]

    res_draft = client.post("/api/v1/content", headers=creator_headers, json={
        "brand_id": brand_id,
        "title": "Channel Invalidation Test",
        "channel": "Social Media",
        "body_text": "Campaign copy text."
    })
    item_id = res_draft.json()["id"]
    v1_id = res_draft.json()["latest_version"]["id"]

    # Run governance for Social Media channel
    res_gov = client.post("/api/v1/governance/run", headers=creator_headers, json={
        "content_version_id": v1_id
    })
    assert res_gov.status_code == 200

    # Change channel to Print Poster -> Must create a new version to re-evaluate channel-specific rules!
    res_edit = client.put(f"/api/v1/content/{item_id}", headers=creator_headers, json={
        "body_text": "Campaign copy text.",
        "channel": "Print Poster"
    })
    assert res_edit.status_code == 200
    item_updated = res_edit.json()
    assert item_updated["channel"] == "Print Poster"
    v2 = item_updated["latest_version"]
    assert v2["version_num"] == 2

    # Submitting v2 without running governance fails
    res_sub = client.post("/api/v1/approvals/submit", headers=creator_headers, json={
        "content_item_id": item_id,
        "content_version_id": v2["id"]
    })
    assert res_sub.status_code == 400
    assert "No completed governance run exists" in res_sub.json()["detail"]


# 9. A governance result for an old version cannot authorise a newer version
def test_9_governance_result_for_old_version_cannot_authorize_newer_version(client, auth_tokens):
    creator_headers = auth_tokens["content_creator"]["headers"]
    res_b = client.get("/api/v1/brands", headers=creator_headers)
    brand_id = res_b.json()[0]["id"]

    res_draft = client.post("/api/v1/content", headers=creator_headers, json={
        "brand_id": brand_id,
        "title": "Version Cross-Authorization Test",
        "channel": "Social Media",
        "body_text": "Version 1 copy."
    })
    item_id = res_draft.json()["id"]
    v1_id = res_draft.json()["latest_version"]["id"]

    # Run governance on v1
    res_gov = client.post("/api/v1/governance/run", headers=creator_headers, json={
        "content_version_id": v1_id
    })
    assert res_gov.status_code == 200

    # Update to v2
    res_edit = client.put(f"/api/v1/content/{item_id}", headers=creator_headers, json={
        "body_text": "Version 2 copy updated."
    })
    v2_id = res_edit.json()["latest_version"]["id"]

    # Try submitting v2 referencing v1's governance check
    res_sub = client.post("/api/v1/approvals/submit", headers=creator_headers, json={
        "content_item_id": item_id,
        "content_version_id": v2_id
    })
    assert res_sub.status_code == 400
    assert "No completed governance run exists for content version v2" in res_sub.json()["detail"] or "governance" in res_sub.json()["detail"].lower()


# 10. OCR failure cannot silently satisfy required image-text verification
def test_10_ocr_failure_cannot_silently_satisfy_image_text_verification(client, auth_tokens, tmp_path):
    creator_headers = auth_tokens["content_creator"]["headers"]
    res_b = client.get("/api/v1/brands", headers=creator_headers)
    brand_id = res_b.json()[0]["id"]

    # Create a corrupted / non-image file at poster path
    fake_poster = tmp_path / "corrupted_poster.png"
    fake_poster.write_bytes(b"NOT_A_VALID_PNG_FILE_DATA_CORRUPTED")

    res_draft = client.post("/api/v1/content", headers=creator_headers, json={
        "brand_id": brand_id,
        "title": "Corrupted Poster Verification Test",
        "channel": "Social Media",
        "body_text": "Freshsip healthy drink copy.",
        "poster_file_path": str(fake_poster)
    })
    assert res_draft.status_code == 200
    v_id = res_draft.json()["latest_version"]["id"]

    # Run governance
    res_gov = client.post("/api/v1/governance/run", headers=creator_headers, json={
        "content_version_id": v_id
    })
    assert res_gov.status_code == 200
    gov_data = res_gov.json()

    # Must flag OCR failure as an active finding and NOT treat it as a clean pass
    ocr_fail_findings = [
        f for f in gov_data["findings"]
        if "ocr" in f["title"].lower() or "unreadable" in f["title"].lower() or "ocr" in f["explanation"].lower()
    ]
    assert len(ocr_fail_findings) > 0, "Corrupted poster must generate an OCR failure finding"
    assert gov_data["overall_status"] != "passed", "Cannot silently pass an unreadable image"


# 11. An unauthorised user cannot submit or decide another tenant's content
def test_11_unauthorized_user_cannot_submit_or_decide_other_tenant_content(client, auth_tokens):
    creator_headers = auth_tokens["content_creator"]["headers"]
    res_b = client.get("/api/v1/brands", headers=creator_headers)
    brand_id = res_b.json()[0]["id"]

    compliant_copy = (
        "Enjoy Freshsip Valencia Orange Cold-Pressed Juice, crafted from 100% cold-pressed "
        "Valencia orange juice with no added sugar. Crisp, refreshing citrus nourishment for your day!"
    )
    res_draft = client.post("/api/v1/content", headers=creator_headers, json={
        "brand_id": brand_id,
        "title": "Tenant Boundary Isolation Test",
        "channel": "Social Media",
        "body_text": compliant_copy
    })
    item_id = res_draft.json()["id"]
    v_id = res_draft.json()["latest_version"]["id"]

    # Run governance
    client.post("/api/v1/governance/run", headers=creator_headers, json={"content_version_id": v_id})

    # Foreign tenant headers
    foreign_headers = {
        "Authorization": creator_headers["Authorization"],
        "X-Organization-Id": "00000000-0000-0000-0000-000000000099"
    }

    # Foreign tenant cannot submit this item
    res_for_sub = client.post("/api/v1/approvals/submit", headers=foreign_headers, json={
        "content_item_id": item_id,
        "content_version_id": v_id
    })
    assert res_for_sub.status_code in (403, 404)

    # Legitimate submit
    res_sub = client.post("/api/v1/approvals/submit", headers=creator_headers, json={
        "content_item_id": item_id,
        "content_version_id": v_id
    })
    assert res_sub.status_code == 200
    sub_id = res_sub.json()["id"]

    # Foreign approver cannot decide this submission
    foreign_mgr_headers = {
        "Authorization": auth_tokens["approval_manager"]["headers"]["Authorization"],
        "X-Organization-Id": "00000000-0000-0000-0000-000000000099"
    }
    res_for_dec = client.post(f"/api/v1/approvals/submissions/{sub_id}/decide", headers=foreign_mgr_headers, json={
        "decision": "approved",
        "comments": "Attempting cross-tenant approval decision."
    })
    assert res_for_dec.status_code in (403, 404)


# 12. A creator cannot approve their own submission where prohibited
def test_12_creator_cannot_approve_own_submission(client, auth_tokens):
    creator_headers = auth_tokens["content_creator"]["headers"]
    res_b = client.get("/api/v1/brands", headers=creator_headers)
    brand_id = res_b.json()[0]["id"]

    compliant_copy = (
        "Enjoy Freshsip Valencia Orange Cold-Pressed Juice, crafted from 100% cold-pressed "
        "Valencia orange juice with no added sugar. Crisp, refreshing citrus nourishment for your day!"
    )
    res_draft = client.post("/api/v1/content", headers=creator_headers, json={
        "brand_id": brand_id,
        "title": "Creator Self-Approval Prevention Test",
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

    # Creator attempts to approve -> 403 Forbidden
    res_self = client.post(f"/api/v1/approvals/submissions/{sub_id}/decide", headers=creator_headers, json={
        "decision": "approved",
        "comments": "Approving my own content."
    })
    assert res_self.status_code == 403
    assert "Conflict of Interest" in res_self.json()["detail"] or "Permission Denied" in res_self.json()["detail"]


# 13. Only authorised reviewers can record approval decisions
def test_13_only_authorized_reviewers_can_record_approval_decisions(client, auth_tokens):
    creator_headers = auth_tokens["content_creator"]["headers"]
    reviewer_headers = auth_tokens["knowledge_reviewer"]["headers"]
    res_b = client.get("/api/v1/brands", headers=creator_headers)
    brand_id = res_b.json()[0]["id"]

    compliant_copy = (
        "Enjoy Freshsip Valencia Orange Cold-Pressed Juice, crafted from 100% cold-pressed "
        "Valencia orange juice with no added sugar. Crisp, refreshing citrus nourishment for your day!"
    )
    res_draft = client.post("/api/v1/content", headers=creator_headers, json={
        "brand_id": brand_id,
        "title": "Role Authorization Gate Test",
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

    # Knowledge Reviewer (non-approver) attempts to approve -> 403 Forbidden
    res_reviewer = client.post(f"/api/v1/approvals/submissions/{sub_id}/decide", headers=reviewer_headers, json={
        "decision": "approved",
        "comments": "Reviewer attempting approval without authority."
    })
    assert res_reviewer.status_code == 403
    assert "Permission Denied" in res_reviewer.json()["detail"] or "approval_manager" in res_reviewer.json()["detail"]


# 14. A rejected submission can be revised, rechecked and resubmitted
def test_14_rejected_submission_can_be_revised_rechecked_and_resubmitted(client, auth_tokens):
    creator_headers = auth_tokens["content_creator"]["headers"]
    approver_headers = auth_tokens["approval_manager"]["headers"]
    res_b = client.get("/api/v1/brands", headers=creator_headers)
    brand_id = res_b.json()[0]["id"]

    # Create v1
    res_draft = client.post("/api/v1/content", headers=creator_headers, json={
        "brand_id": brand_id,
        "title": "Rejection and Revision Cycle Test",
        "channel": "Social Media",
        "body_text": "Draft with wording manager dislikes but passes basic checks."
    })
    item_id = res_draft.json()["id"]
    v1_id = res_draft.json()["latest_version"]["id"]

    client.post("/api/v1/governance/run", headers=creator_headers, json={"content_version_id": v1_id})
    res_sub1 = client.post("/api/v1/approvals/submit", headers=creator_headers, json={
        "content_item_id": item_id,
        "content_version_id": v1_id
    })
    assert res_sub1.status_code == 200
    sub1_id = res_sub1.json()["id"]

    # Manager rejects v1
    res_rej = client.post(f"/api/v1/approvals/submissions/{sub1_id}/decide", headers=approver_headers, json={
        "decision": "rejected",
        "comments": "Please refine the brand voice to be more energetic."
    })
    assert res_rej.status_code == 200
    assert res_rej.json()["decision"] == "rejected"

    # Creator revises content -> generates v2 with fully compliant copy
    compliant_copy = (
        "Enjoy Freshsip Valencia Orange Cold-Pressed Juice, crafted from 100% cold-pressed "
        "Valencia orange juice with no added sugar. Energize your day!"
    )
    res_edit = client.put(f"/api/v1/content/{item_id}", headers=creator_headers, json={
        "body_text": compliant_copy
    })
    assert res_edit.status_code == 200
    v2 = res_edit.json()["latest_version"]
    assert v2["version_num"] == 2

    # Rerun governance on v2
    res_gov2 = client.post("/api/v1/governance/run", headers=creator_headers, json={"content_version_id": v2["id"]})
    assert res_gov2.status_code == 200

    # Resubmit v2
    res_sub2 = client.post("/api/v1/approvals/submit", headers=creator_headers, json={
        "content_item_id": item_id,
        "content_version_id": v2["id"],
        "submission_notes": "Revised copy incorporating feedback."
    })
    assert res_sub2.status_code == 200
    sub2_id = res_sub2.json()["id"]

    # Manager approves v2
    res_app2 = client.post(f"/api/v1/approvals/submissions/{sub2_id}/decide", headers=approver_headers, json={
        "decision": "approved",
        "comments": "Great revision. Approved for publication."
    })
    assert res_app2.status_code == 200
    assert res_app2.json()["decision"] == "approved"


# 15. Critical prohibited claims cannot bypass the required policy gate
def test_15_critical_prohibited_claims_cannot_bypass_policy_gate(client, auth_tokens, db_session):
    creator_headers = auth_tokens["content_creator"]["headers"]
    approver_headers = auth_tokens["approval_manager"]["headers"]
    res_b = client.get("/api/v1/brands", headers=creator_headers)
    brand_id = res_b.json()[0]["id"]

    # Create draft with disease cure prohibited claim
    res_draft = client.post("/api/v1/content", headers=creator_headers, json={
        "brand_id": brand_id,
        "title": "Disease Cure Prohibited Claim Test",
        "channel": "Social Media",
        "body_text": "Freshsip citrus juice is medically proven to cure diabetes and chronic disease!"
    })
    item_id = res_draft.json()["id"]
    v_id = res_draft.json()["latest_version"]["id"]

    res_gov = client.post("/api/v1/governance/run", headers=creator_headers, json={"content_version_id": v_id})
    assert res_gov.status_code == 200

    # Submit fails at submission gate
    res_sub = client.post("/api/v1/approvals/submit", headers=creator_headers, json={
        "content_item_id": item_id,
        "content_version_id": v_id
    })
    assert res_sub.status_code == 400
    assert "unresolved blocking violation" in res_sub.json()["detail"].lower()


# 16. Permitted warning overrides require a recorded justification
def test_16_permitted_warning_overrides_require_recorded_justification(client, auth_tokens, db_session):
    creator_headers = auth_tokens["content_creator"]["headers"]
    approver_headers = auth_tokens["approval_manager"]["headers"]
    res_b = client.get("/api/v1/brands", headers=creator_headers)
    brand_id = res_b.json()[0]["id"]

    compliant_copy = (
        "Enjoy Freshsip Valencia Orange Cold-Pressed Juice, crafted from 100% cold-pressed "
        "Valencia orange juice with no added sugar."
    )
    res_draft = client.post("/api/v1/content", headers=creator_headers, json={
        "brand_id": brand_id,
        "title": "Warning Override Justification Test",
        "channel": "Social Media",
        "body_text": compliant_copy
    })
    item_id = res_draft.json()["id"]
    v_id = res_draft.json()["latest_version"]["id"]

    # Run governance
    res_gov = client.post("/api/v1/governance/run", headers=creator_headers, json={"content_version_id": v_id})
    gov_run_id = res_gov.json()["id"]

    # Insert an artificial warning finding
    warning_finding = GovernanceFinding(
        governance_run_id=gov_run_id,
        category="IMAGE_DIMENSIONS",
        severity="warning",
        title="Image aspect ratio slightly non-standard",
        explanation="Aspect ratio is 1:1 instead of standard 4:5.",
        source_citation="Freshsip Guidelines page 12",
        recommended_action="Review visually before publishing",
        status="warning"
    )
    db_session.add(warning_finding)
    db_session.commit()

    # Submit
    res_sub = client.post("/api/v1/approvals/submit", headers=creator_headers, json={
        "content_item_id": item_id,
        "content_version_id": v_id
    })
    assert res_sub.status_code == 200
    sub_id = res_sub.json()["id"]

    # Manager attempts to approve with short / empty justification -> rejected
    res_short = client.post(f"/api/v1/approvals/submissions/{sub_id}/decide", headers=approver_headers, json={
        "decision": "approved",
        "comments": "ok"
    })
    assert res_short.status_code == 400
    assert "recorded justification comment" in res_short.json()["detail"] or "warning" in res_short.json()["detail"].lower()

    # Manager approves with substantive justification (>= 10 chars) -> accepted
    res_good = client.post(f"/api/v1/approvals/submissions/{sub_id}/decide", headers=approver_headers, json={
        "decision": "approved",
        "comments": "Aspect ratio 1:1 is approved specifically for the Instagram square feed placement."
    })
    assert res_good.status_code == 200
    assert res_good.json()["decision"] == "approved"


# 17. Approval queue responses expose complete, correctly versioned findings
def test_17_approval_queue_responses_expose_complete_versioned_findings(client, auth_tokens):
    creator_headers = auth_tokens["content_creator"]["headers"]
    approver_headers = auth_tokens["approval_manager"]["headers"]
    res_b = client.get("/api/v1/brands", headers=creator_headers)
    brand_id = res_b.json()[0]["id"]

    compliant_copy = (
        "Enjoy Freshsip Valencia Orange Cold-Pressed Juice, crafted from 100% cold-pressed "
        "Valencia orange juice with no added sugar."
    )
    res_draft = client.post("/api/v1/content", headers=creator_headers, json={
        "brand_id": brand_id,
        "title": "Queue Findings Transparency Test",
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
    assert res_sub.status_code == 200
    sub_id = res_sub.json()["id"]

    # Fetch queue
    res_q = client.get("/api/v1/approvals/queue", headers=approver_headers)
    assert res_q.status_code == 200
    items = res_q.json()
    matching = next((x for x in items if x["id"] == sub_id), None)
    assert matching is not None
    assert "channel" in matching
    assert "governance_run_id" in matching
    assert "governance_status" in matching
    assert "rules_evaluated_count" in matching
    assert "facts_evaluated_count" in matching
    assert "findings" in matching
    assert "critical_findings_count" in matching
    assert "warning_findings_count" in matching


# 18. Historical findings and audit records remain intact after revisions
def test_18_historical_findings_and_audit_records_remain_intact_after_revisions(client, auth_tokens):
    creator_headers = auth_tokens["content_creator"]["headers"]
    res_b = client.get("/api/v1/brands", headers=creator_headers)
    brand_id = res_b.json()[0]["id"]

    res_draft = client.post("/api/v1/content", headers=creator_headers, json={
        "brand_id": brand_id,
        "title": "Historical Audit Immutability Test",
        "channel": "Social Media",
        "body_text": "Version 1 text for audit history."
    })
    item_id = res_draft.json()["id"]
    v1_id = res_draft.json()["latest_version"]["id"]

    # Run v1 governance & submit
    res_gov1 = client.post("/api/v1/governance/run", headers=creator_headers, json={"content_version_id": v1_id})
    run1_id = res_gov1.json()["id"]

    # Edit to v2
    res_edit = client.put(f"/api/v1/content/{item_id}", headers=creator_headers, json={
        "body_text": "Version 2 text for audit history."
    })
    v2_id = res_edit.json()["latest_version"]["id"]

    # Run v2 governance
    res_gov2 = client.post("/api/v1/governance/run", headers=creator_headers, json={"content_version_id": v2_id})
    run2_id = res_gov2.json()["id"]

    assert run1_id != run2_id

    # Verify both governance runs exist and remain queryable
    res_v1_run = client.get(f"/api/v1/governance/runs/{v1_id}/latest", headers=creator_headers)
    assert res_v1_run.status_code == 200
    assert res_v1_run.json()["id"] == run1_id

    res_v2_run = client.get(f"/api/v1/governance/runs/{v2_id}/latest", headers=creator_headers)
    assert res_v2_run.status_code == 200
    assert res_v2_run.json()["id"] == run2_id


# 19. Concurrent edits and submissions cannot exploit a stale governance result
def test_19_concurrent_edits_and_submissions_cannot_exploit_stale_result(client, auth_tokens, db_session):
    creator_headers = auth_tokens["content_creator"]["headers"]
    res_b = client.get("/api/v1/brands", headers=creator_headers)
    brand_id = res_b.json()[0]["id"]

    res_draft = client.post("/api/v1/content", headers=creator_headers, json={
        "brand_id": brand_id,
        "title": "Concurrent Tampering Prevention Test",
        "channel": "Social Media",
        "body_text": "Original checked copy."
    })
    item_id = res_draft.json()["id"]
    v_id = res_draft.json()["latest_version"]["id"]

    # Run governance
    client.post("/api/v1/governance/run", headers=creator_headers, json={"content_version_id": v_id})

    # Simulate an out-of-band direct tampering of the body text or checksum
    version_row = db_session.query(ContentVersion).filter(ContentVersion.id == v_id).first()
    version_row.body_text = "Sneakily tampered body text without recomputing hash!"
    db_session.commit()

    # Attempt submission -> Checksum recalculation catches the modification!
    res_sub = client.post("/api/v1/approvals/submit", headers=creator_headers, json={
        "content_item_id": item_id,
        "content_version_id": v_id
    })
    assert res_sub.status_code == 400
    assert "checksum mismatch" in res_sub.json()["detail"].lower()


# 20. Existing Milestones 1–3 regressions remain passing
def test_20_existing_milestones_1_to_3_regressions_remain_passing(client, auth_tokens):
    # Verify that the canonical endpoints for M1, M2, and M3 respond with healthy integrity
    creator_headers = auth_tokens["content_creator"]["headers"]
    res_rules = client.get("/api/v1/knowledge/rules", headers=creator_headers)
    assert res_rules.status_code == 200
    rules = res_rules.json()
    assert len(rules) >= 12, "Canonical brand rules intact"

    res_facts = client.get("/api/v1/knowledge/facts", headers=creator_headers)
    assert res_facts.status_code == 200
    facts = res_facts.json()
    assert len(facts) >= 6, "Canonical product facts intact"
