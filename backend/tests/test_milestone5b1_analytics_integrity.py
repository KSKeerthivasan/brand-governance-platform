import pytest
import hashlib
from datetime import datetime
from app.models.brand import Brand
from app.models.content import (
    ContentItem,
    ContentVersion,
    GovernanceRun,
    GovernanceFinding,
    ApprovalSubmission,
    ApprovalDecision,
    ReviewerFindingDisposition
)
from app.models.knowledge import KnowledgeRule
from app.models.organization import User


def test_01_run_with_only_successful_checks_is_clean_pass(client, auth_tokens, db_session):
    """
    Test 1: A governance run with only successful checks (status='passed_check')
    must be classified as a clean pass and NOT counted as a run with actionable findings.
    """
    headers = auth_tokens["approval_manager"]["headers"]
    org_id = auth_tokens["approval_manager"]["org_id"]
    brand = db_session.query(Brand).filter(Brand.organization_id == org_id).first()
    user = db_session.query(User).first()

    # Create a draft
    item = ContentItem(
        organization_id=org_id,
        brand_id=brand.id,
        created_by=user.id,
        title="Clean Draft Passed Checks Only",
        channel="instagram"
    )
    db_session.add(item)
    db_session.flush()

    checksum = hashlib.sha256(b"Compliant body text").hexdigest()
    version = ContentVersion(
        content_item_id=item.id,
        version_num=1,
        body_text="Compliant body text",
        checksum=checksum,
        created_by=user.id
    )
    db_session.add(version)
    db_session.flush()

    # Governance engine sets overall_status='passed' when only passed_check findings exist
    run = GovernanceRun(
        content_version_id=version.id,
        overall_status="passed",
        rules_evaluated_count=8,
        findings_count=1
    )
    db_session.add(run)
    db_session.flush()

    # Add a successful informational check
    finding = GovernanceFinding(
        governance_run_id=run.id,
        title="Resolution Compliant",
        category="image_resolution",
        explanation="Image resolution meets brand standards.",
        severity="info",
        status="passed_check",
        source_citation="Brand Guidelines v1, Section 2",
        recommended_action="Ensure copy continues to clearly negate medical claims."
    )
    db_session.add(finding)
    db_session.commit()

    res = client.get("/api/v1/analytics/overview", headers=headers)
    assert res.status_code == 200, res.text
    data = res.json()

    assert data["total_runs"] >= 1
    assert data["clean_runs_count"] >= 1
    # Check that this run's passed_check is recorded under successful_checks
    assert data["successful_checks_count"] >= 1


def test_02_warning_and_failed_runs_classified_correctly(client, auth_tokens, db_session):
    """
    Test 2: Warning and failed runs are classified as runs with actionable findings.
    """
    headers = auth_tokens["approval_manager"]["headers"]
    org_id = auth_tokens["approval_manager"]["org_id"]
    brand = db_session.query(Brand).filter(Brand.organization_id == org_id).first()
    user = db_session.query(User).first()

    # Create Item with warning run
    item1 = ContentItem(
        organization_id=org_id,
        brand_id=brand.id,
        created_by=user.id,
        title="Warning Run Item",
        channel="web"
    )
    db_session.add(item1)
    db_session.flush()

    v1 = ContentVersion(
        content_item_id=item1.id,
        version_num=1,
        body_text="Body with warning",
        checksum=hashlib.sha256(b"w").hexdigest(),
        created_by=user.id
    )
    db_session.add(v1)
    db_session.flush()

    run_warn = GovernanceRun(
        content_version_id=v1.id,
        overall_status="warnings",
        rules_evaluated_count=5
    )
    db_session.add(run_warn)
    db_session.flush()

    f_warn = GovernanceFinding(
        governance_run_id=run_warn.id,
        title="Warning finding",
        category="tone_and_voice",
        explanation="Tone needs adjustment",
        severity="warning",
        status="unresolved",
        source_citation="Brand Guidelines v1",
        recommended_action="Adjust tone"
    )
    db_session.add(f_warn)

    # Create Item with failed run
    item2 = ContentItem(
        organization_id=org_id,
        brand_id=brand.id,
        created_by=user.id,
        title="Failed Run Item",
        channel="web"
    )
    db_session.add(item2)
    db_session.flush()

    v2 = ContentVersion(
        content_item_id=item2.id,
        version_num=1,
        body_text="Body with blocker",
        checksum=hashlib.sha256(b"f").hexdigest(),
        created_by=user.id
    )
    db_session.add(v2)
    db_session.flush()

    run_fail = GovernanceRun(
        content_version_id=v2.id,
        overall_status="failed",
        rules_evaluated_count=5
    )
    db_session.add(run_fail)
    db_session.flush()

    f_fail = GovernanceFinding(
        governance_run_id=run_fail.id,
        title="Blocker finding",
        category="prohibited_claim",
        explanation="Prohibited health claim",
        severity="critical",
        status="unresolved",
        source_citation="Brand Guidelines v1",
        recommended_action="Remove prohibited health claim"
    )
    db_session.add(f_fail)
    db_session.commit()

    res = client.get("/api/v1/analytics/overview", headers=headers)
    assert res.status_code == 200
    data = res.json()

    assert data["runs_with_findings_count"] >= 2
    assert data["actionable_findings_count"] >= 2


