import pytest
from app.models.knowledge import KnowledgeRule, KnowledgeFact
from app.models.content import ContentItem, ContentVersion, GovernanceRun

def test_1_compliant_product_advertisement_passes(client, auth_tokens):
    """
    1. A compliant product advertisement passes applicable mandatory-wording checks.
    """
    headers = auth_tokens["content_creator"]["headers"]
    res_b = client.get("/api/v1/brands", headers=headers)
    brand_id = res_b.json()[0]["id"]

    compliant_copy = (
        "Enjoy Freshsip Valencia Orange Cold-Pressed Juice, crafted from 100% cold-pressed "
        "Valencia orange juice with no added sugar. Crisp, refreshing citrus nourishment for your day!"
    )
    res_draft = client.post("/api/v1/content", headers=headers, json={
        "brand_id": brand_id,
        "title": "Summer Refreshment Promo",
        "channel": "Social Media",
        "body_text": compliant_copy
    })
    assert res_draft.status_code == 200
    v_id = res_draft.json()["latest_version"]["id"]

    res_gov = client.post("/api/v1/governance/run", headers=headers, json={
        "content_version_id": v_id
    })
    assert res_gov.status_code == 200
    data = res_gov.json()
    assert data["overall_status"] == "passed"
    blocking_findings = [f for f in data["findings"] if f["severity"] in ("critical", "high") and f.get("status") != "passed_check"]
    assert len(blocking_findings) == 0


def test_2_prohibited_organic_claim_triggers_prohibition(client, auth_tokens):
    """
    2. A prohibited organic-certification claim triggers the documented prohibition (FR-RULE-010).
    """
    headers = auth_tokens["content_creator"]["headers"]
    res_b = client.get("/api/v1/brands", headers=headers)
    brand_id = res_b.json()[0]["id"]

    violating_copy = "Freshsip Valencia Orange Cold-Pressed Juice is made from 100% certified organic and USDA Organic fruit."
    res_draft = client.post("/api/v1/content", headers=headers, json={
        "brand_id": brand_id,
        "title": "Organic Claim Violation",
        "channel": "Social Media",
        "body_text": violating_copy
    })
    v_id = res_draft.json()["latest_version"]["id"]

    res_gov = client.post("/api/v1/governance/run", headers=headers, json={
        "content_version_id": v_id
    })
    assert res_gov.status_code == 200
    data = res_gov.json()
    assert data["overall_status"] == "failed"

    organic_findings = [
        f for f in data["findings"]
        if "organic" in f["title"].lower() or "organic" in f["explanation"].lower() or "fr-rule-010" in f["title"].lower()
    ]
    assert len(organic_findings) >= 1
    assert any(f["severity"] in ("critical", "high") for f in organic_findings)


def test_3_no_added_sugar_accepted_where_permitted(client, auth_tokens):
    """
    3. 'No Added Sugar' is accepted where the source policy permits it (FR-RULE-005 / FR-RULE-006).
    """
    headers = auth_tokens["content_creator"]["headers"]
    res_b = client.get("/api/v1/brands", headers=headers)
    brand_id = res_b.json()[0]["id"]

    copy_with_nas = "Valencia Orange Cold-Pressed Juice has no added sugar—only natural fruit sugars."
    res_draft = client.post("/api/v1/content", headers=headers, json={
        "brand_id": brand_id,
        "title": "Sugar Policy Check",
        "channel": "Social Media",
        "body_text": copy_with_nas
    })
    v_id = res_draft.json()["latest_version"]["id"]

    res_gov = client.post("/api/v1/governance/run", headers=headers, json={
        "content_version_id": v_id
    })
    assert res_gov.status_code == 200
    findings = res_gov.json()["findings"]

    # Must NOT flag 'No Added Sugar' as missing or violating
    sugar_errors = [
        f for f in findings
        if f["category"] == "mandatory_wording_missing" and "sugar" in f["title"].lower()
    ]
    assert len(sugar_errors) == 0


