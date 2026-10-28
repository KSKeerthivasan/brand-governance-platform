import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import func, distinct

from app.database import get_db
from app.models.content import (
    ContentItem,
    ContentVersion,
    GovernanceRun,
    GovernanceFinding,
    ApprovalSubmission,
    ApprovalDecision,
    ReviewerFindingDisposition
)
from app.models.knowledge import KnowledgeRule, KnowledgeFact
from app.models.organization import OrganizationMembership, User
from app.api.deps import require_any_member
from app.services.audit import log_audit_event
from app.schemas.analytics import (
    ReviewerFindingDispositionCreate,
    ReviewerFindingDispositionOut,
    AnalyticsOverviewOut,
    RepeatedMistakeItem,
    RepeatedMistakesOut,
    AmbiguitySignal,
    RuleAmbiguityReportItem,
    AmbiguityReportOut
)

logger = logging.getLogger("inkloom.analytics")
router = APIRouter()

ALLOWED_DISPOSITIONS = {
    "confirmed_issue",
    "false_positive",
    "guideline_unclear",
    "conflicting_guidelines",
    "insufficient_evidence",
    "other"
}

DISPOSITIONS_REQUIRING_JUSTIFICATION = {
    "false_positive",
    "guideline_unclear",
    "conflicting_guidelines",
    "insufficient_evidence"
}


# =========================================================================
# 1. REVIEWER FINDING DISPOSITIONS (FEEDBACK MECHANISM)
# =========================================================================

@router.post("/findings/{finding_id}/feedback", response_model=ReviewerFindingDispositionOut)
def record_finding_disposition(
    finding_id: str,
    req: ReviewerFindingDispositionCreate,
    membership: OrganizationMembership = Depends(require_any_member),
    db: Session = Depends(get_db)
):
    """
    Records structured reviewer feedback on a specific governance finding and rule.
    Enforces:
    1. Role: Only authorized reviewers (approval_manager, knowledge_reviewer, org_admin) can submit.
       Content creators are strictly forbidden (403).
    2. Tenant Isolation: Finding must belong to content within the caller's organization.
    3. Justification Gate: Challenging dispositions (false_positive, guideline_unclear,
       conflicting_guidelines, insufficient_evidence) require substantive explanation (>= 10 chars).
    4. Auditable History: Preserves disposition as an immutable event.
    """
    # Invariant 1: Role check
    if membership.role not in ["org_admin", "approval_manager", "knowledge_reviewer"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission Denied: Only authorized reviewers and managers can record finding dispositions."
        )

    # Invariant 2: Validate disposition
    if req.disposition not in ALLOWED_DISPOSITIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid disposition '{req.disposition}'. Allowed: {sorted(list(ALLOWED_DISPOSITIONS))}"
        )

    # Invariant 3: Justification check
    if req.disposition in DISPOSITIONS_REQUIRING_JUSTIFICATION:
        if not req.explanation or len(req.explanation.strip()) < 10:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Explanation Required: Dispositions that question a rule or finding ('{req.disposition}') require a meaningful explanation (minimum 10 characters)."
            )

    # Invariant 4: Tenant isolation
    finding = db.query(GovernanceFinding).join(
        GovernanceRun, GovernanceRun.id == GovernanceFinding.governance_run_id
    ).join(
        ContentVersion, ContentVersion.id == GovernanceRun.content_version_id
    ).join(
        ContentItem, ContentItem.id == ContentVersion.content_item_id
    ).filter(
        GovernanceFinding.id == finding_id,
        ContentItem.organization_id == membership.organization_id
    ).first()

    if not finding:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Governance finding not found within your organization."
        )

    gov_run = finding.governance_run
    version = gov_run.content_version
    item = version.content_item

    # Persist disposition record
    disposition_record = ReviewerFindingDisposition(
        organization_id=membership.organization_id,
        governance_run_id=gov_run.id,
        finding_id=finding.id,
        rule_id=finding.matched_rule_id,
        content_item_id=item.id if item else None,
        content_version_id=version.id if version else None,
        disposition=req.disposition,
        reviewer_id=membership.user_id,
        explanation=req.explanation.strip()
    )
    db.add(disposition_record)
    db.commit()
    db.refresh(disposition_record)

    reviewer_user = db.query(User).filter(User.id == membership.user_id).first()
    reviewer_name = reviewer_user.full_name if reviewer_user else "Reviewer"

    # Audit log entry
    log_audit_event(
        db=db,
        organization_id=membership.organization_id,
        user_id=membership.user_id,
        event_type="FINDING_DISPOSITION_RECORDED",
        entity_type="governance_finding",
        entity_id=finding.id,
        summary=f"Reviewer recorded '{req.disposition}' disposition on finding '{finding.title[:50]}'",
        details={
            "finding_id": finding.id,
            "disposition": req.disposition,
            "rule_id": finding.matched_rule_id,
            "content_item_id": item.id if item else None,
            "version_num": version.version_num if version else None,
            "explanation": req.explanation.strip()
        }
    )

    out = ReviewerFindingDispositionOut.model_validate(disposition_record)
    out.reviewer_name = reviewer_name
    return out


