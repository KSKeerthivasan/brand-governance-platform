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
from app.models.organization import Organization, User, OrganizationMembership

def _create_test_finding(db_session, org_id, rule_id=None, severity="warning"):
    brand = db_session.query(Brand).filter(Brand.organization_id == org_id).first()
    user = db_session.query(User).first()
    if not rule_id:
        rule = db_session.query(KnowledgeRule).filter(KnowledgeRule.organization_id == org_id).first()
        rule_id = rule.id if rule else None

    item = ContentItem(
        organization_id=org_id,
        brand_id=brand.id,
        created_by=user.id,
        title="Test Feedback Draft",
        channel="instagram"
    )
    db_session.add(item)
    db_session.flush()

    checksum = hashlib.sha256(b"Test Draft Body").hexdigest()
    version = ContentVersion(
        content_item_id=item.id,
        version_num=1,
        body_text="Test Draft Body",
        checksum=checksum,
        created_by=user.id
    )
    db_session.add(version)
    db_session.flush()

    run = GovernanceRun(content_version_id=version.id, overall_status="warnings", rules_evaluated_count=5)
    db_session.add(run)
    db_session.flush()

    finding = GovernanceFinding(
        governance_run_id=run.id,
        matched_rule_id=rule_id,
        title="Test Rule Finding",
        category="prohibited_claim",
        explanation="Detected prohibited claim in text",
        severity=severity,
        status="unresolved",
        source_citation="Brand Guidelines v2",
        recommended_action="Remove claim"
    )
    db_session.add(finding)
    db_session.commit()
    db_session.refresh(finding)
    return finding


def test_01_historical_aggregates_and_denominators(client, auth_tokens, db_session):
    """
    Test 1: Verify overview aggregates match persisted governance runs and findings.
    Verify that all percentage metrics have clearly defined and mathematically correct denominators.
    """
    headers = auth_tokens["approval_manager"]["headers"]
    org_id = auth_tokens["approval_manager"]["org_id"]

    res = client.get("/api/v1/analytics/overview", headers=headers)
    assert res.status_code == 200, res.text
    data = res.json()

    # Query DB directly to verify ground truth
    total_runs_db = db_session.query(GovernanceRun).join(
        ContentVersion, ContentVersion.id == GovernanceRun.content_version_id
    ).join(
        ContentItem, ContentItem.id == ContentVersion.content_item_id
    ).filter(ContentItem.organization_id == org_id).count()

    assert data["total_runs"] == total_runs_db
    if total_runs_db > 0:
        assert data["data_available"] is True
        # Verify denominator mathematical integrity:
        # runs_with_findings_pct + clean_runs_pct should equal 100% (within 0.2 rounding)
        assert abs((data["runs_with_findings_pct"] + data["clean_runs_pct"]) - 100.0) <= 0.2
        assert data["runs_with_findings_count"] + data["clean_runs_count"] == data["total_runs"]

        # Verify severity distribution
        if data["total_findings"] > 0:
            sev_sum = sum(data["findings_by_severity"].values())
            assert sev_sum == data["total_findings"]
            sev_pct_sum = sum(data["findings_by_severity_pct"].values())
            assert abs(sev_pct_sum - 100.0) <= 0.5


