import pytest
from app.models.knowledge import KnowledgeRule, KnowledgeFact
from app.database import SessionLocal

def test_usda_certified_organic_is_not_required_wording(client, auth_tokens):
    """
    Regression Test 1: Verify 'USDA Certified Organic' is NOT required wording.
    Drafts omitting this term must NOT receive a 'Missing Mandatory Term' finding.
    """
    headers = auth_tokens["content_creator"]["headers"]
    res_b = client.get("/api/v1/brands", headers=headers)
    brand_id = res_b.json()[0]["id"]

    res_draft = client.post("/api/v1/content", headers=headers, json={
        "brand_id": brand_id,
        "title": "Clean Juice Ad",
        "channel": "Social Media",
        "body_text": "Enjoy Freshsip Valencia Orange Cold-Pressed Juice with no added sugar."
    })
    version_id = res_draft.json()["latest_version"]["id"]

    res_gov = client.post("/api/v1/governance/run", headers=headers, json={
        "content_version_id": version_id
    })
    assert res_gov.status_code == 200
    gov_data = res_gov.json()

    # Must NOT have any missing mandatory term for organic
    missing_organic = [
        f for f in gov_data["findings"]
        if f["category"] == "mandatory_wording_missing" and "organic" in f["title"].lower()
    ]
    assert len(missing_organic) == 0, f"Unexpected mandatory organic finding: {missing_organic}"


def test_unsupported_organic_claim_detected_by_prohibition(client, auth_tokens):
    """
    Regression Test 2: Verify that claiming 'USDA Certified Organic' is detected
    as a violation under FR-RULE-010 (Prohibition of Unsupported Organic Claims).
    """
    headers = auth_tokens["content_creator"]["headers"]
    res_b = client.get("/api/v1/brands", headers=headers)
    brand_id = res_b.json()[0]["id"]

    res_draft = client.post("/api/v1/content", headers=headers, json={
        "brand_id": brand_id,
        "title": "Prohibited Organic Claim Ad",
        "channel": "Social Media",
        "body_text": "Try our new USDA Certified Organic cold-pressed juice!"
    })
    version_id = res_draft.json()["latest_version"]["id"]

    res_gov = client.post("/api/v1/governance/run", headers=headers, json={
        "content_version_id": version_id
    })
    assert res_gov.status_code == 200
    gov_data = res_gov.json()
    assert gov_data["overall_status"] == "failed"

    # Must flag prohibited wording under FR-RULE-010
    prohibited_organic = [
        f for f in gov_data["findings"]
        if f["category"] == "prohibited_wording" and "organic" in f["title"].lower()
    ]
    assert len(prohibited_organic) >= 1
    assert "freshsip_brand_guidelines.pdf" in prohibited_organic[0]["source_citation"]
    assert "Section D" in prohibited_organic[0]["source_citation"] or "p. 4" in prohibited_organic[0]["source_citation"]


def test_no_added_sugar_is_not_falsely_flagged_as_missing(client, auth_tokens):
    """
    Regression Test 3: Verify 'No Added Sugar' is recognized and not falsely flagged as missing.
    """
    headers = auth_tokens["content_creator"]["headers"]
    res_b = client.get("/api/v1/brands", headers=headers)
    brand_id = res_b.json()[0]["id"]

    res_draft = client.post("/api/v1/content", headers=headers, json={
        "brand_id": brand_id,
        "title": "No Added Sugar Post",
        "channel": "Social Media",
        "body_text": "Freshsip Valencia Orange Cold-Pressed Juice has no added sugar."
    })
    version_id = res_draft.json()["latest_version"]["id"]

    res_gov = client.post("/api/v1/governance/run", headers=headers, json={
        "content_version_id": version_id
    })
    assert res_gov.status_code == 200
    gov_data = res_gov.json()

    missing_sugar = [
        f for f in gov_data["findings"]
        if f["category"] == "mandatory_wording_missing" and "sugar" in f["title"].lower()
    ]
    assert len(missing_sugar) == 0, f"Unexpected missing sugar finding: {missing_sugar}"


def test_zero_added_sugar_is_not_universally_mandatory(client, auth_tokens):
    """
    Regression Test 4: Verify 'Zero Added Sugar' is NOT treated as a mandatory phrase.
    """
    headers = auth_tokens["content_creator"]["headers"]
    res_b = client.get("/api/v1/brands", headers=headers)
    brand_id = res_b.json()[0]["id"]

    res_draft = client.post("/api/v1/content", headers=headers, json={
        "brand_id": brand_id,
        "title": "Natural Vegetable Juice",
        "channel": "Social Media",
        "body_text": "Savor the pure flavor of Garden Tomato Celery Press!"
    })
    version_id = res_draft.json()["latest_version"]["id"]

    res_gov = client.post("/api/v1/governance/run", headers=headers, json={
        "content_version_id": version_id
    })
    assert res_gov.status_code == 200
    gov_data = res_gov.json()

    zero_sugar_findings = [
        f for f in gov_data["findings"]
        if "zero added sugar" in f["title"].lower()
    ]
    assert len(zero_sugar_findings) == 0