@router.get("/findings/{finding_id}/feedback", response_model=List[ReviewerFindingDispositionOut])
def get_finding_dispositions(
    finding_id: str,
    membership: OrganizationMembership = Depends(require_any_member),
    db: Session = Depends(get_db)
):
    """
    Returns auditable historical dispositions recorded for a specific governance finding.
    """
    finding = db.query(GovernanceFinding).join(
        GovernanceRun, GovernanceRun.id == GovernanceFinding.governance_run_id
    ).join(
        ContentVersion, ContentVersion.id == GovernanceRun.content_version_id
    ).join(
        ContentItem, ContentItem.id == ContentVersion.content_item_id
    ).filter(
        GovernanceFinding.id == finding_id,
        ContentItem.organization_id == membership.organization_id
    ).first()

    if not finding:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Governance finding not found within your organization."
        )

    records = db.query(ReviewerFindingDisposition).filter(
        ReviewerFindingDisposition.finding_id == finding_id,
        ReviewerFindingDisposition.organization_id == membership.organization_id
    ).order_by(ReviewerFindingDisposition.created_at.desc()).all()

    results = []
    for r in records:
        out = ReviewerFindingDispositionOut.model_validate(r)
        if r.reviewer:
            out.reviewer_name = r.reviewer.full_name
        results.append(out)
    return results


# =========================================================================
# 2. HISTORICAL GOVERNANCE ANALYTICS OVERVIEW
# =========================================================================

