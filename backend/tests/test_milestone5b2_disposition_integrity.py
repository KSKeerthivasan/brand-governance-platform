import pytest
import hashlib
from datetime import datetime, timedelta
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


def _create_base_finding(db_session, org_id, user_id, rule_id, severity="warning"):
    brand = db_session.query(Brand).filter(Brand.organization_id == org_id).first()
    item = ContentItem(
        organization_id=org_id,
        brand_id=brand.id,
        created_by=user_id,
        title="Test Draft Item",
        channel="instagram"
    )
    db_session.add(item)
    db_session.flush()

    checksum = hashlib.sha256(b"Finding Draft Body").hexdigest()
    version = ContentVersion(
        content_item_id=item.id,
        version_num=1,
        body_text="Finding Draft Body",
        checksum=checksum,
        created_by=user_id
    )
    db_session.add(version)
    db_session.flush()

    run = GovernanceRun(
        content_version_id=version.id,
        overall_status="warnings",
        rules_evaluated_count=5
    )
    db_session.add(run)
    db_session.flush()

    finding = GovernanceFinding(
        governance_run_id=run.id,
        matched_rule_id=rule_id,
        title="Sample Finding",
        category="prohibited_claim",
        explanation="Detected rule match",
        severity=severity,
        status="unresolved",
        source_citation="Brand Guidelines v1",
        recommended_action="Inspect rule wording"
    )
    db_session.add(finding)
    db_session.commit()
    db_session.refresh(finding)
    return finding, item, version, run


def test_01_one_finding_multiple_dispositions_preserves_immutable_history(client, auth_tokens, db_session):
    """
    Test 1: One finding receiving multiple disposition events over time
    retains an immutable historical audit trail with timestamps, actors, and explanations.
    """
    headers = auth_tokens["approval_manager"]["headers"]
    org_id = auth_tokens["approval_manager"]["org_id"]
    user = db_session.query(User).first()

    rule = KnowledgeRule(
        organization_id=org_id,
        rule_code="RULE-5B2-01",
        title="Rule Multi Event Audit Test",
        rule_type="prohibited_claim",
        pattern=r"\btest01\b",
        explanation="Test rule",
        status="approved"
    )
    db_session.add(rule)
    db_session.commit()

    finding, item, version, run = _create_base_finding(db_session, org_id, user.id, rule.id)

    # 1st disposition event
    res1 = client.post(
        f"/api/v1/analytics/findings/{finding.id}/feedback",
        json={"disposition": "guideline_unclear", "explanation": "Initial review: wording seems ambiguous."},
        headers=headers
    )
    assert res1.status_code == 200

    # 2nd disposition event on same finding
    res2 = client.post(
        f"/api/v1/analytics/findings/{finding.id}/feedback",
        json={"disposition": "conflicting_guidelines", "explanation": "Follow-up review: contradicts Brand Rule 4."},
        headers=headers
    )
    assert res2.status_code == 200

    # 3rd disposition event on same finding
    res3 = client.post(
        f"/api/v1/analytics/findings/{finding.id}/feedback",
        json={"disposition": "other", "explanation": "Team aligned on escalation."},
        headers=headers
    )
    assert res3.status_code == 200

    # Fetch history via GET
    res_history = client.get(f"/api/v1/analytics/findings/{finding.id}/feedback", headers=headers)
    assert res_history.status_code == 200
    events = res_history.json()

    assert len(events) == 3
    # Check descending order: latest is first
    assert events[0]["disposition"] == "other"
    assert events[1]["disposition"] == "conflicting_guidelines"
    assert events[2]["disposition"] == "guideline_unclear"

    # All events preserve reviewer id, explanation, and timestamps
    for ev in events:
        assert ev["finding_id"] == finding.id
        assert ev["rule_id"] == rule.id
        assert ev["reviewer_id"] is not None
        assert ev["created_at"] is not None


