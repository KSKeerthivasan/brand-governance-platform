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
  severity: 'critical' | 'warning' | 'info';
  title: string;
  explanation: string;
  text_excerpt?: string;
  matched_rule_id?: string;
  matched_fact_id?: string;
  source_citation: string;
  recommended_action: string;
  status: string;
  created_at: string;
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
  content_version_id: string;
  version_num: number;
  body_text: string;
  checksum: string;
  submitted_by: string;
  submitter_name?: string;
  submission_notes?: string;
  status: 'pending' | 'approved' | 'rejected' | 'changes_requested';
  created_at: string;
  decisions: ApprovalDecision[];
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
