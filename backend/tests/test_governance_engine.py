import pytest

def test_governance_detects_prohibited_words_and_citations(client, auth_tokens):
    headers = auth_tokens["content_creator"]["headers"]
    
    # 1. Get Brand
    res_b = client.get("/api/v1/brands", headers=headers)
    assert res_b.status_code == 200
    brand_id = res_b.json()[0]["id"]

    # 2. Create content draft with prohibited wording
    res_draft = client.post("/api/v1/content", headers=headers, json={
        "brand_id": brand_id,
        "title": "Prohibited Test Draft",
        "channel": "Social Media",
        "body_text": "This beverage is a miracle cure for dehydration! USDA Certified Organic and Zero Added Sugar."
    })
    assert res_draft.status_code == 200
    draft_data = res_draft.json()
    version_id = draft_data["latest_version"]["id"]

    # 3. Run governance checks
    res_gov = client.post("/api/v1/governance/run", headers=headers, json={
        "content_version_id": version_id
    })
    assert res_gov.status_code == 200
    gov_data = res_gov.json()
    assert gov_data["overall_status"] == "failed"
    
    findings = gov_data["findings"]
    prohibited_findings = [f for f in findings if f["category"] == "prohibited_wording"]
    assert len(prohibited_findings) >= 2
    
    # Check that citations are present and not fabricated
    for f in prohibited_findings:
        assert f["source_citation"] != ""
        assert "freshsip_brand_guidelines.pdf" in f["source_citation"] or "Brand Guidelines" in f["source_citation"]

def test_governance_detects_unsupported_health_claims(client, auth_tokens):
    headers = auth_tokens["content_creator"]["headers"]
    res_b = client.get("/api/v1/brands", headers=headers)
    brand_id = res_b.json()[0]["id"]

    # Create draft with medical claims
    res_draft = client.post("/api/v1/content", headers=headers, json={
        "brand_id": brand_id,
        "title": "Unsupported Health Claim Draft",
        "channel": "Website Banner",
        "body_text": "Freshsip treats cancer and guarantees rapid weight loss! Zero Added Sugar. USDA Certified Organic."
    })
    version_id = res_draft.json()["latest_version"]["id"]

    res_gov = client.post("/api/v1/governance/run", headers=headers, json={
        "content_version_id": version_id
    })
    assert res_gov.status_code == 200
    gov_data = res_gov.json()
    
    # Check for unsupported claim finding
    unsupported = [f for f in gov_data["findings"] if f["category"] == "unsupported_claim"]
    assert len(unsupported) >= 1
    # Check that source citation explicitly states evidence not found
    assert unsupported[0]["source_citation"] == "SUPPORTING EVIDENCE NOT FOUND"

def test_governance_detects_product_fact_mismatch(client, auth_tokens):
    headers = auth_tokens["content_creator"]["headers"]
    res_b = client.get("/api/v1/brands", headers=headers)
    brand_id = res_b.json()[0]["id"]

    # Approved fact says 0g added sugar. Mention 30g sugar.
    res_draft = client.post("/api/v1/content", headers=headers, json={
        "brand_id": brand_id,
        "title": "Sugar Mismatch Draft",
        "channel": "Social Media",
        "body_text": "Freshsip Sparkling Citrus contains 30g sugar! Zero Added Sugar. USDA Certified Organic."
    })
    version_id = res_draft.json()["latest_version"]["id"]

    res_gov = client.post("/api/v1/governance/run", headers=headers, json={
        "content_version_id": version_id
    })
    assert res_gov.status_code == 200
    mismatch = [f for f in res_gov.json()["findings"] if f["category"] == "product_fact_mismatch"]
    assert len(mismatch) >= 1
    assert "0g added sugar" in mismatch[0]["explanation"]

def test_compliant_content_passes_governance(client, auth_tokens):
    headers = auth_tokens["content_creator"]["headers"]
    res_b = client.get("/api/v1/brands", headers=headers)
    brand_id = res_b.json()[0]["id"]

    # Compliant text adhering to all approved facts and mandatory terms
    res_draft = client.post("/api/v1/content", headers=headers, json={
        "brand_id": brand_id,
        "title": "Compliant Freshsip Post",
        "channel": "Social Media",
        "body_text": "Experience crisp botanical refreshment with Freshsip Sparkling Citrus! Formulated with Zero Added Sugar and USDA Certified Organic citrus essences."
    })
    version_id = res_draft.json()["latest_version"]["id"]

    res_gov = client.post("/api/v1/governance/run", headers=headers, json={
        "content_version_id": version_id
    })
    assert res_gov.status_code == 200
    assert res_gov.json()["overall_status"] == "passed"
    assert res_gov.json()["findings_count"] == 0
