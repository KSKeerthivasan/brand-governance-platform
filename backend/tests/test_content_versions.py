import pytest

def test_content_versioning_and_checksum(client, auth_tokens):
    headers = auth_tokens["content_creator"]["headers"]
    res_b = client.get("/api/v1/brands", headers=headers)
    brand_id = res_b.json()[0]["id"]

    # 1. Create v1
    res1 = client.post("/api/v1/content", headers=headers, json={
        "brand_id": brand_id,
        "title": "Version Track Draft",
        "channel": "Social Media",
        "body_text": "First iteration of draft text."
    })
    assert res1.status_code == 200
    content_id = res1.json()["id"]
    v1_id = res1.json()["latest_version"]["id"]
    v1_checksum = res1.json()["latest_version"]["checksum"]
    assert res1.json()["current_version_num"] == 1

    # 2. Update body text -> Creates v2
    res2 = client.put(f"/api/v1/content/{content_id}", headers=headers, json={
        "body_text": "Second iteration of draft text with enhancements."
    })
    assert res2.status_code == 200
    v2_id = res2.json()["latest_version"]["id"]
    v2_checksum = res2.json()["latest_version"]["checksum"]
    assert res2.json()["current_version_num"] == 2
    assert v1_id != v2_id
    assert v1_checksum != v2_checksum

    # 3. Verify version list preserves both
    res_versions = client.get(f"/api/v1/content/{content_id}/versions", headers=headers)
    assert res_versions.status_code == 200
    version_list = res_versions.json()
    assert len(version_list) == 2
    version_nums = [v["version_num"] for v in version_list]
    assert 1 in version_nums and 2 in version_nums

def test_editing_submitted_content_resets_status_and_creates_new_version(client, auth_tokens):
    creator_headers = auth_tokens["content_creator"]["headers"]
    approver_headers = auth_tokens["approval_manager"]["headers"]
    res_b = client.get("/api/v1/brands", headers=creator_headers)
    brand_id = res_b.json()[0]["id"]

    # 1. Create and submit draft
    res1 = client.post("/api/v1/content", headers=creator_headers, json={
        "brand_id": brand_id,
        "title": "Approval Lifecycle Test",
        "channel": "Social Media",
        "body_text": "Clean draft text for approval."
    })
    content_id = res1.json()["id"]
    v1_id = res1.json()["latest_version"]["id"]

    # Submit for approval
    res_sub = client.post("/api/v1/approvals/submit", headers=creator_headers, json={
        "content_item_id": content_id,
        "content_version_id": v1_id,
        "submission_notes": "Ready for manager review."
    })
    assert res_sub.status_code == 200

    # Approver approves v1
    sub_id = res_sub.json()["id"]
    res_app = client.post(f"/api/v1/approvals/submissions/{sub_id}/decide", headers=approver_headers, json={
        "decision": "approved",
        "comments": "Looks great, approved for release."
    })
    assert res_app.status_code == 200

    # Content item should now be approved
    item_res = client.get(f"/api/v1/content/{content_id}", headers=creator_headers)
    assert item_res.json()["status"] == "approved"

    # 2. Creator edits approved content
    res_edit = client.put(f"/api/v1/content/{content_id}", headers=creator_headers, json={
        "body_text": "Modified text after approval."
    })
    assert res_edit.status_code == 200
    data = res_edit.json()
    
    # Invariant: Must reset status to draft, generate v2, and NOT inherit approved state!
    assert data["status"] == "draft"
    assert data["current_version_num"] == 2
    assert data["latest_version"]["version_num"] == 2