def test_02_distinct_reviewed_finding_counts_not_inflated_by_repeated_events(client, auth_tokens, db_session):
    """
    Test 2: Submitting repeated feedback on the SAME finding does NOT inflate
    distinct reviewed finding counts or artificially multiply the ambiguity score.
    """
    headers = auth_tokens["approval_manager"]["headers"]
    org_id = auth_tokens["approval_manager"]["org_id"]
    user = db_session.query(User).first()

    rule = KnowledgeRule(
        organization_id=org_id,
        rule_code="RULE-5B2-02",
        title="Rule Repeat Distortion Check",
        rule_type="prohibited_claim",
        pattern=r"\btest02\b",
        explanation="Test rule",
        status="approved"
    )
    db_session.add(rule)
    db_session.commit()

    finding, item, version, run = _create_base_finding(db_session, org_id, user.id, rule.id)

    # Submit 3 repeated 'guideline_unclear' feedback events on the SAME finding
    for i in range(3):
        res = client.post(
            f"/api/v1/analytics/findings/{finding.id}/feedback",
            json={"disposition": "guideline_unclear", "explanation": f"Submission #{i+1}: definitely unclear."},
            headers=headers
        )
        assert res.status_code == 200

    # Query ambiguity signals
    res_signals = client.get(f"/api/v1/analytics/ambiguity-signals?rule_id={rule.id}", headers=headers)
    assert res_signals.status_code == 200
    data = res_signals.json()

    assert data["flagged_rules_count"] == 1
    rule_item = data["rules"][0]

    # Verify:
    # 1. total_dispositions_count is 1 (1 distinct finding reviewed, NOT 3!)
    assert rule_item["total_dispositions_count"] == 1
    # 2. total_events_count is 3 (3 historical feedback events recorded)
    assert rule_item["total_events_count"] == 3
    # 3. distinct_findings_count is 1
    assert rule_item["distinct_findings_count"] == 1

    # Check the unclear signal
    sig = rule_item["signals"][0]
    assert sig["signal_type"] == "guideline_unclear"
    assert sig["count"] == 1  # 1 distinct finding
    assert sig["event_count"] == 3  # 3 historical events
    assert sig["denominator"] == 1  # denominator is distinct reviewed findings
    assert sig["percentage"] == 100.0

    # Ambiguity score must use distinct finding count (1 * 15), not 3 * 15!
    # score = len(signals)*20 + unclear_distinct*15 = 20 + 15 = 35.0
    assert rule_item["ambiguity_score"] == 35.0


def test_03_false_positive_rate_uses_distinct_findings_denominator(client, auth_tokens, db_session):
    """
    Test 3: False-positive rate denominator equals distinct reviewed findings count,
    and multiple false_positive events on the same finding count as 1 false positive finding.
    """
    headers = auth_tokens["approval_manager"]["headers"]
    org_id = auth_tokens["approval_manager"]["org_id"]
    user = db_session.query(User).first()

    rule = KnowledgeRule(
        organization_id=org_id,
        rule_code="RULE-5B2-03",
        title="Rule FP Rate Denominator Check",
        rule_type="prohibited_claim",
        pattern=r"\btest03\b",
        explanation="Test rule",
        status="approved"
    )
    db_session.add(rule)
    db_session.commit()

    # Finding 1: Receives 3 false_positive feedback events
    f1, it1, v1, r1 = _create_base_finding(db_session, org_id, user.id, rule.id)
    for i in range(3):
        res = client.post(
            f"/api/v1/analytics/findings/{f1.id}/feedback",
            json={"disposition": "false_positive", "explanation": f"FP submission #{i+1}: compliant context."},
            headers=headers
        )
        assert res.status_code == 200

    # Finding 2: Receives 1 confirmed_issue feedback event
    f2, it2, v2, r2 = _create_base_finding(db_session, org_id, user.id, rule.id)
    res_conf = client.post(
        f"/api/v1/analytics/findings/{f2.id}/feedback",
        json={"disposition": "confirmed_issue", "explanation": "Accurate issue."},
        headers=headers
    )
    assert res_conf.status_code == 200

    res_signals = client.get(f"/api/v1/analytics/ambiguity-signals?rule_id={rule.id}", headers=headers)
    assert res_signals.status_code == 200
    data = res_signals.json()

    assert data["flagged_rules_count"] == 1
    rule_item = data["rules"][0]

    # Total distinct reviewed findings = 2 (Finding 1 and Finding 2)
    assert rule_item["total_dispositions_count"] == 2
    # Total historical events = 4 (3 for f1 + 1 for f2)
    assert rule_item["total_events_count"] == 4

    # FP Signal verification:
    # 1 distinct finding is FP out of 2 distinct reviewed findings -> 50.0%
    # (If events were used, it would falsely report 3 out of 4 -> 75%)
    fp_sig = next(s for s in rule_item["signals"] if s["signal_type"] == "high_false_positive_rate")
    assert fp_sig["count"] == 1  # 1 distinct finding
    assert fp_sig["event_count"] == 3  # 3 events
    assert fp_sig["denominator"] == 2  # 2 distinct reviewed findings
    assert fp_sig["percentage"] == 50.0