@router.get("/overview", response_model=AnalyticsOverviewOut)
def get_governance_analytics_overview(
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    channel: Optional[str] = None,
    brand_id: Optional[str] = None,
    severity: Optional[str] = None,
    status_filter: Optional[str] = Query(None, alias="status"),
    membership: OrganizationMembership = Depends(require_any_member),
    db: Session = Depends(get_db)
):
    """
    Returns aggregated historical governance run and finding metrics:
    - Total runs, runs with findings, clean runs
    - Severity and outcome distributions with rigorous percentage definitions
    - Chronological run activity
    """
    # Base query for governance runs
    run_query = db.query(GovernanceRun).join(
        ContentVersion, ContentVersion.id == GovernanceRun.content_version_id
    ).join(
        ContentItem, ContentItem.id == ContentVersion.content_item_id
    ).filter(
        ContentItem.organization_id == membership.organization_id
    )

    if brand_id:
        run_query = run_query.filter(ContentItem.brand_id == brand_id)
    if channel:
        run_query = run_query.filter(ContentItem.channel == channel)

    date_from_dt = None
    date_to_dt = None
    if date_from:
        try:
            date_from_dt = datetime.fromisoformat(date_from)
            run_query = run_query.filter(GovernanceRun.created_at >= date_from_dt)
        except Exception:
            pass
    if date_to:
        try:
            date_to_dt = datetime.fromisoformat(date_to)
            run_query = run_query.filter(GovernanceRun.created_at <= date_to_dt)
        except Exception:
            pass

    runs = run_query.all()
    total_runs = len(runs)

    if total_runs == 0:
        return AnalyticsOverviewOut(
            date_from=date_from,
            date_to=date_to,
            total_runs=0,
            runs_with_findings_count=0,
            runs_with_findings_pct=0.0,
            clean_runs_count=0,
            clean_runs_pct=0.0,
            total_findings=0,
            actionable_findings_count=0,
            actionable_findings_pct=0.0,
            successful_checks_count=0,
            successful_checks_pct=0.0,
            unresolved_review_count=0,
            unresolved_review_pct=0.0,
            findings_by_severity={"critical": 0, "warning": 0, "info": 0},
            findings_by_severity_pct={"critical": 0.0, "warning": 0.0, "info": 0.0},
            actionable_findings_by_severity={"critical": 0, "warning": 0, "info": 0},
            actionable_findings_by_severity_pct={"critical": 0.0, "warning": 0.0, "info": 0.0},
            findings_by_status={},
            findings_by_category={},
            runs_over_time=[],
            data_available=False
        )

    run_ids = [r.id for r in runs]

    # Query findings in these runs
    finding_query = db.query(GovernanceFinding).filter(
        GovernanceFinding.governance_run_id.in_(run_ids)
    )
    if severity:
        finding_query = finding_query.filter(GovernanceFinding.severity == severity)
    if status_filter:
        finding_query = finding_query.filter(GovernanceFinding.status == status_filter)

    all_findings = finding_query.all()
    total_findings = len(all_findings)

    # Classify clean runs based on actual governance engine run status:
    # A run is clean if and only if overall_status is 'passed' (no unresolved warnings/blockers)
    clean_runs = sum(1 for r in runs if r.overall_status == "passed")
    runs_with_findings = total_runs - clean_runs

    runs_with_findings_pct = round((runs_with_findings / total_runs) * 100, 1) if total_runs > 0 else 0.0
    clean_runs_pct = round((clean_runs / total_runs) * 100, 1) if total_runs > 0 else 0.0

    # Separate actionable findings from successful informational checks and review requirements
    actionable_findings = [f for f in all_findings if (f.status or "").lower() != "passed_check"]
    successful_checks = [f for f in all_findings if (f.status or "").lower() == "passed_check"]
    unresolved_review = [f for f in all_findings if (f.status or "").lower() in ("unresolved", "unable_to_verify")]

    actionable_cnt = len(actionable_findings)
    successful_cnt = len(successful_checks)
    unresolved_cnt = len(unresolved_review)

    actionable_pct = round((actionable_cnt / total_findings) * 100, 1) if total_findings > 0 else 0.0
    successful_pct = round((successful_cnt / total_findings) * 100, 1) if total_findings > 0 else 0.0
    unresolved_pct = round((unresolved_cnt / total_findings) * 100, 1) if total_findings > 0 else 0.0

    # Severity distribution (all findings)
    sev_counts = {"critical": 0, "warning": 0, "info": 0}
    for f in all_findings:
        s = f.severity.lower() if f.severity else "warning"
        sev_counts[s] = sev_counts.get(s, 0) + 1

    sev_pcts = {}
    for s, c in sev_counts.items():
        sev_pcts[s] = round((c / total_findings) * 100, 1) if total_findings > 0 else 0.0

    # Severity distribution for actionable findings only (excluding successful informational checks)
    act_sev_counts = {"critical": 0, "warning": 0, "info": 0}
    for f in actionable_findings:
        s = f.severity.lower() if f.severity else "warning"
        act_sev_counts[s] = act_sev_counts.get(s, 0) + 1

    act_sev_pcts = {}
    for s, c in act_sev_counts.items():
        act_sev_pcts[s] = round((c / actionable_cnt) * 100, 1) if actionable_cnt > 0 else 0.0

    # Status distribution
    status_counts = {}
    for f in all_findings:
        st = f.status.lower() if f.status else "unresolved"
        status_counts[st] = status_counts.get(st, 0) + 1

    # Category distribution
    cat_counts = {}
    for f in all_findings:
        cat = f.category or "other"
        cat_counts[cat] = cat_counts.get(cat, 0) + 1

    # Time series (grouped by date)
    date_runs = {}
    date_findings = {}
    date_clean = {}
    for r in runs:
        d_str = r.created_at.strftime("%Y-%m-%d")
        date_runs[d_str] = date_runs.get(d_str, 0) + 1
        if r.overall_status == "passed":
            date_clean[d_str] = date_clean.get(d_str, 0) + 1

    run_date_map = {r.id: r.created_at.strftime("%Y-%m-%d") for r in runs}
    for f in all_findings:
        d_str = run_date_map.get(f.governance_run_id)
        if d_str:
            date_findings[d_str] = date_findings.get(d_str, 0) + 1

    all_dates = sorted(list(date_runs.keys()))
    runs_over_time = [
        {
            "date": d,
            "runs_count": date_runs[d],
            "findings_count": date_findings.get(d, 0),
            "clean_runs_count": date_clean.get(d, 0)
        }
        for d in all_dates
    ]

    return AnalyticsOverviewOut(
        date_from=date_from,
        date_to=date_to,
        total_runs=total_runs,
        runs_with_findings_count=runs_with_findings,
        runs_with_findings_pct=runs_with_findings_pct,
        clean_runs_count=clean_runs,
        clean_runs_pct=clean_runs_pct,
        total_findings=total_findings,
        actionable_findings_count=actionable_cnt,
        actionable_findings_pct=actionable_pct,
        successful_checks_count=successful_cnt,
        successful_checks_pct=successful_pct,
        unresolved_review_count=unresolved_cnt,
        unresolved_review_pct=unresolved_pct,
        findings_by_severity=sev_counts,
        findings_by_severity_pct=sev_pcts,
        actionable_findings_by_severity=act_sev_counts,
        actionable_findings_by_severity_pct=act_sev_pcts,
        findings_by_status=status_counts,
        findings_by_category=cat_counts,
        runs_over_time=runs_over_time,
        data_available=True
    )


# =========================================================================
# 3. REPEATED MISTAKES & RECURRING VIOLATIONS
# =========================================================================