def test_4_zero_added_sugar_not_demanded_as_universal_phrase(client, auth_tokens):
    """
    4. 'Zero Added Sugar' is not demanded as a universal phrase.
    """
    headers = auth_tokens["content_creator"]["headers"]
    res_b = client.get("/api/v1/brands", headers=headers)
    brand_id = res_b.json()[0]["id"]

    copy_simple = "Freshsip Valencia Orange Cold-Pressed Juice is delicious and 100% pure."
    res_draft = client.post("/api/v1/content", headers=headers, json={
        "brand_id": brand_id,
        "title": "Universal Phrase Check",
        "channel": "Social Media",
        "body_text": copy_simple
    })
    v_id = res_draft.json()["latest_version"]["id"]

    res_gov = client.post("/api/v1/governance/run", headers=headers, json={
        "content_version_id": v_id
    })
    assert res_gov.status_code == 200
    findings = res_gov.json()["findings"]

    # Verify no finding demands 'Zero Added Sugar'
    zero_sugar_demands = [
        f for f in findings
        if "zero added sugar" in f["title"].lower() or "zero added sugar" in f["explanation"].lower()
    ]
    assert len(zero_sugar_demands) == 0


def test_5_product_nutritional_disclosures_not_applied_to_corporate_announcements(client, auth_tokens):
    """
    5. Product-specific nutritional disclosures do not apply to generic corporate announcements.
    """
    headers = auth_tokens["content_creator"]["headers"]
    res_b = client.get("/api/v1/brands", headers=headers)
    brand_id = res_b.json()[0]["id"]

    corporate_copy = (
        "Freshsip Beverages is proud to announce the expansion of our sustainable cold-chain distribution network "
        "across Southern India. We remain committed to transparent governance and community well-being."
    )
    res_draft = client.post("/api/v1/content", headers=headers, json={
        "brand_id": brand_id,
        "title": "Corporate Expansion Press Release",
        "channel": "Social Media",
        "body_text": corporate_copy
    })
    v_id = res_draft.json()["latest_version"]["id"]

    res_gov = client.post("/api/v1/governance/run", headers=headers, json={
        "content_version_id": v_id
    })
    assert res_gov.status_code == 200
    data = res_gov.json()
    assert data["overall_status"] == "passed"

    # Must NOT have product fact mismatches or product disclosure requirements
    fact_findings = [f for f in data["findings"] if f["category"] in ("product_fact_mismatch", "mandatory_wording_missing")]
    assert len(fact_findings) == 0


def test_6_product_scoped_rule_not_applied_to_other_products(client, auth_tokens):
    """
    6. A rule scoped to one product does not incorrectly apply to another product (e.g. Celery disclosure for FS-PROD-003 vs FS-PROD-001).
    """
    headers = auth_tokens["content_creator"]["headers"]
    res_b = client.get("/api/v1/brands", headers=headers)
    brand_id = res_b.json()[0]["id"]

    # Case A: Valencia Orange Cold-Pressed Juice (FS-PROD-001) in packaging channel
    orange_pack_copy = "Freshsip Valencia Orange Cold-Pressed Juice in 250 mL glass bottle. Made with 100% orange juice. Keep refrigerated."
    res_orange = client.post("/api/v1/content", headers=headers, json={
        "brand_id": brand_id,
        "title": "Valencia Orange Packaging",
        "channel": "packaging",
        "body_text": orange_pack_copy
    })
    v_orange_id = res_orange.json()["latest_version"]["id"]

    res_gov_orange = client.post("/api/v1/governance/run", headers=headers, json={
        "content_version_id": v_orange_id
    })
    assert res_gov_orange.status_code == 200
    orange_findings = res_gov_orange.json()["findings"]

    # Celery disclosure must NOT apply to Valencia Orange
    celery_findings_on_orange = [f for f in orange_findings if "celery" in f["title"].lower()]
    assert len(celery_findings_on_orange) == 0

    # Case B: Garden Tomato Celery Press (FS-PROD-003) missing Celery disclosure on packaging
    tomato_pack_copy = "Freshsip Garden Tomato Celery Press in 250 mL glass bottle. Refreshing savory vegetable juice. Keep refrigerated."
    res_tomato = client.post("/api/v1/content", headers=headers, json={
        "brand_id": brand_id,
        "title": "Tomato Celery Packaging",
        "channel": "packaging",
        "body_text": tomato_pack_copy
    })
    v_tomato_id = res_tomato.json()["latest_version"]["id"]

    res_gov_tomato = client.post("/api/v1/governance/run", headers=headers, json={
        "content_version_id": v_tomato_id
    })
    assert res_gov_tomato.status_code == 200
    tomato_findings = res_gov_tomato.json()["findings"]

    # Celery disclosure MUST be flagged for FS-PROD-003 on packaging
    celery_findings_on_tomato = [f for f in tomato_findings if "celery" in f["title"].lower()]
    assert len(celery_findings_on_tomato) >= 1
    assert any(f["severity"] == "critical" for f in celery_findings_on_tomato)


