from typing import Optional, List, Dict, Any
from pydantic import BaseModel, ConfigDict, Field
from datetime import datetime

class ReviewerFindingDispositionCreate(BaseModel):
    disposition: str  # confirmed_issue, false_positive, guideline_unclear, conflicting_guidelines, insufficient_evidence, other
    explanation: str = Field(..., description="Justification or feedback detail")

class ReviewerFindingDispositionOut(BaseModel):
    id: str
    organization_id: str
    governance_run_id: str
    finding_id: str
    rule_id: Optional[str] = None
    content_item_id: Optional[str] = None
    content_version_id: Optional[str] = None
    disposition: str
    reviewer_id: str
    reviewer_name: Optional[str] = None
    explanation: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class AnalyticsOverviewOut(BaseModel):
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    total_runs: int
    runs_with_findings_count: int
    runs_with_findings_pct: float
    clean_runs_count: int
    clean_runs_pct: float
    total_findings: int
    actionable_findings_count: int = 0
    actionable_findings_pct: float = 0.0
    successful_checks_count: int = 0
    successful_checks_pct: float = 0.0
    unresolved_review_count: int = 0
    unresolved_review_pct: float = 0.0
    findings_by_severity: Dict[str, int]
    findings_by_severity_pct: Dict[str, float]
    actionable_findings_by_severity: Dict[str, int] = {}
    actionable_findings_by_severity_pct: Dict[str, float] = {}
    findings_by_status: Dict[str, int]
    findings_by_category: Dict[str, int]
    runs_over_time: List[Dict[str, Any]]
    data_available: bool

class RepeatedMistakeItem(BaseModel):
    rule_id: str
    rule_code: Optional[str] = None
    rule_title: str
    rule_type: str
    category: str
    total_findings: int
    actionable_findings_count: int = 0
    successful_checks_count: int = 0
    unresolved_review_count: int = 0
    distinct_content_items_count: int
    distinct_versions_count: int
    severity_distribution: Dict[str, int]
    channels_distribution: Dict[str, int]
    products_distribution: Dict[str, int]
    recurrent_version_issues_count: int
    recurrence_trend: str  # increasing, decreasing, stable, insufficient_history
    trend_details: Optional[str] = None

class RepeatedMistakesOut(BaseModel):
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    total_repeated_rules_count: int
    items: List[RepeatedMistakeItem]
    data_available: bool

class AmbiguitySignal(BaseModel):
    signal_type: str  # guideline_unclear, conflicting_guidelines, high_false_positive_rate, warning_override_frequency, insufficient_evidence
    title: str
    description: str
    count: int  # Distinct findings represented
    event_count: int = 0  # Total historical feedback occurrences
    denominator: int  # Distinct reviewed findings for rule
    percentage: float
    date_range: Optional[str] = None
    sample_feedback: List[str] = []
    evidence_source: str = "reviewer_disposition"  # reviewer_disposition or approval_decision
    distinct_content_items_count: int = 0
    distinct_findings_count: int = 0

class RuleAmbiguityReportItem(BaseModel):
    rule_id: str
    rule_code: Optional[str] = None
    rule_title: str
    rule_type: str
    source_citation: Optional[str] = None
    ambiguity_level: str  # high, medium, low
    ambiguity_score: float
    total_dispositions_count: int  # Distinct reviewed findings
    total_events_count: int = 0  # All historical feedback events
    dispositions_breakdown: Dict[str, int]  # All historical events breakdown
    effective_dispositions_breakdown: Dict[str, int] = {}  # Effective disposition per distinct finding
    distinct_content_items_count: int = 0
    distinct_findings_count: int = 0
    evidence_base_size: str = "small"  # small, moderate, substantial
    warning_overrides_count: int = 0
    verified_rule_overrides_count: int = 0
    content_level_overrides_count: int = 0
    override_attribution_notes: Optional[str] = None
    signals: List[AmbiguitySignal]
    recommended_action: str

class AmbiguityReportOut(BaseModel):
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    flagged_rules_count: int
    total_reviewed_rules_count: int
    criteria_summary: str
    rules: List[RuleAmbiguityReportItem]
    data_available: bool