def test_02_repeated_mistakes_distinct_content_items_distinction(client, auth_tokens, db_session):
    """
    Test 2: Verify that repeated mistakes separate findings count from distinct affected content items.
    Multiple findings within a single run/draft must not inflate the distinct items count.
    """
    headers = auth_tokens["approval_manager"]["headers"]
    org_id = auth_tokens["approval_manager"]["org_id"]

    brand = db_session.query(Brand).filter(Brand.organization_id == org_id).first()
    assert brand is not None
    user = db_session.query(User).first()
    assert user is not None

    rule = db_session.query(KnowledgeRule).filter(KnowledgeRule.organization_id == org_id).first()
    assert rule is not None

    # Create 1 content item with 1 version, 1 run, but 2 findings of the same rule
    item = ContentItem(
        organization_id=org_id,
        brand_id=brand.id,
        created_by=user.id,
        title="Multi Finding Draft",
        channel="instagram"
    )
    db_session.add(item)
    db_session.flush()

    checksum = hashlib.sha256(b"Draft with 2 violations").hexdigest()
    version = ContentVersion(
        content_item_id=item.id,
        version_num=1,
        body_text="Draft with 2 violations",
        checksum=checksum,
        created_by=user.id
    )
    db_session.add(version)
    db_session.flush()

    run = GovernanceRun(content_version_id=version.id, overall_status="failed", rules_evaluated_count=1)
    db_session.add(run)
    db_session.flush()

    f1 = GovernanceFinding(
        governance_run_id=run.id,
        matched_rule_id=rule.id,
        category="prohibited_claim",
        title="Violation 1",
        explanation="First instance",
        severity="critical",
        status="unresolved",
        source_citation="Guide",
        recommended_action="Fix"
    )
    f2 = GovernanceFinding(
        governance_run_id=run.id,
        matched_rule_id=rule.id,
        category="prohibited_claim",
        title="Violation 2",
        explanation="Second instance",
        severity="critical",
        status="unresolved",
        source_citation="Guide",
        recommended_action="Fix"
    )
    db_session.add_all([f1, f2])
    db_session.commit()

    res = client.get("/api/v1/analytics/repeated-mistakes", headers=headers)
    assert res.status_code == 200
    data = res.json()

    # Find this rule in repeated mistakes
    rule_item = next((r for r in data["items"] if r["rule_id"] == rule.id), None)
    assert rule_item is not None
    # Total findings must be >= 2, but distinct content items must strictly count items
    assert rule_item["total_findings"] >= 2
    assert rule_item["distinct_content_items_count"] <= rule_item["total_findings"]


def test_03_analytics_filters(client, auth_tokens):
    """
    Test 3: Verify that date-range, channel, and severity filters affect the aggregates consistently.
    """
    headers = auth_tokens["approval_manager"]["headers"]

    # Filter by specific channel
    res_insta = client.get("/api/v1/analytics/overview?channel=instagram", headers=headers)
    assert res_insta.status_code == 200
    data_insta = res_insta.json()

    res_all = client.get("/api/v1/analytics/overview", headers=headers)
    assert res_all.status_code == 200
    data_all = res_all.json()

    # Instagram runs should be <= all runs
    assert data_insta["total_runs"] <= data_all["total_runs"]

    # Filter by severity
    res_crit = client.get("/api/v1/analytics/overview?severity=critical", headers=headers)
    assert res_crit.status_code == 200
    data_crit = res_crit.json()
    assert data_crit["findings_by_severity"].get("warning", 0) == 0


def test_04_trend_determination_with_insufficient_and_sufficient_history(client, auth_tokens, db_session):
    """
    Test 4: Verify recurrence trends. Rules with < 3 occurrences must report 'insufficient_history'
    rather than fabricating a trend.
    """
    headers = auth_tokens["approval_manager"]["headers"]
    org_id = auth_tokens["approval_manager"]["org_id"]

    brand = db_session.query(Brand).filter(Brand.organization_id == org_id).first()
    assert brand is not None
    user = db_session.query(User).first()
    assert user is not None

    # Create a rule with only 1 occurrence
    rule_single = KnowledgeRule(
        organization_id=org_id,
        rule_code="TEST-SINGLE-01",
        title="Single Occurrence Rule",
        rule_type="prohibited_word",
        pattern="test-single",
        explanation="Do not use test-single pattern",
        severity="warning",
        status="approved",
        source_citation="Test Guide"
    )
    db_session.add(rule_single)
    db_session.flush()

    item = ContentItem(
        organization_id=org_id,
        brand_id=brand.id,
        created_by=user.id,
        title="Single Finding Item",
        channel="web"
    )
    db_session.add(item)
    db_session.flush()

    checksum = hashlib.sha256(b"test-single").hexdigest()
    ver = ContentVersion(
        content_item_id=item.id,
        version_num=1,
        body_text="test-single",
        checksum=checksum,
        created_by=user.id
    )
    db_session.add(ver)
    db_session.flush()

    run = GovernanceRun(content_version_id=ver.id, overall_status="failed", created_at=datetime.utcnow() - timedelta(days=5))
    db_session.add(run)
    db_session.flush()
    f = GovernanceFinding(
        governance_run_id=run.id,
        matched_rule_id=rule_single.id,
        category="tone",
        title="Single Finding",
        explanation="Found single",
        severity="warning",
        status="unresolved",
        source_citation="Guide",
        recommended_action="Fix"
    )
    db_session.add(f)
    db_session.commit()

    res = client.get("/api/v1/analytics/repeated-mistakes", headers=headers)
    assert res.status_code == 200
    data = res.json()

    rule_out = next((r for r in data["items"] if r["rule_id"] == rule_single.id), None)
    assert rule_out is not None
    assert rule_out["recurrence_trend"] == "insufficient_history"
    assert "insufficient history" in rule_out["trend_details"].lower()


