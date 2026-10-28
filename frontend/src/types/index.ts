export type UserRole = 'org_admin' | 'knowledge_reviewer' | 'content_creator' | 'approval_manager';

export interface User {
  id: string;
  email: string;
  full_name: string;
  is_active: boolean;
  created_at: string;
}

export interface AuthState {
  token: string | null;
  user: User | null;
  organizationId: string | null;
  organizationName: string | null;
  organizationSlug: string | null;
  role: UserRole | null;
  isDemo: boolean;
  isAuthenticated: boolean;
}

export interface Organization {
  id: string;
  name: string;
  slug: string;
  created_at: string;
}

export interface Member {
  id: string;
  organization_id: string;
  user_id: string;
  user_email: string;
  user_full_name: string;
  role: UserRole;
  created_at: string;
}

export interface Brand {
  id: string;
  organization_id: string;
  name: string;
  description?: string;
  created_at: string;
}

export interface KnowledgeSource {
  id: string;
  organization_id: string;
  brand_id?: string;
  title: string;
  source_type: string;
  filename: string;
  file_size_bytes: number;
  mime_type: string;
  version: number;
  status: 'pending_review' | 'reviewed' | 'archived';
  extracted_summary?: string;
  created_at: string;
  rules_count?: number;
  facts_count?: number;
  assets_count?: number;
}

export interface KnowledgeRule {
  id: string;
  organization_id: string;
  brand_id?: string;
  source_id?: string;
  rule_type: string;
  title: string;
  pattern: string;
  explanation: string;
  severity: 'critical' | 'warning' | 'info';
  context_condition?: string;
  source_citation?: string;
  rule_code?: string;
  source_status?: 'approved' | 'pending_review' | 'expired' | 'rejected' | 'unknown';
  enforcement_action?: string;
  rationale?: string;
  recommended_alternatives?: string;
  exceptions?: string;
  examples_bad?: string;
  examples_good?: string;
  evidence_passage?: string;
  page_number?: number;
  evidence_validation?: string;
  uncertainty_notes?: string;
  is_corrected?: boolean;
  status: 'pending_review' | 'approved' | 'rejected' | 'deprecated';
  reviewed_by?: string;
  reviewed_at?: string;
  review_notes?: string;
  created_at: string;
}

export interface KnowledgeFact {
  id: string;
  organization_id: string;
  brand_id?: string;
  source_id?: string;
  product_name: string;
  category: string;
  fact_key: string;
  fact_value: string;
  supporting_evidence?: string;
  source_citation?: string;
  product_id?: string;
  unit?: string;
  value_status?: string;
  source_status?: 'approved' | 'pending_review' | 'expired' | 'rejected' | 'unknown';
  page_number?: number;
  evidence_validation?: string;
  uncertainty_notes?: string;
  is_corrected?: boolean;
  valid_from?: string;
  valid_until?: string;
  status: 'pending_review' | 'approved' | 'rejected' | 'expired';
  reviewed_by?: string;
  reviewed_at?: string;
  review_notes?: string;
  created_at: string;
}

export interface BrandAsset {
  id: string;
  organization_id: string;
  brand_id?: string;
  source_id?: string;
  asset_name: string;
  asset_type: string;
  file_path: string;
  mime_type: string;
  width?: number;
  height?: number;
  aspect_ratio?: string;
  color_mode?: string;
  min_clearance_px?: number;
  alt_text_required: boolean;
  status: 'pending_review' | 'approved' | 'rejected';
  created_at: string;
}

export interface ContentVersion {
  id: string;
  content_item_id: string;
  version_num: number;
  body_text: string;
  checksum: string;
  created_by?: string;
  created_at: string;
  poster_file_path?: string;
  poster_asset_id?: string;
  poster_alt_text?: string;
  poster_url?: string;
  is_pdf?: boolean;
  page_count?: number;
}

