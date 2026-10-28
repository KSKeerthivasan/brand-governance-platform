import pytest

def test_creator_cannot_approve_own_content(client, auth_tokens):
    creator_headers = auth_tokens["content_creator"]["headers"]
    res_b = client.get("/api/v1/brands", headers=creator_headers)
    brand_id = res_b.json()[0]["id"]

    # Create draft
    res_draft = client.post("/api/v1/content", headers=creator_headers, json={
        "brand_id": brand_id,
        "title": "Self Approval Security Test",
        "channel": "Social Media",
        "body_text": "Sample text for self approval test."
    })
    content_id = res_draft.json()["id"]
    version_id = res_draft.json()["latest_version"]["id"]

    # Run governance first to satisfy fail-closed precondition
    res_gov = client.post("/api/v1/governance/run", headers=creator_headers, json={
        "content_version_id": version_id
    })
    assert res_gov.status_code == 200

    # Submit
    res_sub = client.post("/api/v1/approvals/submit", headers=creator_headers, json={
        "content_item_id": content_id,
        "content_version_id": version_id,
        "submission_notes": "Attempting self approval test."
    })
    assert res_sub.status_code == 200
    sub_id = res_sub.json()["id"]

    # Creator attempts to approve their own content -> Must be rejected with 403 Forbidden!
    res_self_app = client.post(f"/api/v1/approvals/submissions/{sub_id}/decide", headers=creator_headers, json={
        "decision": "approved",
        "comments": "Self approving my own post."
    })
    assert res_self_app.status_code == 403
    assert "Permission Denied" in res_self_app.json()["detail"] or "Conflict of Interest" in res_self_app.json()["detail"]

def test_approval_manager_approves_submission_with_official_label(client, auth_tokens):
    creator_headers = auth_tokens["content_creator"]["headers"]
    approver_headers = auth_tokens["approval_manager"]["headers"]
    res_b = client.get("/api/v1/brands", headers=creator_headers)
    brand_id = res_b.json()[0]["id"]

    # Create draft
    res_draft = client.post("/api/v1/content", headers=creator_headers, json={
        "brand_id": brand_id,
        "title": "Official Approval Label Test",
        "channel": "Social Media",
        "body_text": "Compliant text ready for executive signoff."
    })
    content_id = res_draft.json()["id"]
    version_id = res_draft.json()["latest_version"]["id"]

    # Run governance first to satisfy fail-closed precondition
    res_gov = client.post("/api/v1/governance/run", headers=creator_headers, json={
        "content_version_id": version_id
    })
    assert res_gov.status_code == 200

    # Submit
    res_sub = client.post("/api/v1/approvals/submit", headers=creator_headers, json={
        "content_item_id": content_id,
        "content_version_id": version_id,
        "submission_notes": "Ready for manager sign-off."
    })
    assert res_sub.status_code == 200
    sub_id = res_sub.json()["id"]

    # Manager approves
    res_dec = client.post(f"/api/v1/approvals/submissions/{sub_id}/decide", headers=approver_headers, json={
        "decision": "approved",
        "comments": "Verified against brand guidelines. Approved."
    })
    assert res_dec.status_code == 200
    dec_data = res_dec.json()
    assert dec_data["decision"] == "approved"
    assert dec_data["decision_label"] == "Approved — Ready to Publish"