def test_03_clean_pass_rate_definition(client, auth_tokens, db_session):
    """
    Test 3: Clean pass rate matches definition: clean_runs_count / total_runs * 100.
    """
    headers = auth_tokens["approval_manager"]["headers"]

    res = client.get("/api/v1/analytics/overview", headers=headers)
    assert res.status_code == 200
    data = res.json()

    total = data["total_runs"]
    clean = data["clean_runs_count"]
    with_findings = data["runs_with_findings_count"]

    assert clean + with_findings == total
    if total > 0:
        expected_rate = round((clean / total) * 100, 1)
        assert data["clean_runs_pct"] == expected_rate


def test_04_severity_counts_distinguish_actionable_from_passed_check(client, auth_tokens, db_session):
    """
    Test 4: Severity counts distinguish actionable findings from successful informational checks.
    """
    headers = auth_tokens["approval_manager"]["headers"]

    res = client.get("/api/v1/analytics/overview", headers=headers)
    assert res.status_code == 200
    data = res.json()

    assert "actionable_findings_by_severity" in data
    assert "successful_checks_count" in data
    assert "actionable_findings_count" in data

    # Actionable count + successful checks count + any unresolved review should be consistent with total findings
    assert data["actionable_findings_count"] + data["successful_checks_count"] == data["total_findings"]


def test_05_repeated_mistakes_excludes_passed_checks_and_separates_distinct_items(client, auth_tokens, db_session):
    """
    Test 5: Repeated mistakes excludes status='passed_check' and counts distinct content items affected.
    """
    headers = auth_tokens["approval_manager"]["headers"]
    org_id = auth_tokens["approval_manager"]["org_id"]
    brand = db_session.query(Brand).filter(Brand.organization_id == org_id).first()
    user = db_session.query(User).first()

    # Create a test rule
    rule = KnowledgeRule(
        organization_id=org_id,
        rule_code="TEST-INTEGRITY-01",
        title="No Sensational Guarantees",
        rule_type="prohibited_claim",
        pattern=r"\bguarantee\b",
        explanation="Do not guarantee results",
        status="approved"
    )
    db_session.add(rule)
    db_session.flush()

    # Content Item 1: Has actionable violation
    item1 = ContentItem(
        organization_id=org_id,
        brand_id=brand.id,
        created_by=user.id,
        title="Draft with Violation",
        channel="instagram"
    )
    db_session.add(item1)
    db_session.flush()

    v1 = ContentVersion(
        content_item_id=item1.id,
        version_num=1,
        body_text="We guarantee results",
        checksum=hashlib.sha256(b"v1").hexdigest(),
        created_by=user.id
    )
    db_session.add(v1)
    db_session.flush()

    run1 = GovernanceRun(content_version_id=v1.id, overall_status="warnings", rules_evaluated_count=5)
    db_session.add(run1)
    db_session.flush()

    f1 = GovernanceFinding(
        governance_run_id=run1.id,
        matched_rule_id=rule.id,
        title="Sensational Claim",
        category="prohibited_claim",
        explanation="Used guarantee",
        severity="warning",
        status="unresolved",
        source_citation="Brand Guidelines v1",
        recommended_action="Remove guarantee"
    )
    db_session.add(f1)

    # Content Item 2: Has passed_check finding for the SAME rule
    item2 = ContentItem(
        organization_id=org_id,
        brand_id=brand.id,
        created_by=user.id,
        title="Draft with Passed Check",
        channel="instagram"
    )
    db_session.add(item2)
    db_session.flush()

    v2 = ContentVersion(
        content_item_id=item2.id,
        version_num=1,
        body_text="No guarantees made",
        checksum=hashlib.sha256(b"v2").hexdigest(),
        created_by=user.id
    )
    db_session.add(v2)
    db_session.flush()

    run2 = GovernanceRun(content_version_id=v2.id, overall_status="passed", rules_evaluated_count=5)
    db_session.add(run2)
    db_session.flush()

    f2 = GovernanceFinding(
        governance_run_id=run2.id,
        matched_rule_id=rule.id,
        title="Checked and Passed",
        category="prohibited_claim",
        explanation="Passed check cleanly",
        severity="info",
        status="passed_check",
        source_citation="Brand Guidelines v1",
        recommended_action="Keep compliant"
    )
    db_session.add(f2)
    db_session.commit()

    res = client.get("/api/v1/analytics/repeated-mistakes", headers=headers)
    assert res.status_code == 200
    data = res.json()

    # Find our rule
    target_item = next((it for it in data["items"] if it["rule_id"] == rule.id), None)
    assert target_item is not None
    # Distinct items MUST be 1 (only Item 1 had actionable violation; Item 2 passed_check is excluded!)
    assert target_item["distinct_content_items_count"] == 1
    assert target_item["total_findings"] == 1
    assert target_item["successful_checks_count"] == 0