export interface ContentItem {
  id: string;
  organization_id: string;
  brand_id: string;
  created_by: string;
  title: string;
  channel: string;
  current_version_num: number;
  status: 'draft' | 'submitted' | 'approved' | 'changes_requested' | 'rejected';
  created_at: string;
  updated_at: string;
  latest_version?: ContentVersion;
}

export interface GovernanceFinding {
  id: string;
  governance_run_id: string;
  category: string;
  severity: 'critical' | 'high' | 'warning' | 'info';
  title: string;
  explanation: string;
  text_excerpt?: string;
  matched_rule_id?: string;
  matched_rule_code?: string;
  matched_fact_id?: string;
  matched_fact_key?: string;
  source_citation: string;
  recommended_action: string;
  status: string;
  created_at: string;
  ocr_confidence?: number;
  bounding_box?: any;
  evidence_type?: string;
  page_number?: number;
  source_status?: string;
  enforcement_action?: string;
  is_blocker?: boolean;
  suggestion?: CorrectionSuggestion;
}

export interface CorrectionSuggestion {
  id: string;
  finding_id: string;
  content_item_id: string;
  content_version_id: string;
  source_checksum: string;
  target_type: 'body_text' | 'poster_image' | 'pdf_page';
  page_number?: number;
  rule_id?: string;
  rule_code?: string;
  fact_id?: string;
  fact_key?: string;
  original_text: string;
  proposed_text?: string;
  diff_preview?: string;
  explanation: string;
  evidence_source: string;
  correction_type: string;
  confidence: 'high' | 'medium' | 'manual_review';
  can_auto_apply: boolean;
  status: 'pending' | 'accepted' | 'rejected' | 'stale' | 'applied';
  created_at: string;
  resolved_at?: string;
}

export interface CorrectionSuggestionApplyResponse {
  suggestion: CorrectionSuggestion;
  content_item_id: string;
  new_version_num?: number;
  new_version_id?: string;
  applied_to_text: boolean;
  message: string;
}

export interface GovernanceRun {
  id: string;
  content_version_id: string;
  executed_by?: string;
  overall_status: 'passed' | 'warnings' | 'failed';
  rules_evaluated_count: number;
  facts_evaluated_count: number;
  findings_count: number;
  created_at: string;
  findings: GovernanceFinding[];
}

export interface ApprovalDecision {
  id: string;
  approval_submission_id: string;
  content_version_id: string;
  decided_by: string;
  decider_name?: string;
  decision: 'approved' | 'rejected' | 'changes_requested';
  decision_label: string;
  comments: string;
  created_at: string;
}

export interface ApprovalSubmission {
  id: string;
  content_item_id: string;
  content_item_title: string;
  brand_name: string;
  channel?: string;
  content_version_id: string;
  version_num: number;
  body_text: string;
  checksum: string;
  submitted_by: string;
  submitter_name?: string;
  submission_notes?: string;
  status: 'pending' | 'approved' | 'rejected' | 'changes_requested';
  created_at: string;
  poster_file_path?: string;
  poster_asset_id?: string;
  poster_alt_text?: string;
  poster_url?: string;
  is_pdf?: boolean;
  page_count?: number;
  decisions: ApprovalDecision[];
  governance_run_id?: string;
  governance_status?: 'passed' | 'warnings' | 'failed';
  rules_evaluated_count?: number;
  facts_evaluated_count?: number;
  findings_count?: number;
  critical_findings_count?: number;
  warning_findings_count?: number;
  info_findings_count?: number;
  findings?: GovernanceFinding[];
}

export interface AuditEvent {
  id: string;
  organization_id: string;
  user_id?: string;
  user_name?: string;
  event_type: string;
  entity_type: string;
  entity_id: string;
  summary: string;
  details?: any;
  created_at: string;
}

export interface ImageGovernanceResult {
  passed: boolean;
  dimensions?: string;
  aspect_ratio?: string;
  color_mode?: string;
  findings: string[];
  recommendations: string[];
}

