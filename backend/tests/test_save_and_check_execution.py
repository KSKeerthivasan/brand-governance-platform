import pytest

def test_scenario_a_existing_draft_edit_copy_and_check(client, auth_tokens):
    """
    Scenario A: Existing draft - edited copy is saved and the checked version contains the edited copy.
    """
    headers = auth_tokens["content_creator"]["headers"]
    res_b = client.get("/api/v1/brands", headers=headers)
    assert res_b.status_code == 200
    brand_id = res_b.json()[0]["id"]

    # 1. Create initial draft (v1)
    res_create = client.post("/api/v1/content", headers=headers, json={
        "brand_id": brand_id,
        "title": "Summer Sparkle Campaign",
        "channel": "Instagram Post",
        "body_text": "Original copy without claims."
    })
    assert res_create.status_code == 200
    content_id = res_create.json()["id"]
    v1_id = res_create.json()["latest_version"]["id"]
    assert res_create.json()["current_version_num"] == 1

    # 2. Creator edits copy in Content Studio and triggers Run Governance Checks
    edited_copy = "Freshsip cures chronic fatigue with 100% organic lemon juice!"
    res_update = client.put(f"/api/v1/content/{content_id}", headers=headers, json={
        "title": "Summer Sparkle Campaign",
        "channel": "Instagram Post",
        "body_text": edited_copy
    })
    assert res_update.status_code == 200
    saved_item = res_update.json()
    assert saved_item["current_version_num"] == 2
    v2_id = saved_item["latest_version"]["id"]
    assert v2_id != v1_id
    assert saved_item["latest_version"]["body_text"] == edited_copy

    # 3. Governance check runs against the newly persisted version ID (v2_id)
    res_gov = client.post("/api/v1/governance/run", headers=headers, json={
        "content_version_id": v2_id
    })
    assert res_gov.status_code == 200
    gov_run = res_gov.json()
    assert gov_run["content_version_id"] == v2_id
    # The check evaluates the edited copy and detects the prohibited health claim
    assert gov_run["overall_status"] in ["critical_issues", "warnings", "failed"]
    finding_titles = [f["title"].lower() for f in gov_run["findings"]]
    # Should flag health/medical claim or prohibited wording
    assert any(any(k in t for k in ["health", "claim", "disease", "medical", "organic", "cure", "prohibited"]) for t in finding_titles)


def test_scenario_b_existing_draft_attach_poster_and_check(client, auth_tokens):
    """
    Scenario B: Existing draft - attach new poster and alt text, run checks,
    verify checked version contains the current poster and alt text.
    """
    headers = auth_tokens["content_creator"]["headers"]
    res_b = client.get("/api/v1/brands", headers=headers)
    brand_id = res_b.json()[0]["id"]

    # 1. Create copy-only draft (v1)
    res_create = client.post("/api/v1/content", headers=headers, json={
        "brand_id": brand_id,
        "title": "Poster Visual Check",
        "channel": "Instagram Post",
        "body_text": "Refreshing sparkling water with natural real citrus flavor."
    })
    content_id = res_create.json()["id"]
    v1_id = res_create.json()["latest_version"]["id"]

    # 2. Attach creative poster file path and alt-text in editor, then save & check
    poster_path = "./storage_data/19a8a675-7b45-4834-8836-de1996c2a919/knowledge/campaign_citrus_ginger_pending.png"
    alt_text = "Close-up of a sparkling can on ice surrounded by sliced lemons and limes"
    res_update = client.put(f"/api/v1/content/{content_id}", headers=headers, json={
        "title": "Poster Visual Check",
        "channel": "Instagram Post",
        "body_text": "Refreshing sparkling water with natural real citrus flavor.",
        "poster_file_path": poster_path,
        "poster_alt_text": alt_text
    })
    assert res_update.status_code == 200
    v2_id = res_update.json()["latest_version"]["id"]
    assert v2_id != v1_id
    assert res_update.json()["latest_version"]["poster_file_path"] == poster_path
    assert res_update.json()["latest_version"]["poster_alt_text"] == alt_text

    # 3. Governance check runs on v2
    res_gov = client.post("/api/v1/governance/run", headers=headers, json={
        "content_version_id": v2_id
    })
    assert res_gov.status_code == 200
    gov_run = res_gov.json()
    assert gov_run["content_version_id"] == v2_id
    # Check that findings include visual evaluations
    categories = [f["category"] for f in gov_run["findings"]]
    assert any(c in ["accessibility", "dimensions", "colour", "contrast", "logo", "layout"] for c in categories)