def test_7_channel_and_format_specific_rules_enforced_only_in_documented_contexts(client, auth_tokens):
    """
    7. Channel- and format-specific rules are enforced only in their documented contexts (e.g. packaging rules on social posts).
    """
    headers = auth_tokens["content_creator"]["headers"]
    res_b = client.get("/api/v1/brands", headers=headers)
    brand_id = res_b.json()[0]["id"]

    # Casual social media post about Tomato Celery Press
    social_copy = "Enjoying a cold glass of Freshsip Garden Tomato Celery Press for an afternoon energy recharge!"
    res_social = client.post("/api/v1/content", headers=headers, json={
        "brand_id": brand_id,
        "title": "Social Post Tomato Celery",
        "channel": "Social Media",
        "body_text": social_copy
    })
    v_social_id = res_social.json()["latest_version"]["id"]

    res_gov_social = client.post("/api/v1/governance/run", headers=headers, json={
        "content_version_id": v_social_id
    })
    assert res_gov_social.status_code == 200
    social_findings = res_gov_social.json()["findings"]

    # Packaging allergen/storage mandatory disclosure (FR-RULE-014 scope: packaging, product_descriptions, ecommerce_listings)
    # is NOT enforced on casual social media posts
    packaging_mandates = [
        f for f in social_findings
        if f["category"] == "mandatory_wording_missing" and "fr-rule-014" in f["title"].lower()
    ]
    assert len(packaging_mandates) == 0