export interface ReviewerFindingDisposition {
  id: string;
  organization_id: string;
  governance_run_id: string;
  finding_id: string;
  rule_id?: string;
  content_item_id?: string;
  content_version_id?: string;
  disposition: 'confirmed_issue' | 'false_positive' | 'guideline_unclear' | 'conflicting_guidelines' | 'insufficient_evidence' | 'other';
  reviewer_id: string;
  reviewer_name?: string;
  explanation: string;
  created_at: string;
}

export interface AnalyticsOverview {
  date_from?: string;
  date_to?: string;
  total_runs: number;
  runs_with_findings_count: number;
  runs_with_findings_pct: number;
  clean_runs_count: number;
  clean_runs_pct: number;
  total_findings: number;
  actionable_findings_count: number;
  actionable_findings_pct: number;
  successful_checks_count: number;
  successful_checks_pct: number;
  unresolved_review_count: number;
  unresolved_review_pct: number;
  findings_by_severity: Record<string, number>;
  findings_by_severity_pct: Record<string, number>;
  actionable_findings_by_severity: Record<string, number>;
  actionable_findings_by_severity_pct: Record<string, number>;
  findings_by_status: Record<string, number>;
  findings_by_category: Record<string, number>;
  runs_over_time: Array<{
    date: string;
    runs_count: number;
    findings_count: number;
    clean_runs_count: number;
  }>;
  data_available: boolean;
}

export interface RepeatedMistakeItem {
  rule_id: string;
  rule_code?: string;
  rule_title: string;
  rule_type: string;
  category: string;
  total_findings: number;
  actionable_findings_count: number;
  successful_checks_count: number;
  unresolved_review_count: number;
  distinct_content_items_count: number;
  distinct_versions_count: number;
  severity_distribution: Record<string, number>;
  channels_distribution: Record<string, number>;
  products_distribution: Record<string, number>;
  recurrent_version_issues_count: number;
  recurrence_trend: 'increasing' | 'decreasing' | 'stable' | 'insufficient_history';
  trend_details?: string;
}

export interface RepeatedMistakesData {
  date_from?: string;
  date_to?: string;
  total_repeated_rules_count: number;
  items: RepeatedMistakeItem[];
  data_available: boolean;
}

export interface AmbiguitySignal {
  signal_type: 'guideline_unclear' | 'conflicting_guidelines' | 'high_false_positive_rate' | 'warning_override_frequency' | 'insufficient_evidence';
  title: string;
  description: string;
  count: number;
  event_count?: number;
  denominator: number;
  percentage: number;
  date_range?: string;
  sample_feedback: string[];
  evidence_source: 'reviewer_disposition' | 'approval_decision';
  distinct_content_items_count?: number;
  distinct_findings_count?: number;
}

export interface RuleAmbiguityReportItem {
  rule_id: string;
  rule_code?: string;
  rule_title: string;
  rule_type: string;
  source_citation?: string;
  ambiguity_level: 'high' | 'medium' | 'low';
  ambiguity_score: number;
  total_dispositions_count: number;
  total_events_count?: number;
  dispositions_breakdown: Record<string, number>;
  effective_dispositions_breakdown?: Record<string, number>;
  distinct_content_items_count: number;
  distinct_findings_count: number;
  evidence_base_size: 'small' | 'moderate' | 'substantial';
  warning_overrides_count: number;
  verified_rule_overrides_count: number;
  content_level_overrides_count: number;
  override_attribution_notes?: string;
  signals: AmbiguitySignal[];
  recommended_action: string;
}

export interface AmbiguityReportData {
  date_from?: string;
  date_to?: string;
  flagged_rules_count: number;
  total_reviewed_rules_count: number;
  criteria_summary: string;
  rules: RuleAmbiguityReportItem[];
  data_available: boolean;
}