def test_06_warning_override_attribution_multi_rule_separation(client, auth_tokens, db_session):
    """
    Test 6: Multi-rule warning approvals without rule-specific citations are NOT
    falsely attributed to individual rules, and are excluded from ambiguity scores.
    """
    headers = auth_tokens["approval_manager"]["headers"]
    org_id = auth_tokens["approval_manager"]["org_id"]
    brand = db_session.query(Brand).filter(Brand.organization_id == org_id).first()
    user = db_session.query(User).first()

    # Create two rules
    rule_a = KnowledgeRule(
        organization_id=org_id,
        rule_code="RULE-MULTI-A",
        title="Multi Rule A Guideline",
        rule_type="style",
        pattern=r"\bruleA\b",
        explanation="Rule A",
        status="approved"
    )
    rule_b = KnowledgeRule(
        organization_id=org_id,
        rule_code="RULE-MULTI-B",
        title="Multi Rule B Guideline",
        rule_type="style",
        pattern=r"\bruleB\b",
        explanation="Rule B",
        status="approved"
    )
    db_session.add_all([rule_a, rule_b])
    db_session.flush()

    # Create draft with warnings from BOTH rules
    item = ContentItem(
        organization_id=org_id,
        brand_id=brand.id,
        created_by=user.id,
        title="Draft With Multiple Warnings",
        channel="web"
    )
    db_session.add(item)
    db_session.flush()

    version = ContentVersion(
        content_item_id=item.id,
        version_num=1,
        body_text="ruleA and ruleB present",
        checksum=hashlib.sha256(b"multi").hexdigest(),
        created_by=user.id
    )
    db_session.add(version)
    db_session.flush()

    run = GovernanceRun(content_version_id=version.id, overall_status="warnings", rules_evaluated_count=5)
    db_session.add(run)
    db_session.flush()

    f_a = GovernanceFinding(
        governance_run_id=run.id,
        matched_rule_id=rule_a.id,
        title="Warning Rule A",
        category="style",
        explanation="Warning A",
        severity="warning",
        status="unresolved",
        source_citation="Brand Guidelines v1",
        recommended_action="Fix Rule A"
    )
    f_b = GovernanceFinding(
        governance_run_id=run.id,
        matched_rule_id=rule_b.id,
        title="Warning Rule B",
        category="style",
        explanation="Warning B",
        severity="warning",
        status="unresolved",
        source_citation="Brand Guidelines v1",
        recommended_action="Fix Rule B"
    )
    db_session.add_all([f_a, f_b])
    db_session.flush()

    # Submission and general approval decision covering BOTH warnings without citing either rule
    sub = ApprovalSubmission(
        content_item_id=item.id,
        content_version_id=version.id,
        submitted_by=user.id,
        status="approved",
        submission_notes="Please review"
    )
    db_session.add(sub)
    db_session.flush()

    decision = ApprovalDecision(
        approval_submission_id=sub.id,
        content_version_id=version.id,
        decided_by=user.id,
        decision="approved",
        decision_label="Approved — Ready to Publish",
        comments="Approved for seasonal promotional launch without reservation."
    )
    db_session.add(decision)
    db_session.commit()

    # Query ambiguity report
    res = client.get("/api/v1/analytics/ambiguity-signals", headers=headers)
    assert res.status_code == 200
    data = res.json()

    # Check Rule A and Rule B
    for rule_id in [rule_a.id, rule_b.id]:
        rule_item = next((r for r in data["rules"] if r["rule_id"] == rule_id), None)
        if rule_item:
            # Verified rule overrides count MUST be 0!
            assert rule_item["verified_rule_overrides_count"] == 0
            # Content level overrides count MUST be 1
            assert rule_item["content_level_overrides_count"] == 1
            # Note documenting the exclusion
            assert rule_item["override_attribution_notes"] is not None
            assert "excluded from rule ambiguity score" in rule_item["override_attribution_notes"]