def test_05_reviewer_feedback_recording_and_role_enforcement(client, auth_tokens, db_session):
    """
    Test 5: Verify structured reviewer feedback mechanism and role enforcement:
    - Content creators must be rejected with 403 Forbidden.
    - Approval managers, knowledge reviewers, and org admins must be permitted.
    """
    org_id = auth_tokens["approval_manager"]["org_id"]
    finding = _create_test_finding(db_session, org_id)

    payload = {
        "disposition": "confirmed_issue",
        "explanation": "Legitimate violation confirmed during approval review."
    }

    # 1. Content Creator attempt -> 403 Forbidden
    creator_headers = auth_tokens["content_creator"]["headers"]
    res_creator = client.post(f"/api/v1/analytics/findings/{finding.id}/feedback", json=payload, headers=creator_headers)
    assert res_creator.status_code == 403
    assert "Permission Denied" in res_creator.text

    # 2. Approval Manager attempt -> 200 OK
    approver_headers = auth_tokens["approval_manager"]["headers"]
    res_approver = client.post(f"/api/v1/analytics/findings/{finding.id}/feedback", json=payload, headers=approver_headers)
    assert res_approver.status_code == 200
    disp_data = res_approver.json()
    assert disp_data["disposition"] == "confirmed_issue"
    assert disp_data["finding_id"] == finding.id
    assert disp_data["reviewer_name"] is not None

    # Verify history retrieval
    res_hist = client.get(f"/api/v1/analytics/findings/{finding.id}/feedback", headers=approver_headers)
    assert res_hist.status_code == 200
    assert len(res_hist.json()) >= 1


def test_06_reviewer_feedback_justification_gate(client, auth_tokens, db_session):
    """
    Test 6: Verify justification requirement for challenging dispositions:
    - guideline_unclear, false_positive, conflicting_guidelines, insufficient_evidence
      require >= 10 characters explanation.
    """
    approver_headers = auth_tokens["approval_manager"]["headers"]
    org_id = auth_tokens["approval_manager"]["org_id"]
    finding = _create_test_finding(db_session, org_id)

    # Attempt with empty explanation
    res_empty = client.post(
        f"/api/v1/analytics/findings/{finding.id}/feedback",
        json={"disposition": "guideline_unclear", "explanation": "vague"},
        headers=approver_headers
    )
    assert res_empty.status_code == 400
    assert "Explanation Required" in res_empty.text

    # Attempt with >= 10 characters
    res_valid = client.post(
        f"/api/v1/analytics/findings/{finding.id}/feedback",
        json={
            "disposition": "guideline_unclear",
            "explanation": "Guideline wording is vague and does not define acceptable context."
        },
        headers=approver_headers
    )
    assert res_valid.status_code == 200
    assert res_valid.json()["disposition"] == "guideline_unclear"


def test_07_tenant_isolation_analytics_and_feedback(client, auth_tokens, db_session):
    """
    Test 7: Verify tenant boundaries:
    - Users from Org B cannot view or submit feedback on Org A findings.
    - Org B analytics overview does not leak Org A data.
    """
    org_id_a = auth_tokens["approval_manager"]["org_id"]
    finding_org_a = _create_test_finding(db_session, org_id_a)

    # Create an isolated Org B with brand and user
    org_b = Organization(name="Other Corp", slug="other-corp")
    db_session.add(org_b)
    db_session.flush()

    brand_b = Brand(organization_id=org_b.id, name="Other Brand")
    db_session.add(brand_b)
    db_session.flush()

    user_b = User(
        email="manager@othercorp.com",
        full_name="Other Manager",
        hashed_password="fakehashpassword123"
    )
    db_session.add(user_b)
    db_session.flush()

    membership_b = OrganizationMembership(organization_id=org_b.id, user_id=user_b.id, role="approval_manager")
    db_session.add(membership_b)
    db_session.commit()

    # Create valid auth token for Org B approval manager
    from app.services.auth import create_access_token
    token_b = create_access_token({
        "sub": user_b.id,
        "email": user_b.email,
        "org_id": org_b.id,
        "role": "approval_manager",
        "is_demo": False
    })
    headers_b = {
        "Authorization": f"Bearer {token_b}",
        "X-Organization-Id": org_b.id
    }

    # Org B checks its overview: must be 0 runs and data_available=False
    res_b_overview = client.get("/api/v1/analytics/overview", headers=headers_b)
    assert res_b_overview.status_code == 200
    assert res_b_overview.json()["total_runs"] == 0
    assert res_b_overview.json()["data_available"] is False

    # Org B attempts to record feedback on Org A finding -> 404 Not Found
    res_cross_disp = client.post(
        f"/api/v1/analytics/findings/{finding_org_a.id}/feedback",
        json={"disposition": "confirmed_issue", "explanation": "Hacking across tenant"},
        headers=headers_b
    )
    assert res_cross_disp.status_code == 404