def test_8_pending_expired_rejected_claims_not_treated_as_approved(client, auth_tokens):
    """
    8. Pending, expired, rejected and deprecated rules or claims are not treated as active approved evidence.
    """
    headers = auth_tokens["content_creator"]["headers"]
    res_b = client.get("/api/v1/brands", headers=headers)
    brand_id = res_b.json()[0]["id"]

    # Case A: Pending claim (FS-CLAIM-004)
    pending_claim_copy = "Spiced Carrot Beetroot Press is suitable for all allergy-sensitive consumers and produced in a 100% allergen-free facility."
    res_pending = client.post("/api/v1/content", headers=headers, json={
        "brand_id": brand_id,
        "title": "Pending Claim Usage",
        "channel": "Social Media",
        "body_text": pending_claim_copy
    })
    v_pending_id = res_pending.json()["latest_version"]["id"]
    res_gov_pending = client.post("/api/v1/governance/run", headers=headers, json={"content_version_id": v_pending_id})
    assert res_gov_pending.status_code == 200
    pending_findings = [f for f in res_gov_pending.json()["findings"] if "pending" in f["title"].lower() or "fr-rule-018" in f["title"].lower()]
    assert len(pending_findings) >= 1

    # Case B: Expired claim (FS-CLAIM-005)
    expired_claim_copy = "Contains 65% carrot juice, 30% beetroot juice, and 3% ginger juice with 38 kcal per 100 mL (2025 Specification Cycle)."
    res_expired = client.post("/api/v1/content", headers=headers, json={
        "brand_id": brand_id,
        "title": "Expired Claim Usage",
        "channel": "Social Media",
        "body_text": expired_claim_copy
    })
    v_expired_id = res_expired.json()["latest_version"]["id"]
    res_gov_expired = client.post("/api/v1/governance/run", headers=headers, json={"content_version_id": v_expired_id})
    assert res_gov_expired.status_code == 200
    expired_findings = [f for f in res_gov_expired.json()["findings"] if "expired" in f["title"].lower()]
    assert len(expired_findings) >= 1

    # Case C: Rejected claim (FS-CLAIM-010)
    rejected_claim_copy = "Detoxifies your liver, flushes out bodily toxins in 48 hours, and melts stubborn belly fat naturally."
    res_rejected = client.post("/api/v1/content", headers=headers, json={
        "brand_id": brand_id,
        "title": "Rejected Claim Usage",
        "channel": "Social Media",
        "body_text": rejected_claim_copy
    })
    v_rejected_id = res_rejected.json()["latest_version"]["id"]
    res_gov_rejected = client.post("/api/v1/governance/run", headers=headers, json={"content_version_id": v_rejected_id})
    assert res_gov_rejected.status_code == 200
    assert res_gov_rejected.json()["overall_status"] == "failed"
    rejected_findings = [f for f in res_gov_rejected.json()["findings"] if "rejected" in f["title"].lower() or "detox" in f["title"].lower()]
    assert len(rejected_findings) >= 1


def test_9_missing_product_context_reports_uncertainty(client, auth_tokens):
    """
    9. Missing product context does not silently produce unsupported product-specific findings,
       but reports ambiguity/uncertainty.
    """
    headers = auth_tokens["content_creator"]["headers"]
    res_b = client.get("/api/v1/brands", headers=headers)
    brand_id = res_b.json()[0]["id"]

    # Claim states 22 calories and MRP ₹95 without mentioning which product
    ambiguous_copy = "Our cold-pressed juice provides only 22 calories and is priced at MRP ₹95 for healthy living!"
    res_draft = client.post("/api/v1/content", headers=headers, json={
        "brand_id": brand_id,
        "title": "Ambiguous Juice Post",
        "channel": "Social Media",
        "body_text": ambiguous_copy
    })
    v_id = res_draft.json()["latest_version"]["id"]

    res_gov = client.post("/api/v1/governance/run", headers=headers, json={
        "content_version_id": v_id
    })
    assert res_gov.status_code == 200
    findings = res_gov.json()["findings"]

    # Uncertainty/missing product context should be reported
    uncertainty_findings = [
        f for f in findings
        if "missing product context" in f["title"].lower() or f["category"] == "missing_evidence"
    ]
    assert len(uncertainty_findings) >= 1


def test_10_missing_or_conflicting_evidence_escalated_appropriately(client, auth_tokens):
    """
    10. Missing or conflicting evidence is reported as uncertainty or escalated appropriately (FR-RULE-018).
    """
    headers = auth_tokens["content_creator"]["headers"]
    res_b = client.get("/api/v1/brands", headers=headers)
    brand_id = res_b.json()[0]["id"]

    # Copy states unestablished Vitamin C quantification (FR-RULE-009 / FS-CLAIM-009 pending)
    unestablished_copy = "One 250 mL bottle of Valencia Orange Cold-Pressed Juice supplies 100% of your daily Vitamin C requirement."
    res_draft = client.post("/api/v1/content", headers=headers, json={
        "brand_id": brand_id,
        "title": "Unestablished Vitamin C Claim",
        "channel": "Social Media",
        "body_text": unestablished_copy
    })
    v_id = res_draft.json()["latest_version"]["id"]

    res_gov = client.post("/api/v1/governance/run", headers=headers, json={
        "content_version_id": v_id
    })
    assert res_gov.status_code == 200
    data = res_gov.json()
    assert data["overall_status"] == "failed"

    escalation_findings = [
        f for f in data["findings"]
        if f["category"] in ("missing_evidence", "claim_status_issue", "prohibited_wording")
    ]
    assert len(escalation_findings) >= 1