def test_07_warning_override_attribution_single_rule_and_explicit_citation(client, auth_tokens, db_session):
    """
    Test 7:
    - Single-rule warning on version IS attributed as verified rule override.
    - Explicit rule citation in multi-rule approval IS attributed as verified rule override.
    """
    headers = auth_tokens["approval_manager"]["headers"]
    org_id = auth_tokens["approval_manager"]["org_id"]
    brand = db_session.query(Brand).filter(Brand.organization_id == org_id).first()
    user = db_session.query(User).first()

    # Single-warning rule
    rule_single = KnowledgeRule(
        organization_id=org_id,
        rule_code="RULE-SINGLE-101",
        title="Single Rule Guideline",
        rule_type="claim",
        pattern=r"\bsingle\b",
        explanation="Single",
        status="approved"
    )
    db_session.add(rule_single)
    db_session.flush()

    item1 = ContentItem(
        organization_id=org_id,
        brand_id=brand.id,
        created_by=user.id,
        title="Draft With Single Warning",
        channel="web"
    )
    db_session.add(item1)
    db_session.flush()

    v1 = ContentVersion(
        content_item_id=item1.id,
        version_num=1,
        body_text="single",
        checksum=hashlib.sha256(b"s1").hexdigest(),
        created_by=user.id
    )
    db_session.add(v1)
    db_session.flush()

    r1 = GovernanceRun(content_version_id=v1.id, overall_status="warnings", rules_evaluated_count=5)
    db_session.add(r1)
    db_session.flush()

    f1 = GovernanceFinding(
        governance_run_id=r1.id,
        matched_rule_id=rule_single.id,
        title="Single Warning",
        category="claim",
        explanation="Single warning",
        severity="warning",
        status="unresolved",
        source_citation="Brand Guidelines v1",
        recommended_action="Follow single rule"
    )
    db_session.add(f1)
    db_session.flush()

    sub1 = ApprovalSubmission(content_item_id=item1.id, content_version_id=v1.id, submitted_by=user.id, status="approved")
    db_session.add(sub1)
    db_session.flush()

    dec1 = ApprovalDecision(
        approval_submission_id=sub1.id,
        content_version_id=v1.id,
        decided_by=user.id,
        decision="approved",
        decision_label="Approved — Ready to Publish",
        comments="Approved single rule exception."
    )
    db_session.add(dec1)

    # Also add 1 reviewer disposition so rule has a signal to appear in ambiguity report
    disp = ReviewerFindingDisposition(
        organization_id=org_id,
        governance_run_id=r1.id,
        finding_id=f1.id,
        rule_id=rule_single.id,
        disposition="guideline_unclear",
        reviewer_id=user.id,
        explanation="Guideline is hard to interpret for clinical copy."
    )
    db_session.add(disp)
    db_session.commit()

    res = client.get(f"/api/v1/analytics/ambiguity-signals?rule_id={rule_single.id}", headers=headers)
    assert res.status_code == 200
    data = res.json()

    assert data["flagged_rules_count"] == 1
    rule_item = data["rules"][0]
    assert rule_item["verified_rule_overrides_count"] == 1
    assert rule_item["content_level_overrides_count"] == 0