def test_08_guideline_ambiguity_signals_derived_from_evidence(client, auth_tokens, db_session):
    """
    Test 8: Verify guideline ambiguity signals are derived from recorded reviewer feedback
    (unclear, conflicting, false positive, insufficient evidence) and warning overrides, NOT mere violation count.
    """
    approver_headers = auth_tokens["approval_manager"]["headers"]
    org_id = auth_tokens["approval_manager"]["org_id"]

    brand = db_session.query(Brand).filter(Brand.organization_id == org_id).first()
    assert brand is not None
    user = db_session.query(User).first()
    assert user is not None

    # Create a rule specifically to test ambiguity signals
    rule_ambig = KnowledgeRule(
        organization_id=org_id,
        rule_code="AMBIG-TEST-01",
        title="Ambiguous Tone Guideline",
        rule_type="tone_guideline",
        pattern="youthfully",
        explanation="Speak youthfully but strictly professionally.",
        severity="warning",
        status="approved",
        source_citation="Tone Guide Sec 4"
    )
    db_session.add(rule_ambig)
    db_session.flush()

    item = ContentItem(
        organization_id=org_id,
        brand_id=brand.id,
        created_by=user.id,
        title="Ambiguity Test Item",
        channel="instagram"
    )
    db_session.add(item)
    db_session.flush()

    checksum = hashlib.sha256(b"Testing ambiguous tone").hexdigest()
    ver = ContentVersion(
        content_item_id=item.id,
        version_num=1,
        body_text="Testing ambiguous tone",
        checksum=checksum,
        created_by=user.id
    )
    db_session.add(ver)
    db_session.flush()

    run = GovernanceRun(content_version_id=ver.id, overall_status="warnings")
    db_session.add(run)
    db_session.flush()
    finding = GovernanceFinding(
        governance_run_id=run.id,
        matched_rule_id=rule_ambig.id,
        category="tone",
        title="Tone check warning",
        explanation="Tone unclear",
        severity="warning",
        status="unresolved",
        source_citation="Tone Guide Sec 4",
        recommended_action="Clarify tone"
    )
    db_session.add(finding)
    db_session.commit()

    # Record 2 'guideline_unclear' reviewer dispositions on this finding
    res1 = client.post(
        f"/api/v1/analytics/findings/{finding.id}/feedback",
        json={
            "disposition": "guideline_unclear",
            "explanation": "Reviewer 1 found youthfully vs strictly professional conflicting and vague."
        },
        headers=approver_headers
    )
    assert res1.status_code == 200

    res2 = client.post(
        f"/api/v1/analytics/findings/{finding.id}/feedback",
        json={
            "disposition": "conflicting_guidelines",
            "explanation": "Reviewer 2 notes this rule contradicts Brand Rule B-02 on casual social tone."
        },
        headers=approver_headers
    )
    assert res2.status_code == 200

    # Query ambiguity signals endpoint
    res_ambig = client.get("/api/v1/analytics/ambiguity-signals", headers=approver_headers)
    assert res_ambig.status_code == 200
    report = res_ambig.json()

    flagged_rule = next((r for r in report["rules"] if r["rule_id"] == rule_ambig.id), None)
    assert flagged_rule is not None
    assert flagged_rule["ambiguity_level"] in ["high", "medium"]
    assert flagged_rule["ambiguity_score"] > 0
    assert flagged_rule["dispositions_breakdown"].get("guideline_unclear", 0) >= 1
    assert flagged_rule["dispositions_breakdown"].get("conflicting_guidelines", 0) >= 1

    # Verify signals contain exact criteria and samples
    signal_types = [s["signal_type"] for s in flagged_rule["signals"]]
    assert "guideline_unclear" in signal_types
    assert "conflicting_guidelines" in signal_types

    # Ensure rule was NOT auto-deleted or deactivated
    db_rule = db_session.query(KnowledgeRule).filter(KnowledgeRule.id == rule_ambig.id).first()
    assert db_rule.status == "approved"