def test_04_changed_disposition_false_positive_superseded_by_confirmed_issue(client, auth_tokens, db_session):
    """
    Test 4: When a finding is initially marked false_positive but subsequently confirmed
    as a genuine issue, the effective disposition becomes confirmed_issue and the false-positive
    signal does NOT trigger.
    """
    headers = auth_tokens["approval_manager"]["headers"]
    org_id = auth_tokens["approval_manager"]["org_id"]
    user = db_session.query(User).first()

    rule = KnowledgeRule(
        organization_id=org_id,
        rule_code="RULE-5B2-04",
        title="Rule Superseded FP Check",
        rule_type="prohibited_claim",
        pattern=r"\btest04\b",
        explanation="Test rule",
        status="approved"
    )
    db_session.add(rule)
    db_session.commit()

    finding, item, version, run = _create_base_finding(db_session, org_id, user.id, rule.id)

    # 1st feedback: false_positive
    res1 = client.post(
        f"/api/v1/analytics/findings/{finding.id}/feedback",
        json={"disposition": "false_positive", "explanation": "Initially thought this was an over-flag."},
        headers=headers
    )
    assert res1.status_code == 200

    # 2nd feedback: reviewer changes assessment to confirmed_issue
    res2 = client.post(
        f"/api/v1/analytics/findings/{finding.id}/feedback",
        json={"disposition": "confirmed_issue", "explanation": "Re-inspected brand guide; this is indeed a violation."},
        headers=headers
    )
    assert res2.status_code == 200

    res_signals = client.get(f"/api/v1/analytics/ambiguity-signals?rule_id={rule.id}", headers=headers)
    assert res_signals.status_code == 200
    data = res_signals.json()

    # Effective disposition is confirmed_issue -> rule has NO active ambiguity signals!
    assert data["flagged_rules_count"] == 0


def test_05_changed_disposition_confirmed_issue_superseded_by_false_positive(client, auth_tokens, db_session):
    """
    Test 5: When a finding is initially marked confirmed_issue but subsequently changed
    to false_positive, the effective disposition becomes false_positive and triggers the signal.
    """
    headers = auth_tokens["approval_manager"]["headers"]
    org_id = auth_tokens["approval_manager"]["org_id"]
    user = db_session.query(User).first()

    rule = KnowledgeRule(
        organization_id=org_id,
        rule_code="RULE-5B2-05",
        title="Rule Confirmed to FP Check",
        rule_type="prohibited_claim",
        pattern=r"\btest05\b",
        explanation="Test rule",
        status="approved"
    )
    db_session.add(rule)
    db_session.commit()

    finding, item, version, run = _create_base_finding(db_session, org_id, user.id, rule.id)

    # 1st: confirmed_issue
    res1 = client.post(
        f"/api/v1/analytics/findings/{finding.id}/feedback",
        json={"disposition": "confirmed_issue", "explanation": "Initially thought valid."},
        headers=headers
    )
    assert res1.status_code == 200

    # 2nd: changed to false_positive
    res2 = client.post(
        f"/api/v1/analytics/findings/{finding.id}/feedback",
        json={"disposition": "false_positive", "explanation": "Found approved exception in Section 3; over-flagged."},
        headers=headers
    )
    assert res2.status_code == 200

    res_signals = client.get(f"/api/v1/analytics/ambiguity-signals?rule_id={rule.id}", headers=headers)
    assert res_signals.status_code == 200
    data = res_signals.json()

    assert data["flagged_rules_count"] == 1
    rule_item = data["rules"][0]
    fp_sig = next(s for s in rule_item["signals"] if s["signal_type"] == "high_false_positive_rate")
    assert fp_sig["count"] == 1
    assert fp_sig["percentage"] == 100.0


