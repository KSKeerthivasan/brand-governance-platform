import os
import pytest
from app.models.content import ContentVersion

def test_poster_governance_integration_and_versioning(client, auth_tokens):
    creator_headers = auth_tokens["content_creator"]["headers"]
    mgr_headers = auth_tokens["approval_manager"]["headers"]

    # 1. Fetch Brand ID
    res_b = client.get("/api/v1/brands", headers=creator_headers)
    assert res_b.status_code == 200
    brand_id = res_b.json()[0]["id"]

    # Locate available test poster image
    test_poster_path = "./storage_data/19a8a675-7b45-4834-8836-de1996c2a919/knowledge/campaign_citrus_ginger_pending.png"
    assert os.path.exists(test_poster_path), "Test poster image file must exist on disk"

    # 2. Create content draft WITH an attached poster
    res_create = client.post("/api/v1/content", headers=creator_headers, json={
        "brand_id": brand_id,
        "title": "Summer Citrus Splash Ad",
        "channel": "Instagram Post",
        "body_text": "Refresh your summer with Freshsip Sparkling Citrus! 100% cold-pressed valencia oranges.",
        "poster_file_path": test_poster_path,
        "poster_alt_text": "Cold-pressed citrus sparkling beverage bottle against summer foliage background"
    })
    assert res_create.status_code == 200
    draft = res_create.json()
    assert draft["title"] == "Summer Citrus Splash Ad"
    assert draft["current_version_num"] == 1
    assert draft["status"] == "draft"

    v1 = draft["latest_version"]
    assert v1["poster_file_path"] == test_poster_path
    assert v1["poster_alt_text"] == "Cold-pressed citrus sparkling beverage bottle against summer foliage background"
    assert v1["poster_url"] == f"/api/v1/content/versions/{v1['id']}/poster"
    v1_checksum = v1["checksum"]
    assert len(v1_checksum) == 64

    # 3. Stream the poster image via endpoint
    res_poster_img = client.get(v1["poster_url"], headers=creator_headers)
    assert res_poster_img.status_code == 200
    assert res_poster_img.headers["content-type"] in ["image/png", "image/jpeg"]
    assert len(res_poster_img.content) > 0

    # 4. Run Unified Governance on Version 1
    res_gov = client.post("/api/v1/governance/run", headers=creator_headers, json={
        "content_version_id": v1["id"]
    })
    assert res_gov.status_code == 200
    gov = res_gov.json()
    assert gov["findings_count"] > 0
    categories = [f["category"] for f in gov["findings"]]

    # Verify unified findings include visual categories and text checks
    assert "dimensions" in categories
    assert "colour" in categories
    assert "contrast" in categories
    assert "logo" in categories
    assert "accessibility" in categories
    assert "layout" in categories

    # Verify visual findings contain real result statuses
    visual_statuses = [f["status"] for f in gov["findings"] if f["category"] in ("dimensions", "colour", "contrast", "accessibility", "layout")]
    assert any(s in ("passed_check", "verified_issue", "unable_to_verify") for s in visual_statuses)

    # 5. Revise content draft: update poster alt text / copy text
    # This must generate Version 2 with a new checksum
    res_update = client.put(f"/api/v1/content/{draft['id']}", headers=creator_headers, json={
        "title": "Summer Citrus Splash Ad (Revised)",
        "channel": "Instagram Post",
        "body_text": "Refresh your day with authentic Freshsip Sparkling Citrus! Valencia orange goodness.",
        "poster_file_path": test_poster_path,
        "poster_alt_text": "Updated high-contrast Freshsip Sparkling Citrus bottle on dark forest green background"
    })
    assert res_update.status_code == 200
    updated_draft = res_update.json()
    assert updated_draft["current_version_num"] == 2
    assert updated_draft["status"] == "draft"

    v2 = updated_draft["latest_version"]
    assert v2["version_num"] == 2
    assert v2["checksum"] != v1_checksum, "Changing copy or poster must produce a new checksum"

    # Run governance on v2 to satisfy fail-closed precondition
    res_gov_v2 = client.post("/api/v1/governance/run", headers=creator_headers, json={
        "content_version_id": v2["id"]
    })
    assert res_gov_v2.status_code == 200

    # 6. Submit Version 2 for human approval
    res_submit = client.post("/api/v1/approvals/submit", headers=creator_headers, json={
        "content_item_id": draft["id"],
        "content_version_id": v2["id"],
        "submission_notes": "All brand colors verified. Alt-text descriptive. Ready for review."
    })
    assert res_submit.status_code == 200
    submission = res_submit.json()
    assert submission["status"] == "pending"
    assert submission["version_num"] == 2
    assert submission["poster_file_path"] == test_poster_path
    assert submission["poster_alt_text"] == "Updated high-contrast Freshsip Sparkling Citrus bottle on dark forest green background"
    assert submission["poster_url"] == f"/api/v1/content/versions/{v2['id']}/poster"

    # 7. Check Approval Queue as Approval Manager
    res_queue = client.get("/api/v1/approvals/queue", headers=mgr_headers)
    assert res_queue.status_code == 200
    queue = res_queue.json()
    matching_sub = next((s for s in queue if s["id"] == submission["id"]), None)
    assert matching_sub is not None
    assert matching_sub["poster_url"] is not None
    assert matching_sub["version_num"] == 2

    # 8. Approve submission with official label
    res_decide = client.post(f"/api/v1/approvals/submissions/{submission['id']}/decide", headers=mgr_headers, json={
        "decision": "approved",
        "comments": "Visuals and copy align with Q4 guidelines. Approved."
    })
    assert res_decide.status_code == 200
    decision = res_decide.json()
    assert decision["decision_label"] == "Approved — Ready to Publish"

def test_copy_only_draft_still_works_without_poster(client, auth_tokens):
    creator_headers = auth_tokens["content_creator"]["headers"]
    res_b = client.get("/api/v1/brands", headers=creator_headers)
    brand_id = res_b.json()[0]["id"]

    # Create copy-only draft (no poster)
    res_create = client.post("/api/v1/content", headers=creator_headers, json={
        "brand_id": brand_id,
        "title": "Copy Only Newsletter Draft",
        "channel": "Email Newsletter",
        "body_text": "Join our community newsletter for weekly cold-pressed recipe updates."
    })
    assert res_create.status_code == 200
    draft = res_create.json()
    assert draft["latest_version"]["poster_file_path"] is None
    assert draft["latest_version"]["poster_url"] is None

    # Run governance check on copy-only draft
    res_gov = client.post("/api/v1/governance/run", headers=creator_headers, json={
        "content_version_id": draft["latest_version"]["id"]
    })
    assert res_gov.status_code == 200
    gov = res_gov.json()
    # Visual checks should not be present in copy-only draft
    visual_categories = [f["category"] for f in gov["findings"] if f["category"] in ("dimensions", "colour", "contrast", "logo")]
    assert len(visual_categories) == 0