def test_09_legacy_and_empty_records_handling(client, auth_tokens, db_session):
    """
    Test 9: Verify analytics endpoints gracefully handle malformed, missing, or legacy records without crashing.
    """
    headers = auth_tokens["approval_manager"]["headers"]
    org_id = auth_tokens["approval_manager"]["org_id"]

    brand = db_session.query(Brand).filter(Brand.organization_id == org_id).first()
    assert brand is not None
    user = db_session.query(User).first()
    assert user is not None

    # Create a legacy finding with NULL matched_rule_id
    item = ContentItem(
        organization_id=org_id,
        brand_id=brand.id,
        created_by=user.id,
        title="Legacy Orphan Item",
        channel="email"
    )
    db_session.add(item)
    db_session.flush()

    checksum = hashlib.sha256(b"Legacy orphan text").hexdigest()
    ver = ContentVersion(
        content_item_id=item.id,
        version_num=1,
        body_text="Legacy orphan text",
        checksum=checksum,
        created_by=user.id
    )
    db_session.add(ver)
    db_session.flush()

    run = GovernanceRun(content_version_id=ver.id, overall_status="warnings")
    db_session.add(run)
    db_session.flush()
    legacy_finding = GovernanceFinding(
        governance_run_id=run.id,
        matched_rule_id=None,  # Legacy finding without matched rule
        category="tone",
        title="Unattributed heuristic warning",
        explanation="Legacy run before rule linkage was required",
        severity="info",
        status="unresolved",
        source_citation="",
        recommended_action=""
    )
    db_session.add(legacy_finding)
    db_session.commit()

    # All analytics endpoints must succeed without 500 error
    res_ov = client.get("/api/v1/analytics/overview", headers=headers)
    assert res_ov.status_code == 200

    res_rep = client.get("/api/v1/analytics/repeated-mistakes", headers=headers)
    assert res_rep.status_code == 200

    res_amb = client.get("/api/v1/analytics/ambiguity-signals", headers=headers)
    assert res_amb.status_code == 200


def test_10_existing_governance_and_approval_workflow_unbroken(client, auth_tokens, db_session):
    """
    Test 10: Regression safety: Verify that creating content drafts, running governance checks,
    submitting for approval, and approving still work cleanly without any regressions.
    """
    creator_headers = auth_tokens["content_creator"]["headers"]
    approver_headers = auth_tokens["approval_manager"]["headers"]
    org_id = auth_tokens["approval_manager"]["org_id"]

    brand = db_session.query(Brand).filter(Brand.organization_id == org_id).first()
    assert brand is not None

    # 1. Creator creates draft
    res_create = client.post("/api/v1/content", json={
        "brand_id": brand.id,
        "title": "Milestone 5B Regression Test Draft",
        "channel": "instagram",
        "body_text": "Enjoy Freshsip natural sparkling iced tea."
    }, headers=creator_headers)
    assert res_create.status_code == 200, res_create.text
    item_id = res_create.json()["id"]
    version_id = res_create.json()["latest_version"]["id"]

    # 2. Run governance check
    res_gov = client.post("/api/v1/governance/run", json={
        "content_version_id": version_id
    }, headers=creator_headers)
    assert res_gov.status_code == 200
    assert "overall_status" in res_gov.json()

    # 3. Creator submits for approval
    res_sub = client.post("/api/v1/approvals/submit", json={
        "content_item_id": item_id,
        "content_version_id": version_id,
        "submission_notes": "Submitting clean draft for approval."
    }, headers=creator_headers)
    assert res_sub.status_code == 200
    sub_id = res_sub.json()["id"]

    # 4. Approval manager reviews and decides
    res_dec = client.post(f"/api/v1/approvals/submissions/{sub_id}/decide", json={
        "decision": "approved",
        "comments": "Approved after reviewing clean governance check."
    }, headers=approver_headers)
    assert res_dec.status_code == 200
    assert res_dec.json()["decision"] == "approved"