@router.get("/repeated-mistakes", response_model=RepeatedMistakesOut)
def get_repeated_mistakes(
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    channel: Optional[str] = None,
    brand_id: Optional[str] = None,
    severity: Optional[str] = None,
    membership: OrganizationMembership = Depends(require_any_member),
    db: Session = Depends(get_db)
):
    """
    Identifies recurring brand governance violations grouped by rule.
    Enforces strict distinction:
    - Only includes actionable violations/warnings (excludes successful 'passed_check' findings).
    - Counts findings vs distinct content items affected.
    - Separately tracks recurrent issues across revision cycles (versions of the same draft).
    - Evaluates chronological recurrence trend (increasing, decreasing, stable, insufficient_history).
    """
    # Query findings joined with parent entities, filtering out passed checks
    query = db.query(
        GovernanceFinding,
        GovernanceRun,
        ContentVersion,
        ContentItem,
        KnowledgeRule
    ).join(
        GovernanceRun, GovernanceRun.id == GovernanceFinding.governance_run_id
    ).join(
        ContentVersion, ContentVersion.id == GovernanceRun.content_version_id
    ).join(
        ContentItem, ContentItem.id == ContentVersion.content_item_id
    ).join(
        KnowledgeRule, KnowledgeRule.id == GovernanceFinding.matched_rule_id
    ).filter(
        ContentItem.organization_id == membership.organization_id,
        GovernanceFinding.matched_rule_id != None,
        GovernanceFinding.status != "passed_check"
    )

    if brand_id:
        query = query.filter(ContentItem.brand_id == brand_id)
    if channel:
        query = query.filter(ContentItem.channel == channel)
    if severity:
        query = query.filter(GovernanceFinding.severity == severity)

    date_from_dt = None
    date_to_dt = None
    if date_from:
        try:
            date_from_dt = datetime.fromisoformat(date_from)
            query = query.filter(GovernanceRun.created_at >= date_from_dt)
        except Exception:
            pass
    if date_to:
        try:
            date_to_dt = datetime.fromisoformat(date_to)
            query = query.filter(GovernanceRun.created_at <= date_to_dt)
        except Exception:
            pass

    records = query.all()
    if not records:
        return RepeatedMistakesOut(
            date_from=date_from,
            date_to=date_to,
            total_repeated_rules_count=0,
            items=[],
            data_available=False
        )

    # Group by rule
    grouped: Dict[str, Dict[str, Any]] = {}
    for finding, run, version, item, rule in records:
        r_id = rule.id
        if r_id not in grouped:
            grouped[r_id] = {
                "rule": rule,
                "findings": [],
                "items": set(),
                "versions": set(),
                "item_version_pairs": set(),
                "channels": {},
                "timestamps": []
            }

        grouped[r_id]["findings"].append(finding)
        grouped[r_id]["items"].add(item.id)
        grouped[r_id]["versions"].add(version.id)
        grouped[r_id]["item_version_pairs"].add((item.id, version.version_num))
        grouped[r_id]["channels"][item.channel] = grouped[r_id]["channels"].get(item.channel, 0) + 1
        grouped[r_id]["timestamps"].append(run.created_at)

    items_out = []
    for r_id, g in grouped.items():
        rule = g["rule"]
        findings_list = g["findings"]
        distinct_items = g["items"]
        distinct_versions = g["versions"]

        # Recurrent across versions: check how many items had this rule in >1 version
        item_version_counts: Dict[str, int] = {}
        for it_id, v_num in g["item_version_pairs"]:
            item_version_counts[it_id] = item_version_counts.get(it_id, 0) + 1
        recurrent_across_versions = sum(1 for it_id, cnt in item_version_counts.items() if cnt > 1)

        # Severity distribution
        sev_dist = {"critical": 0, "warning": 0, "info": 0}
        for f in findings_list:
            s = f.severity.lower() if f.severity else "warning"
            sev_dist[s] = sev_dist.get(s, 0) + 1

        # Unresolved review requirements count
        unresolved_cnt = sum(1 for f in findings_list if (f.status or "").lower() in ("unresolved", "unable_to_verify"))

        # Trend analysis: compare earlier half vs recent half of timestamps
        timestamps = sorted(g["timestamps"])
        total_cnt = len(timestamps)

        if total_cnt < 3:
            trend = "insufficient_history"
            trend_details = "Fewer than 3 recorded occurrences; insufficient history to establish trend."
        else:
            time_span = (timestamps[-1] - timestamps[0]).total_seconds()
            if time_span < 60:
                trend = "insufficient_history"
                trend_details = "All occurrences happened in a single narrow window (< 1 minute)."
            else:
                mid_point = timestamps[0] + timedelta(seconds=time_span / 2)
                p1_count = sum(1 for t in timestamps if t < mid_point)
                p2_count = sum(1 for t in timestamps if t >= mid_point)

                if p2_count > p1_count * 1.15:
                    trend = "increasing"
                    trend_details = f"Increased from {p1_count} in earlier window to {p2_count} in recent window."
                elif p2_count < p1_count * 0.85:
                    trend = "decreasing"
                    trend_details = f"Decreased from {p1_count} in earlier window to {p2_count} in recent window."
                else:
                    trend = "stable"
                    trend_details = f"Consistent frequency ({p1_count} earlier vs {p2_count} recent)."

        items_out.append(RepeatedMistakeItem(
            rule_id=rule.id,
            rule_code=rule.rule_code,
            rule_title=rule.title,
            rule_type=rule.rule_type,
            category=findings_list[0].category if findings_list else "other",
            total_findings=total_cnt,
            actionable_findings_count=total_cnt,
            successful_checks_count=0,
            unresolved_review_count=unresolved_cnt,
            distinct_content_items_count=len(distinct_items),
            distinct_versions_count=len(distinct_versions),
            severity_distribution=sev_dist,
            channels_distribution=g["channels"],
            products_distribution={},
            recurrent_version_issues_count=recurrent_across_versions,
            recurrence_trend=trend,
            trend_details=trend_details
        ))

    # Sort primarily by distinct content items affected, then total findings
    items_out.sort(key=lambda x: (x.distinct_content_items_count, x.total_findings), reverse=True)

    return RepeatedMistakesOut(
        date_from=date_from,
        date_to=date_to,
        total_repeated_rules_count=len(items_out),
        items=items_out,
        data_available=True
    )