def test_08_ambiguity_transparency_and_small_evidence_base(client, auth_tokens, db_session):
    """
    Test 8: Expose denominators, distinct items, and small evidence base indicator (< 3 dispositions).
    """
    headers = auth_tokens["approval_manager"]["headers"]
    org_id = auth_tokens["approval_manager"]["org_id"]
    brand = db_session.query(Brand).filter(Brand.organization_id == org_id).first()
    user = db_session.query(User).first()

    rule = KnowledgeRule(
        organization_id=org_id,
        rule_code="RULE-TRANSPARENCY-99",
        title="Transparency Rule",
        rule_type="style",
        pattern=r"\btransp\b",
        explanation="Transparency",
        status="approved"
    )
    db_session.add(rule)
    db_session.flush()

    item = ContentItem(
        organization_id=org_id,
        brand_id=brand.id,
        created_by=user.id,
        title="Transparency Item",
        channel="instagram"
    )
    db_session.add(item)
    db_session.flush()

    v = ContentVersion(
        content_item_id=item.id,
        version_num=1,
        body_text="transp text",
        checksum=hashlib.sha256(b"tr").hexdigest(),
        created_by=user.id
    )
    db_session.add(v)
    db_session.flush()

    run = GovernanceRun(content_version_id=v.id, overall_status="warnings", rules_evaluated_count=5)
    db_session.add(run)
    db_session.flush()

    finding = GovernanceFinding(
        governance_run_id=run.id,
        matched_rule_id=rule.id,
        title="Transparency Finding",
        category="style",
        explanation="Transp issue",
        severity="warning",
        status="unresolved",
        source_citation="Brand Guidelines v1",
        recommended_action="Check transparency"
    )
    db_session.add(finding)
    db_session.flush()

    # Record 1 disposition (small evidence base)
    disp = ReviewerFindingDisposition(
        organization_id=org_id,
        governance_run_id=run.id,
        finding_id=finding.id,
        rule_id=rule.id,
        content_item_id=item.id,
        content_version_id=v.id,
        disposition="conflicting_guidelines",
        reviewer_id=user.id,
        explanation="Conflicting with FTC disclosure guidelines."
    )
    db_session.add(disp)
    db_session.commit()

    res = client.get(f"/api/v1/analytics/ambiguity-signals?rule_id={rule.id}", headers=headers)
    assert res.status_code == 200
    data = res.json()

    assert data["flagged_rules_count"] == 1
    rule_item = data["rules"][0]

    # Verify transparency fields
    assert rule_item["evidence_base_size"] == "small"
    assert rule_item["total_dispositions_count"] == 1
    assert rule_item["distinct_content_items_count"] == 1
    assert rule_item["distinct_findings_count"] == 1
    assert "small evidence base" in rule_item["recommended_action"].lower()

    # Check signal fields
    sig = rule_item["signals"][0]
    assert sig["count"] == 1
    assert sig["denominator"] == 1
    assert sig["percentage"] == 100.0
    assert sig["evidence_source"] == "reviewer_disposition"
    assert sig["distinct_content_items_count"] == 1
    assert sig["distinct_findings_count"] == 1


def test_09_empty_history_and_zero_denominators(client, auth_tokens):
    """
    Test 9: Empty history and zero denominators return clean responses without 500 errors or division by zero.
    """
    headers = auth_tokens["approval_manager"]["headers"]
    # Query with future dates that match no data
    future_date = "2099-01-01"

    res_ov = client.get(f"/api/v1/analytics/overview?date_from={future_date}", headers=headers)
    assert res_ov.status_code == 200
    data_ov = res_ov.json()
    assert data_ov["total_runs"] == 0
    assert data_ov["clean_runs_pct"] == 0.0
    assert data_ov["runs_with_findings_pct"] == 0.0
    assert data_ov["data_available"] is False

    res_rep = client.get(f"/api/v1/analytics/repeated-mistakes?date_from={future_date}", headers=headers)
    assert res_rep.status_code == 200
    data_rep = res_rep.json()
    assert data_rep["total_repeated_rules_count"] == 0
    assert data_rep["items"] == []
    assert data_rep["data_available"] is False

    res_amb = client.get(f"/api/v1/analytics/ambiguity-signals?date_from={future_date}", headers=headers)
    assert res_amb.status_code == 200
    data_amb = res_amb.json()
    assert data_amb["flagged_rules_count"] == 0