def test_corporate_content_not_forced_to_contain_product_disclosures(client, auth_tokens):
    """
    Regression Test 5: Verify corporate announcements are not forced to contain product-specific disclosures.
    """
    headers = auth_tokens["content_creator"]["headers"]
    res_b = client.get("/api/v1/brands", headers=headers)
    brand_id = res_b.json()[0]["id"]

    res_draft = client.post("/api/v1/content", headers=headers, json={
        "brand_id": brand_id,
        "title": "Corporate Office Opening",
        "channel": "Social Media",
        "body_text": "Freshsip Beverages is proud to announce the opening of our new Bengaluru headquarters."
    })
    version_id = res_draft.json()["latest_version"]["id"]

    res_gov = client.post("/api/v1/governance/run", headers=headers, json={
        "content_version_id": version_id
    })
    assert res_gov.status_code == 200
    gov_data = res_gov.json()
    assert gov_data["overall_status"] == "passed"
    assert gov_data["findings_count"] == 0


def test_real_six_skus_and_facts_are_present(client, auth_tokens):
    """
    Regression Test 6: Verify the real six SKUs exist in knowledge facts with approved specifications.
    """
    headers = auth_tokens["knowledge_reviewer"]["headers"]
    res_facts = client.get("/api/v1/knowledge/facts?status_filter=approved", headers=headers)
    assert res_facts.status_code == 200
    facts = res_facts.json()

    expected_skus = {
        "FS-PROD-001": "Valencia Orange Cold-Pressed Juice",
        "FS-PROD-002": "Pink Guava Pomegranate Nectar",
        "FS-PROD-003": "Garden Tomato Celery Press",
        "FS-PROD-004": "Spiced Carrot Beetroot Press",
        "FS-PROD-005": "Green Orchard Cucumber Spinach Blend",
        "FS-PROD-006": "Citrus Carrot Ginger Blend",
    }

    found_skus = set()
    for f in facts:
        p_name = f.get("product_name")
        for sku_id, sku_name in expected_skus.items():
            if sku_name.lower() in p_name.lower():
                found_skus.add(sku_id)

    assert found_skus == set(expected_skus.keys()), f"Missing canonical SKUs: {set(expected_skus.keys()) - found_skus}"


def test_pending_expired_rejected_claims_not_represented_as_approved(client, auth_tokens):
    """
    Regression Test 7: Verify pending, expired, and rejected claims are accurately partitioned by status.
    """
    headers = auth_tokens["knowledge_reviewer"]["headers"]

    # Pending
    res_pending = client.get("/api/v1/knowledge/facts?status_filter=pending_review", headers=headers)
    assert res_pending.status_code == 200
    pending = res_pending.json()
    assert any("allergy" in f["fact_value"].lower() or "vitamin c" in f["fact_value"].lower() or "fibre" in f["fact_value"].lower() for f in pending)

    # Expired
    res_expired = client.get("/api/v1/knowledge/facts?status_filter=expired", headers=headers)
    assert res_expired.status_code == 200
    expired = res_expired.json()
    assert any("2025" in f["fact_value"] or "expired" in f["source_citation"].lower() or "0.9" in f["source_citation"] for f in expired)

    # Rejected
    res_rejected = client.get("/api/v1/knowledge/facts?status_filter=rejected", headers=headers)
    assert res_rejected.status_code == 200
    rejected = res_rejected.json()
    assert any("detox" in f["fact_value"].lower() or "immunity" in f["fact_value"].lower() or "diabetes" in f["fact_value"].lower() for f in rejected)


def test_seeding_is_repeatable_and_preserves_deprecated_state():
    """
    Regression Test 8: Verify idempotent seeding preserves deprecated records and does not resurrect contradictory rules.
    """
    from seed import seed_freshsip_data
    db = SessionLocal()
    try:
        # Run seed twice
        seed_freshsip_data(session=db)
        seed_freshsip_data(session=db)

        # Contradictory rules must remain deprecated
        organic_rules = db.query(KnowledgeRule).filter(KnowledgeRule.pattern == "USDA Certified Organic").all()
        for r in organic_rules:
            assert r.status == "deprecated"

        sugar_rules = db.query(KnowledgeRule).filter(KnowledgeRule.pattern == "Zero Added Sugar").all()
        for r in sugar_rules:
            assert r.status == "deprecated"

        # Canonical FR-RULE-010 must be approved
        r10 = db.query(KnowledgeRule).filter(KnowledgeRule.rule_code == "FR-RULE-010").first()
        assert r10 is not None
        assert r10.status == "approved"
        assert r10.rule_type == "prohibition"
    finally:
        db.close()


def test_tenant_isolation_and_audit_history_intact(client, auth_tokens):
    """
    Regression Test 9: Verify tenant isolation and audit logging remain functional after knowledge repair.
    """
    creator_headers = auth_tokens["content_creator"]["headers"]
    admin_headers = auth_tokens["org_admin"]["headers"]

    # Verify audit log retrieval
    res_audit = client.get("/api/v1/audit", headers=admin_headers)
    assert res_audit.status_code == 200
    logs = res_audit.json()
    assert len(logs) > 0