# =========================================================================
# 4. EVIDENCE-BASED GUIDELINE AMBIGUITY SIGNALS
# =========================================================================

@router.get("/ambiguity-signals", response_model=AmbiguityReportOut)
def get_guideline_ambiguity_signals(
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    brand_id: Optional[str] = None,
    rule_id: Optional[str] = None,
    membership: OrganizationMembership = Depends(require_any_member),
    db: Session = Depends(get_db)
):
    """
    Identifies rules with potential ambiguity based on evidence:
    - Repeated reviewer feedback: 'guideline_unclear', 'conflicting_guidelines', 'false_positive', 'insufficient_evidence'
    - High false-positive rate relative to reviewed findings
    - Frequent warning overrides with recorded justifications
    Crucial: Treats findings as potential signals for Knowledge Managers to review, not automatic rule deletion.
    """
    rule_query = db.query(KnowledgeRule).filter(
        KnowledgeRule.organization_id == membership.organization_id,
        KnowledgeRule.status == "approved"
    )
    if brand_id:
        rule_query = rule_query.filter(
            (KnowledgeRule.brand_id == brand_id) | (KnowledgeRule.brand_id == None)
        )
    if rule_id:
        rule_query = rule_query.filter(KnowledgeRule.id == rule_id)

    approved_rules = rule_query.all()
    if not approved_rules:
        return AmbiguityReportOut(
            date_from=date_from,
            date_to=date_to,
            flagged_rules_count=0,
            total_reviewed_rules_count=0,
            criteria_summary="No approved rules found.",
            rules=[],
            data_available=False
        )

    # Base query for dispositions
    disp_query = db.query(ReviewerFindingDisposition).filter(
        ReviewerFindingDisposition.organization_id == membership.organization_id
    )
    if date_from:
        try:
            disp_query = disp_query.filter(ReviewerFindingDisposition.created_at >= datetime.fromisoformat(date_from))
        except Exception:
            pass
    if date_to:
        try:
            disp_query = disp_query.filter(ReviewerFindingDisposition.created_at <= datetime.fromisoformat(date_to))
        except Exception:
            pass

    all_dispositions = disp_query.all()

    # Group dispositions by rule_id
    rule_disp_map: Dict[str, List[ReviewerFindingDisposition]] = {}
    for d in all_dispositions:
        if d.rule_id:
            rule_disp_map.setdefault(d.rule_id, []).append(d)

    # Query warning overrides from ApprovalDecisions where content had warning findings
    # Join decisions with submission, version, run, and findings
    dec_query = db.query(
        ApprovalDecision,
        ContentVersion,
        ContentItem
    ).join(
        ContentVersion, ContentVersion.id == ApprovalDecision.content_version_id
    ).join(
        ContentItem, ContentItem.id == ContentVersion.content_item_id
    ).filter(
        ContentItem.organization_id == membership.organization_id,
        ApprovalDecision.decision == "approved"
    )

    if date_from:
        try:
            dec_query = dec_query.filter(ApprovalDecision.created_at >= datetime.fromisoformat(date_from))
        except Exception:
            pass
    if date_to:
        try:
            dec_query = dec_query.filter(ApprovalDecision.created_at <= datetime.fromisoformat(date_to))
        except Exception:
            pass

    decisions = dec_query.all()
    version_ids = [dec.content_version_id for dec, ver, itm in decisions]

    # Fetch warning findings for these versions with matched rules
    rule_overrides_verified: Dict[str, List[Dict[str, Any]]] = {}
    rule_overrides_content_level: Dict[str, List[Dict[str, Any]]] = {}

    if version_ids:
        warn_findings = db.query(
            GovernanceRun.content_version_id,
            GovernanceFinding.id.label("finding_id"),
            GovernanceFinding.matched_rule_id,
            KnowledgeRule.rule_code,
            KnowledgeRule.title.label("rule_title")
        ).join(
            GovernanceFinding, GovernanceFinding.governance_run_id == GovernanceRun.id
        ).join(
            KnowledgeRule, KnowledgeRule.id == GovernanceFinding.matched_rule_id
        ).filter(
            GovernanceRun.content_version_id.in_(version_ids),
            GovernanceFinding.severity == "warning",
            GovernanceFinding.status != "passed_check",
            GovernanceFinding.matched_rule_id != None
        ).all()

        # Map content_version_id -> dict of rule_id -> {rule_code, rule_title, finding_ids}
        ver_rules_map: Dict[str, Dict[str, Dict[str, Any]]] = {}
        for row in warn_findings:
            v_id = row.content_version_id
            r_id = row.matched_rule_id
            if v_id not in ver_rules_map:
                ver_rules_map[v_id] = {}
            if r_id not in ver_rules_map[v_id]:
                ver_rules_map[v_id][r_id] = {
                    "rule_code": row.rule_code,
                    "rule_title": row.rule_title,
                    "finding_ids": set()
                }
            ver_rules_map[v_id][r_id]["finding_ids"].add(row.finding_id)

        # Attribute approval decisions with warning overrides:
        # Rule Attribution Invariant:
        # - Single-rule warning on version: reliably attributed to that rule.
        # - Multi-rule warnings on version: attributed to rule ONLY if decision comment explicitly cites rule code or title.
        # - Otherwise, classified as content-level warning override and excluded from rule ambiguity score.
        for dec, ver, itm in decisions:
            v_id = dec.content_version_id
            rules_on_ver = ver_rules_map.get(v_id, {})
            if not rules_on_ver:
                continue

            comment_str = dec.comments or ""
            comment_lower = comment_str.lower()

            if len(rules_on_ver) == 1:
                single_r_id = list(rules_on_ver.keys())[0]
                rule_overrides_verified.setdefault(single_r_id, []).append({
                    "comment": comment_str,
                    "content_item_id": itm.id,
                    "finding_ids": list(rules_on_ver[single_r_id]["finding_ids"]),
                    "evidence_source": "approval_decision"
                })
            else:
                attributed_any = False
                for r_id, r_info in rules_on_ver.items():
                    code = (r_info["rule_code"] or "").lower()
                    title = (r_info["rule_title"] or "").lower()
                    has_code = bool(code and code in comment_lower)
                    has_title = bool(title and len(title) > 3 and title in comment_lower)
                    if has_code or has_title:
                        rule_overrides_verified.setdefault(r_id, []).append({
                            "comment": comment_str,
                            "content_item_id": itm.id,
                            "finding_ids": list(r_info["finding_ids"]),
                            "evidence_source": "approval_decision"
                        })
                        attributed_any = True

                if not attributed_any:
                    # Multi-rule warning without rule-specific citation: separate content-level override
                    for r_id, r_info in rules_on_ver.items():
                        rule_overrides_content_level.setdefault(r_id, []).append({
                            "comment": comment_str,
                            "content_item_id": itm.id,
                            "finding_ids": list(r_info["finding_ids"]),
                            "evidence_source": "approval_decision"
                        })

    flagged_rules = []

    for rule in approved_rules:
        dispositions = rule_disp_map.get(rule.id, [])
        verified_overrides = rule_overrides_verified.get(rule.id, [])
        content_level_overrides = rule_overrides_content_level.get(rule.id, [])

        # 1. Group disposition events by finding_id to distinguish events from distinct reviewed findings
        finding_events_map: Dict[str, List[ReviewerFindingDisposition]] = {}
        for d in dispositions:
            finding_events_map.setdefault(d.finding_id, []).append(d)

        # 2. Determine effective (latest) disposition for each distinct finding
        effective_finding_dispositions: Dict[str, ReviewerFindingDisposition] = {}
        for f_id, f_events in finding_events_map.items():
            sorted_events = sorted(f_events, key=lambda x: x.created_at)
            effective_finding_dispositions[f_id] = sorted_events[-1]

        distinct_reviewed_findings_count = len(finding_events_map)
        total_events_count = len(dispositions)

        # Historical events breakdown (across all recorded feedback events)
        historical_events_breakdown: Dict[str, int] = {}
        for d in dispositions:
            historical_events_breakdown[d.disposition] = historical_events_breakdown.get(d.disposition, 0) + 1

        # Effective dispositions breakdown (per distinct finding)
        effective_dispositions_breakdown: Dict[str, int] = {}
        for f_id, eff_d in effective_finding_dispositions.items():
            disp_name = eff_d.disposition
            effective_dispositions_breakdown[disp_name] = effective_dispositions_breakdown.get(disp_name, 0) + 1

        # Distinct content items and findings represented across dispositions and verified overrides
        distinct_disp_items = {d.content_item_id for d in dispositions if d.content_item_id}
        distinct_disp_findings = {d.finding_id for d in dispositions if d.finding_id}
        distinct_ver_items = {o["content_item_id"] for o in verified_overrides if o.get("content_item_id")}
        distinct_ver_findings = {fid for o in verified_overrides for fid in o.get("finding_ids", [])}

        rule_distinct_items_count = len(distinct_disp_items | distinct_ver_items)
        rule_distinct_findings_count = len(distinct_disp_findings | distinct_ver_findings)

        # Evidence base size indicator based on distinct reviewed findings
        if distinct_reviewed_findings_count < 3:
            evidence_base_size = "small"
        elif distinct_reviewed_findings_count < 10:
            evidence_base_size = "moderate"
        else:
            evidence_base_size = "substantial"

        signals: List[AmbiguitySignal] = []
        denominator = distinct_reviewed_findings_count

        # Signal 1: Unclear guidelines
        # Distinct findings that received 'guideline_unclear' feedback
        # Excludes findings whose latest effective disposition was explicitly changed to 'confirmed_issue'
        unclear_finding_ids = [
            f_id for f_id, f_events in finding_events_map.items()
            if any(e.disposition == "guideline_unclear" for e in f_events)
            and effective_finding_dispositions[f_id].disposition != "confirmed_issue"
        ]
        unclear_distinct_count = len(unclear_finding_ids)
        unclear_event_count = historical_events_breakdown.get("guideline_unclear", 0)

        if unclear_distinct_count >= 1:
            samples = [d.explanation for d in dispositions if d.disposition == "guideline_unclear"][:3]
            pct = round((unclear_distinct_count / denominator) * 100, 1) if denominator > 0 else 0.0
            signals.append(AmbiguitySignal(
                signal_type="guideline_unclear",
                title="Guideline Reported Unclear by Reviewers",
                description=(
                    f"{unclear_distinct_count} distinct finding(s) "
                    f"({unclear_event_count} feedback occurrence(s)) "
                    "reported this guideline as ambiguous or difficult to interpret."
                ),
                count=unclear_distinct_count,
                event_count=unclear_event_count,
                denominator=denominator,
                percentage=pct,
                sample_feedback=samples,
                evidence_source="reviewer_disposition",
                distinct_content_items_count=len({effective_finding_dispositions[fid].content_item_id for fid in unclear_finding_ids if effective_finding_dispositions[fid].content_item_id}),
                distinct_findings_count=unclear_distinct_count
            ))

        # Signal 2: Conflicting guidance
        conflict_finding_ids = [
            f_id for f_id, f_events in finding_events_map.items()
            if any(e.disposition == "conflicting_guidelines" for e in f_events)
            and effective_finding_dispositions[f_id].disposition != "confirmed_issue"
        ]
        conflict_distinct_count = len(conflict_finding_ids)
        conflict_event_count = historical_events_breakdown.get("conflicting_guidelines", 0)

        if conflict_distinct_count >= 1:
            samples = [d.explanation for d in dispositions if d.disposition == "conflicting_guidelines"][:3]
            pct = round((conflict_distinct_count / denominator) * 100, 1) if denominator > 0 else 0.0
            signals.append(AmbiguitySignal(
                signal_type="conflicting_guidelines",
                title="Conflicting Guidance Reported",
                description=(
                    f"{conflict_distinct_count} distinct finding(s) "
                    f"({conflict_event_count} feedback occurrence(s)) "
                    "indicated this guideline conflicts with other brand rules or requirements."
                ),
                count=conflict_distinct_count,
                event_count=conflict_event_count,
                denominator=denominator,
                percentage=pct,
                sample_feedback=samples,
                evidence_source="reviewer_disposition",
                distinct_content_items_count=len({effective_finding_dispositions[fid].content_item_id for fid in conflict_finding_ids if effective_finding_dispositions[fid].content_item_id}),
                distinct_findings_count=conflict_distinct_count
            ))

        # Signal 3: High false-positive rate
        # Strictly based on findings whose effective disposition is false_positive
        fp_finding_ids = [
            f_id for f_id, eff_d in effective_finding_dispositions.items()
            if eff_d.disposition == "false_positive"
        ]
        fp_distinct_count = len(fp_finding_ids)
        fp_event_count = historical_events_breakdown.get("false_positive", 0)

        if fp_distinct_count >= 1:
            pct = round((fp_distinct_count / denominator) * 100, 1) if denominator > 0 else 0.0
            if fp_distinct_count >= 2 or pct >= 25.0:
                samples = [d.explanation for d in dispositions if d.disposition == "false_positive"][:3]
                signals.append(AmbiguitySignal(
                    signal_type="high_false_positive_rate",
                    title="Elevated False-Positive Frequency",
                    description=(
                        f"{fp_distinct_count} distinct finding(s) verified as false positive "
                        f"({pct}% of {denominator} reviewed findings; {fp_event_count} feedback occurrence(s)). "
                        "Pattern may be over-triggering."
                    ),
                    count=fp_distinct_count,
                    event_count=fp_event_count,
                    denominator=denominator,
                    percentage=pct,
                    sample_feedback=samples,
                    evidence_source="reviewer_disposition",
                    distinct_content_items_count=len({effective_finding_dispositions[fid].content_item_id for fid in fp_finding_ids if effective_finding_dispositions[fid].content_item_id}),
                    distinct_findings_count=fp_distinct_count
                ))

        # Signal 4: Insufficient evidence reports
        ins_finding_ids = [
            f_id for f_id, f_events in finding_events_map.items()
            if any(e.disposition == "insufficient_evidence" for e in f_events)
            and effective_finding_dispositions[f_id].disposition != "confirmed_issue"
        ]
        ins_distinct_count = len(ins_finding_ids)
        ins_event_count = historical_events_breakdown.get("insufficient_evidence", 0)

        if ins_distinct_count >= 1:
            samples = [d.explanation for d in dispositions if d.disposition == "insufficient_evidence"][:3]
            pct = round((ins_distinct_count / denominator) * 100, 1) if denominator > 0 else 0.0
            signals.append(AmbiguitySignal(
                signal_type="insufficient_evidence",
                title="Insufficient Rule Context / Evidence",
                description=(
                    f"{ins_distinct_count} distinct finding(s) "
                    f"({ins_event_count} feedback occurrence(s)) "
                    "noted the rule lacks clear supporting evidence passages or definitions."
                ),
                count=ins_distinct_count,
                event_count=ins_event_count,
                denominator=denominator,
                percentage=pct,
                sample_feedback=samples,
                evidence_source="reviewer_disposition",
                distinct_content_items_count=len({effective_finding_dispositions[fid].content_item_id for fid in ins_finding_ids if effective_finding_dispositions[fid].content_item_id}),
                distinct_findings_count=ins_distinct_count
            ))

        # Signal 5: Frequent warning overrides (strictly based on verified rule overrides)
        verified_override_count = len(verified_overrides)
        if verified_override_count >= 2:
            override_samples = [o["comment"] for o in verified_overrides if o.get("comment")][:3]
            signals.append(AmbiguitySignal(
                signal_type="warning_override_frequency",
                title="Frequent Reviewer Warning Overrides",
                description=f"Approved with verified warning justifications on {verified_override_count} occasion(s). Suggests creators repeatedly encounter legitimate exceptions.",
                count=verified_override_count,
                event_count=verified_override_count,
                denominator=verified_override_count,
                percentage=100.0,
                sample_feedback=override_samples,
                evidence_source="approval_decision",
                distinct_content_items_count=len(distinct_ver_items),
                distinct_findings_count=len(distinct_ver_findings)
            ))

        # Determine ambiguity level and score
        if not signals:
            continue

        # Ambiguity score calculation uses distinct findings counts, not raw duplicate events
        score = float(len(signals) * 20 + unclear_distinct_count * 15 + conflict_distinct_count * 25 + fp_distinct_count * 10)
        if len(signals) >= 2 or conflict_distinct_count >= 1 or unclear_distinct_count >= 2:
            level = "high"
            rec_action = "High Priority: Knowledge Manager should review rule wording, define exceptions, and clarify pattern in Knowledge Library."
        elif len(signals) >= 1 or fp_distinct_count >= 1:
            level = "medium"
            rec_action = "Medium Priority: Inspect rule examples and verify pattern precision against legitimate phrasing."
        else:
            level = "low"
            rec_action = "Monitor future reviewer feedback."

        if evidence_base_size == "small":
            rec_action += " (Note: small evidence base — fewer than 3 reviewer dispositions; recommend monitoring before modifying rule)."

        # Notes documenting any content-level overrides excluded from rule score
        content_level_cnt = len(content_level_overrides)
        attribution_notes = None
        if content_level_cnt > 0:
            attribution_notes = (
                f"{content_level_cnt} content-level warning override(s) excluded from rule ambiguity score "
                f"because approval covered multiple rules without rule-specific citation."
            )

        flagged_rules.append(RuleAmbiguityReportItem(
            rule_id=rule.id,
            rule_code=rule.rule_code,
            rule_title=rule.title,
            rule_type=rule.rule_type,
            source_citation=rule.source_citation,
            ambiguity_level=level,
            ambiguity_score=round(score, 1),
            total_dispositions_count=distinct_reviewed_findings_count,
            total_events_count=total_events_count,
            dispositions_breakdown=historical_events_breakdown,
            effective_dispositions_breakdown=effective_dispositions_breakdown,
            distinct_content_items_count=rule_distinct_items_count,
            distinct_findings_count=rule_distinct_findings_count,
            evidence_base_size=evidence_base_size,
            warning_overrides_count=verified_override_count,
            verified_rule_overrides_count=verified_override_count,
            content_level_overrides_count=content_level_cnt,
            override_attribution_notes=attribution_notes,
            signals=signals,
            recommended_action=rec_action
        ))

    # Sort flagged rules by score descending
    flagged_rules.sort(key=lambda x: x.ambiguity_score, reverse=True)

    criteria_summary = (
        "Rules flagged based on recorded reviewer dispositions (unclear, conflicting, false positive, insufficient evidence) "
        "and verified rule-level warning overrides with recorded justifications. Multi-rule content-level warning approvals "
        "are excluded from rule ambiguity scores unless explicitly cited. Results represent potential signals for Knowledge Managers "
        "and do not automatically alter canonical rules."
    )

    return AmbiguityReportOut(
        date_from=date_from,
        date_to=date_to,
        flagged_rules_count=len(flagged_rules),
        total_reviewed_rules_count=len(approved_rules),
        criteria_summary=criteria_summary,
        rules=flagged_rules,
        data_available=len(flagged_rules) > 0
    )
