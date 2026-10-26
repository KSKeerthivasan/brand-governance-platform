import pytest

def test_full_e2e_freshsip_governance_journey(client, auth_tokens):
    """
    End-to-End Scenario matching Section 11:
    1. Access the Freshsip workspace.
    2. Review and approve a candidate knowledge record.
    3. Create marketing content containing a known unsupported claim.
    4. Run the check.
    5. Inspect the finding and its approved source.
    6. Revise the content.
    7. Create a new version and rerun checks.
    8. Submit that version.
    9. Approve it using the authorized approver identity.
    10. Verify the exact version and audit history.
    """
    admin_h = auth_tokens["org_admin"]["headers"]
    reviewer_h = auth_tokens["knowledge_reviewer"]["headers"]
    creator_h = auth_tokens["content_creator"]["headers"]
    approver_h = auth_tokens["approval_manager"]["headers"]

    # -------------------------------------------------------------
    # Step 1: Access Freshsip workspace
    # -------------------------------------------------------------
    res_org = client.get("/api/v1/organizations/current", headers=creator_h)
    assert res_org.status_code == 200
    org = res_org.json()
    assert org["slug"] == "freshsip"

    res_brand = client.get("/api/v1/brands", headers=creator_h)
    assert res_brand.status_code == 200
    brand_id = res_brand.json()[0]["id"]

    # -------------------------------------------------------------
    # Step 2: Knowledge Reviewer inspects & approves candidate rule
    # -------------------------------------------------------------
    res_rules = client.get("/api/v1/knowledge/rules?status_filter=pending_review", headers=reviewer_h)
    assert res_rules.status_code == 200
    pending_rules = res_rules.json()
    
    # If there is a pending rule, approve it
    if pending_rules:
        target_rule = pending_rules[0]
        res_review = client.post(f"/api/v1/knowledge/rules/{target_rule['id']}/review", headers=reviewer_h, json={
            "status": "approved",
            "review_notes": "Reviewed and approved by Rachel Reviewer during audit."
        })
        assert res_review.status_code == 200
        assert res_review.json()["status"] == "approved"

    # -------------------------------------------------------------
    # Step 3: Creator creates draft containing unsupported claim & prohibited word
    # -------------------------------------------------------------
    initial_text = (
        "Freshsip Sparkling Citrus is a miracle elixir that cures chronic illness! "
        "Contains 30g sugar and guarantees rapid fat burning results."
    )
    res_draft = client.post("/api/v1/content", headers=creator_h, json={
        "brand_id": brand_id,
        "title": "Summer Social Blitz 2026",
        "channel": "Social Media",
        "body_text": initial_text
    })
    assert res_draft.status_code == 200
    draft_item = res_draft.json()
    content_id = draft_item["id"]
    v1_id = draft_item["latest_version"]["id"]
    assert draft_item["current_version_num"] == 1

    # -------------------------------------------------------------
    # Step 4: Run the governance check on v1
    # -------------------------------------------------------------
    res_check1 = client.post("/api/v1/governance/run", headers=creator_h, json={
        "content_version_id": v1_id
    })
    assert res_check1.status_code == 200
    check1_data = res_check1.json()
    assert check1_data["overall_status"] == "failed"
    assert check1_data["findings_count"] > 0

    # -------------------------------------------------------------
    # Step 5: Inspect findings and approved sources
    # -------------------------------------------------------------
    findings = check1_data["findings"]
    prohibited_f = [f for f in findings if f["category"] == "prohibited_wording"]
    unsupported_f = [f for f in findings if f["category"] == "unsupported_claim"]
    mismatch_f = [f for f in findings if f["category"] == "product_fact_mismatch"]

    assert len(prohibited_f) >= 1
    assert len(unsupported_f) >= 1
    assert unsupported_f[0]["source_citation"] == "SUPPORTING EVIDENCE NOT FOUND"
    assert "freshsip" in prohibited_f[0]["source_citation"].lower() or "brand" in prohibited_f[0]["source_citation"].lower()

    # -------------------------------------------------------------
    # Step 6 & 7: Revise the content -> Creates v2 and rerun checks
    # -------------------------------------------------------------
    revised_compliant_text = (
        "Energize your afternoon with Freshsip Sparkling Citrus! "
        "Crafted with crisp botanicals, Zero Added Sugar, and 45mg green tea caffeine. "
        "USDA Certified Organic and naturally refreshing."
    )
    res_edit = client.put(f"/api/v1/content/{content_id}", headers=creator_h, json={
        "body_text": revised_compliant_text
    })
    assert res_edit.status_code == 200
    edited_data = res_edit.json()
    assert edited_data["current_version_num"] == 2
    v2_id = edited_data["latest_version"]["id"]
    assert v2_id != v1_id

    # Rerun checks on v2
    res_check2 = client.post("/api/v1/governance/run", headers=creator_h, json={
        "content_version_id": v2_id
    })
    assert res_check2.status_code == 200
    check2_data = res_check2.json()
    assert check2_data["overall_status"] == "passed"
    assert check2_data["findings_count"] == 0

    # -------------------------------------------------------------
    # Step 8: Creator submits v2 for approval
    # -------------------------------------------------------------
    res_sub = client.post("/api/v1/approvals/submit", headers=creator_h, json={
        "content_item_id": content_id,
        "content_version_id": v2_id,
        "submission_notes": "All governance findings resolved. Ready for final publication approval."
    })
    assert res_sub.status_code == 200
    sub_data = res_sub.json()
    submission_id = sub_data["id"]
    assert sub_data["status"] == "pending"
    assert sub_data["version_num"] == 2

    # -------------------------------------------------------------
    # Step 9: Approval Manager approves the submitted version
    # -------------------------------------------------------------
    res_decide = client.post(f"/api/v1/approvals/submissions/{submission_id}/decide", headers=approver_h, json={
        "decision": "approved",
        "comments": "All claims verified against approved brand knowledge. Approved for publication."
    })
    assert res_decide.status_code == 200
    dec_data = res_decide.json()
    assert dec_data["decision"] == "approved"
    assert dec_data["decision_label"] == "Approved — Ready to Publish"
    assert dec_data["content_version_id"] == v2_id

    # -------------------------------------------------------------
    # Step 10: Verify exact version integrity and audit history
    # -------------------------------------------------------------
    res_final_item = client.get(f"/api/v1/content/{content_id}", headers=creator_h)
    assert res_final_item.status_code == 200
    final_item = res_final_item.json()
    assert final_item["status"] == "approved"
    assert final_item["current_version_num"] == 2

    # Verify audit events recorded the journey
    res_audit = client.get("/api/v1/audit?limit=20", headers=admin_h)
    assert res_audit.status_code == 200
    audit_events = res_audit.json()
    event_types = [e["event_type"] for e in audit_events]
    
    assert "CONTENT_CREATED" in event_types
    assert "GOVERNANCE_CHECK_RUN" in event_types
    assert "CONTENT_REVISED" in event_types
    assert "APPROVAL_SUBMITTED" in event_types
    assert "APPROVAL_APPROVED" in event_types