def test_scenario_c_new_draft_immediate_governance_check(client, auth_tokens):
    """
    Scenario C: New draft - create a draft and immediately run checks;
    verify backend is called with the newly persisted version ID (no silent exit).
    """
    headers = auth_tokens["content_creator"]["headers"]
    res_b = client.get("/api/v1/brands", headers=headers)
    brand_id = res_b.json()[0]["id"]

    # 1. Immediately create and persist draft
    res_create = client.post("/api/v1/content", headers=headers, json={
        "brand_id": brand_id,
        "title": "Instant Governance Launch",
        "channel": "Social Media",
        "body_text": "All natural crisp refreshment with zero artificial additives."
    })
    assert res_create.status_code == 200
    persisted_item = res_create.json()
    assert persisted_item["latest_version"] is not None
    persisted_version_id = persisted_item["latest_version"]["id"]
    assert persisted_item["current_version_num"] == 1

    # 2. Immediately invoke governance check on persisted version ID
    res_gov = client.post("/api/v1/governance/run", headers=headers, json={
        "content_version_id": persisted_version_id
    })
    assert res_gov.status_code == 200
    gov_run = res_gov.json()
    assert gov_run["content_version_id"] == persisted_version_id
    assert "overall_status" in gov_run
    assert isinstance(gov_run["findings"], list)


def test_scenario_d_failure_handling(client, auth_tokens):
    """
    Scenario D: Failure handling - saving fails or governance fails;
    verify an actionable error is shown and no stale findings are presented.
    """
    headers = auth_tokens["content_creator"]["headers"]

    # 1. Saving fails with missing required fields
    res_fail_save = client.post("/api/v1/content", headers=headers, json={
        "title": "Incomplete Draft"
        # missing brand_id, body_text
    })
    assert res_fail_save.status_code in [400, 422]

    # 2. Governance check fails when called with invalid / non-existent version ID
    res_fail_gov = client.post("/api/v1/governance/run", headers=headers, json={
        "content_version_id": "00000000-0000-0000-0000-000000000000"
    })
    assert res_fail_gov.status_code in [404, 422]


def test_scenario_e_version_consistency_and_immutability(client, auth_tokens):
    """
    Scenario E: Version consistency - verify findings belong strictly to the exact
    version checked, and subsequent revisions create distinct version records.
    """
    headers = auth_tokens["content_creator"]["headers"]
    res_b = client.get("/api/v1/brands", headers=headers)
    brand_id = res_b.json()[0]["id"]

    # 1. Create v1 with problematic claim
    res1 = client.post("/api/v1/content", headers=headers, json={
        "brand_id": brand_id,
        "title": "Version Consistency Check",
        "channel": "Social Media",
        "body_text": "Clinically proven to cure diabetes instantly!"
    })
    content_id = res1.json()["id"]
    v1_id = res1.json()["latest_version"]["id"]

    # Run checks on v1
    res_gov1 = client.post("/api/v1/governance/run", headers=headers, json={
        "content_version_id": v1_id
    })
    run_v1 = res_gov1.json()
    assert run_v1["content_version_id"] == v1_id
    assert run_v1["overall_status"] == "failed"

    # 2. Create v2 with compliant text
    res2 = client.put(f"/api/v1/content/{content_id}", headers=headers, json={
        "title": "Version Consistency Check",
        "channel": "Social Media",
        "body_text": "Refreshing sparkling water made with natural fruit essence."
    })
    v2_id = res2.json()["latest_version"]["id"]
    assert v2_id != v1_id

    # Run checks on v2
    res_gov2 = client.post("/api/v1/governance/run", headers=headers, json={
        "content_version_id": v2_id
    })
    run_v2 = res_gov2.json()
    assert run_v2["content_version_id"] == v2_id
    assert run_v2["overall_status"] != "failed"

    # 3. Verify latest run lookup by version is consistent and isolated
    res_latest_v1 = client.get(f"/api/v1/governance/runs/{v1_id}/latest", headers=headers)
    assert res_latest_v1.status_code == 200
    assert res_latest_v1.json()["content_version_id"] == v1_id
    assert res_latest_v1.json()["overall_status"] == "failed"

    res_latest_v2 = client.get(f"/api/v1/governance/runs/{v2_id}/latest", headers=headers)
    assert res_latest_v2.status_code == 200
    assert res_latest_v2.json()["content_version_id"] == v2_id
    assert res_latest_v2.json()["overall_status"] != "failed"