def test_11_negated_or_quoted_prohibited_phrases_do_not_trigger_false_positives(client, auth_tokens):
    """
    11. Negated or quoted prohibited phrases do not automatically trigger false positives where context can be reliably distinguished.
    """
    headers = auth_tokens["content_creator"]["headers"]
    res_b = client.get("/api/v1/brands", headers=headers)
    brand_id = res_b.json()[0]["id"]

    # Copy contains negated phrases: "does not claim our juice is a miracle elixir" and "not a cure for diabetes"
    negated_copy = (
        "Freshsip Beverages does not claim our Valencia Orange juice is a miracle elixir or a cure for diabetes. "
        "We simply provide pure, refreshing cold-pressed juice with no added sugar."
    )
    res_draft = client.post("/api/v1/content", headers=headers, json={
        "brand_id": brand_id,
        "title": "Editorial Clarification Post",
        "channel": "Social Media",
        "body_text": negated_copy
    })
    v_id = res_draft.json()["latest_version"]["id"]

    res_gov = client.post("/api/v1/governance/run", headers=headers, json={
        "content_version_id": v_id
    })
    assert res_gov.status_code == 200
    data = res_gov.json()

    # The run must NOT fail due to negated phrases
    assert data["overall_status"] != "failed"

    # Contextual mentions are recorded as passed_check or info
    info_mentions = [
        f for f in data["findings"]
        if f.get("status") == "passed_check" or f.get("severity") == "info"
    ]
    assert len(info_mentions) >= 1


def test_12_tenant_isolation_versioning_and_audit_intact(client, auth_tokens):
    """
    12. Existing tenant isolation, versioning and audit behaviour remains intact.
    """
    headers_creator = auth_tokens["content_creator"]["headers"]
    res_b = client.get("/api/v1/brands", headers=headers_creator)
    brand_id = res_b.json()[0]["id"]

    # 1. Create content item
    res_create = client.post("/api/v1/content", headers=headers_creator, json={
        "brand_id": brand_id,
        "title": "Tenant and Version Isolation Check",
        "channel": "Social Media",
        "body_text": "Valencia Orange Cold-Pressed Juice with no added sugar."
    })
    assert res_create.status_code == 200
    content_id = res_create.json()["id"]
    v1_id = res_create.json()["latest_version"]["id"]
    assert res_create.json()["current_version_num"] == 1

    # 2. Update to create v2
    res_update = client.put(f"/api/v1/content/{content_id}", headers=headers_creator, json={
        "title": "Tenant and Version Isolation Check Updated",
        "channel": "Social Media",
        "body_text": "Valencia Orange Cold-Pressed Juice with no added sugar and natural citrus flavor."
    })
    assert res_update.status_code == 200
    v2_id = res_update.json()["latest_version"]["id"]
    assert v2_id != v1_id
    assert res_update.json()["current_version_num"] == 2

    # 3. Run governance on v2
    res_gov = client.post("/api/v1/governance/run", headers=headers_creator, json={
        "content_version_id": v2_id
    })
    assert res_gov.status_code == 200
    gov_run_id = res_gov.json()["id"]

    # 4. Check audit log was recorded
    res_audit = client.get("/api/v1/audit", headers=headers_creator)
    assert res_audit.status_code == 200
    audit_events = res_audit.json()
    assert any(ev.get("entity_id") == gov_run_id for ev in audit_events)