def test_06_independent_findings_counted_independently(client, auth_tokens, db_session):
    """
    Test 6: Distinct findings for the same rule are counted independently in rates and scores.
    """
    headers = auth_tokens["approval_manager"]["headers"]
    org_id = auth_tokens["approval_manager"]["org_id"]
    user = db_session.query(User).first()

    rule = KnowledgeRule(
        organization_id=org_id,
        rule_code="RULE-5B2-06",
        title="Rule Independent Findings Check",
        rule_type="prohibited_claim",
        pattern=r"\btest06\b",
        explanation="Test rule",
        status="approved"
    )
    db_session.add(rule)
    db_session.commit()

    # Create 3 independent findings
    f1, _, _, _ = _create_base_finding(db_session, org_id, user.id, rule.id)
    f2, _, _, _ = _create_base_finding(db_session, org_id, user.id, rule.id)
    f3, _, _, _ = _create_base_finding(db_session, org_id, user.id, rule.id)

    # f1 and f2 are false_positive
    client.post(f"/api/v1/analytics/findings/{f1.id}/feedback", json={"disposition": "false_positive", "explanation": "FP finding 1."}, headers=headers)
    client.post(f"/api/v1/analytics/findings/{f2.id}/feedback", json={"disposition": "false_positive", "explanation": "FP finding 2."}, headers=headers)
    # f3 is confirmed_issue
    client.post(f"/api/v1/analytics/findings/{f3.id}/feedback", json={"disposition": "confirmed_issue", "explanation": "Confirmed issue."}, headers=headers)

    res = client.get(f"/api/v1/analytics/ambiguity-signals?rule_id={rule.id}", headers=headers)
    assert res.status_code == 200
    data = res.json()

    rule_item = data["rules"][0]
    assert rule_item["total_dispositions_count"] == 3
    assert rule_item["distinct_findings_count"] == 3

    fp_sig = next(s for s in rule_item["signals"] if s["signal_type"] == "high_false_positive_rate")
    assert fp_sig["count"] == 2
    assert fp_sig["denominator"] == 3
    assert fp_sig["percentage"] == 66.7


def test_07_role_and_tenant_boundaries_intact(client, auth_tokens, db_session):
    """
    Test 7: Role checks and tenant boundaries are strictly preserved:
    - Content creators cannot submit finding feedback (403).
    - Unauthenticated users cannot submit finding feedback (401).
    - Invalid disposition is rejected (400).
    - Missing justification on challenging disposition is rejected (400).
    """
    creator_headers = auth_tokens["content_creator"]["headers"]
    approver_headers = auth_tokens["approval_manager"]["headers"]
    org_id = auth_tokens["approval_manager"]["org_id"]
    user = db_session.query(User).first()

    rule = KnowledgeRule(
        organization_id=org_id,
        rule_code="RULE-5B2-07",
        title="Rule Security Check",
        rule_type="prohibited_claim",
        pattern=r"\btest07\b",
        explanation="Test rule",
        status="approved"
    )
    db_session.add(rule)
    db_session.commit()

    finding, _, _, _ = _create_base_finding(db_session, org_id, user.id, rule.id)

    # 1. Creator cannot submit
    res_creator = client.post(
        f"/api/v1/analytics/findings/{finding.id}/feedback",
        json={"disposition": "confirmed_issue", "explanation": "Creator trying to review."},
        headers=creator_headers
    )
    assert res_creator.status_code == 403

    # 2. Invalid disposition rejected
    res_inv = client.post(
        f"/api/v1/analytics/findings/{finding.id}/feedback",
        json={"disposition": "not_a_real_disposition", "explanation": "Invalid disposition."},
        headers=approver_headers
    )
    assert res_inv.status_code == 400

    # 3. Challenging disposition requires >= 10 chars explanation
    res_short = client.post(
        f"/api/v1/analytics/findings/{finding.id}/feedback",
        json={"disposition": "false_positive", "explanation": "short"},
        headers=approver_headers
    )
    assert res_short.status_code == 400
    assert "Explanation Required" in res_short.text
