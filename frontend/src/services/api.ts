import {
  User, AuthState, Organization, Member, Brand,
  KnowledgeSource, KnowledgeRule, KnowledgeFact, BrandAsset,
  ContentItem, ContentVersion, GovernanceRun, ApprovalSubmission,
  ApprovalDecision, AuditEvent, ImageGovernanceResult,
  AnalyticsOverview, RepeatedMistakesData, AmbiguityReportData, ReviewerFindingDisposition,
  CorrectionSuggestion, CorrectionSuggestionApplyResponse
} from '../types';

const API_ROOT = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/+$/, '');
const API_BASE = `${API_ROOT}/api/v1`;

class ApiService {
  private token: string | null = null;
  private organizationId: string | null = null;

  setAuth(token: string | null, orgId: string | null) {
    this.token = token;
    this.organizationId = orgId;
    if (token) {
      localStorage.setItem('inkloom_token', token);
    } else {
      localStorage.removeItem('inkloom_token');
    }
    if (orgId) {
      localStorage.setItem('inkloom_org_id', orgId);
    } else {
      localStorage.removeItem('inkloom_org_id');
    }
  }

  initFromStorage() {
    this.token = localStorage.getItem('inkloom_token');
    this.organizationId = localStorage.getItem('inkloom_org_id');
  }

  private async request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
    const headers = new Headers(options.headers || {});
    if (this.token) {
      headers.set('Authorization', `Bearer ${this.token}`);
    }
    if (this.organizationId) {
      headers.set('X-Organization-Id', this.organizationId);
    }
    if (!headers.has('Content-Type') && !(options.body instanceof FormData)) {
      headers.set('Content-Type', 'application/json');
    }

    const res = await fetch(`${API_BASE}${endpoint}`, {
      ...options,
      headers
    });

    if (!res.ok) {
      let errorMsg = `Request failed (${res.status})`;
      try {
        const errJson = await res.json();
        errorMsg = errJson.detail || errorMsg;
      } catch {}
      throw new Error(errorMsg);
    }

    return res.json();
  }

  // Auth
  async login(email: string, password: string, organizationId?: string, organizationSlug?: string) {
    return this.request<any>('/auth/login', {
      method: 'POST',
      body: JSON.stringify({
        email,
        password,
        organization_id: organizationId,
        organization_slug: organizationSlug
      })
    });
  }

  async switchOrg(organizationId?: string, organizationSlug?: string) {
    return this.request<any>('/auth/switch-org', {
      method: 'POST',
      body: JSON.stringify({
        organization_id: organizationId,
        organization_slug: organizationSlug
      })
    });
  }

  async devLogin(role: string, organizationSlug: string = 'freshsip') {
    return this.request<any>('/auth/dev-login', {
      method: 'POST',
      body: JSON.stringify({ role, organization_slug: organizationSlug })
    });
  }

  async getMe() {
    return this.request<any>('/auth/me');
  }

  async logout() {
    try {
      await this.request<any>('/auth/logout', {
        method: 'POST'
      });
    } catch (err) {
      console.warn('Server logout notice:', err);
    } finally {
      this.setAuth(null, null);
    }
  }

  // Organizations & Members
  async onboardOrganization(payload: {
    organization_name: string;
    organization_slug: string;
    brand_name: string;
    brand_description?: string;
    admin_full_name: string;
    admin_email: string;
    admin_password: string;
  }) {
    return this.request<any>('/organizations', {
      method: 'POST',
      body: JSON.stringify(payload)
    });
  }

  async getCurrentOrg(): Promise<Organization> {
    return this.request<Organization>('/organizations/current');
  }

  async getMembers(): Promise<Member[]> {
    return this.request<Member[]>('/organizations/members');
  }

  async addMember(payload: { user_email: string; role: string; full_name?: string; password?: string }): Promise<Member> {
    return this.request<Member>('/organizations/members', {
      method: 'POST',
      body: JSON.stringify(payload)
    });
  }

  // Brands
  async getBrands(): Promise<Brand[]> {
    return this.request<Brand[]>('/brands');
  }

  // Knowledge Sources & Upload
  async uploadKnowledge(formData: FormData): Promise<KnowledgeSource> {
    return this.request<KnowledgeSource>('/knowledge/upload', {
      method: 'POST',
      body: formData
    });
  }

  async getKnowledgeSources(): Promise<KnowledgeSource[]> {
    return this.request<KnowledgeSource[]>('/knowledge/sources');
  }

  // Knowledge Rules
  async getRules(statusFilter?: string): Promise<KnowledgeRule[]> {
    const q = statusFilter ? `?status_filter=${statusFilter}` : '';
    return this.request<KnowledgeRule[]>(`/knowledge/rules${q}`);
  }

  async updateRule(ruleId: string, payload: any): Promise<KnowledgeRule> {
    return this.request<KnowledgeRule>(`/knowledge/rules/${ruleId}`, {
      method: 'PUT',
      body: JSON.stringify(payload)
    });
  }

  async reviewRule(ruleId: string, status: string, reviewNotes?: string): Promise<KnowledgeRule> {
    return this.request<KnowledgeRule>(`/knowledge/rules/${ruleId}/review`, {
      method: 'POST',
      body: JSON.stringify({ status, review_notes: reviewNotes })
    });
  }

  // Knowledge Facts
  async getFacts(statusFilter?: string): Promise<KnowledgeFact[]> {
    const q = statusFilter ? `?status_filter=${statusFilter}` : '';
    return this.request<KnowledgeFact[]>(`/knowledge/facts${q}`);
  }

  async updateFact(factId: string, payload: any): Promise<KnowledgeFact> {
    return this.request<KnowledgeFact>(`/knowledge/facts/${factId}`, {
      method: 'PUT',
      body: JSON.stringify(payload)
    });
  }

  async reviewFact(factId: string, status: string, reviewNotes?: string): Promise<KnowledgeFact> {
    return this.request<KnowledgeFact>(`/knowledge/facts/${factId}/review`, {
      method: 'POST',
      body: JSON.stringify({ status, review_notes: reviewNotes })
    });
  }

  async reprocessSource(sourceId: string): Promise<KnowledgeSource> {
    return this.request<KnowledgeSource>(`/knowledge/sources/${sourceId}/reprocess`, {
      method: 'POST'
    });
  }

  // Brand Assets
  async getAssets(): Promise<BrandAsset[]> {
    return this.request<BrandAsset[]>('/knowledge/assets');
  }

  async reviewAsset(assetId: string, status: string): Promise<BrandAsset> {
    return this.request<BrandAsset>(`/knowledge/assets/${assetId}/review`, {
      method: 'POST',
      body: JSON.stringify({ status })
    });
  }

  // Content Items
  async uploadPoster(file: File): Promise<{
    file_path: string;
    filename: string;
    width: number;
    height: number;
    color_mode: string;
    format: string;
    size_bytes: number;
    page_count?: number;
    pages?: Array<{
      page_number: number;
      width_pt: number;
      height_pt: number;
      width_px: number;
      height_px: number;
      orientation: string;
      aspect_ratio: string;
    }>;
  }> {
    const formData = new FormData();
    formData.append('file', file);
    return this.request('/content/upload-poster', {
      method: 'POST',
      body: formData
    });
  }

  getPosterUrl(versionId: string, page?: number): string {
    const token = this.token || localStorage.getItem('inkloom_token');
    const params = new URLSearchParams();
    if (token) params.set('token', token);
    if (page !== undefined && page !== null) {
      params.set('page', String(page));
      params.set('render', 'true');
    }
    const qs = params.toString();
    return `${API_BASE}/content/versions/${versionId}/poster${qs ? `?${qs}` : ''}`;
  }

  async getPdfPages(versionId: string): Promise<{
    is_pdf: boolean;
    page_count: number;
    pages: Array<{
      page_number: number;
      width_pt: number;
      height_pt: number;
      width_px: number;
      height_px: number;
      orientation: string;
      aspect_ratio: string;
      image_url: string;
    }>;
  }> {
    return this.request(`/content/versions/${versionId}/pdf-pages`);
  }

  getAssetFileUrl(assetId: string): string {
    const token = this.token || localStorage.getItem('inkloom_token');
    return `${API_BASE}/knowledge/assets/${assetId}/file${token ? `?token=${encodeURIComponent(token)}` : ''}`;
  }

  async getContentItems(): Promise<ContentItem[]> {
    return this.request<ContentItem[]>('/content');
  }

  async getContentItem(contentId: string): Promise<ContentItem> {
    return this.request<ContentItem>(`/content/${contentId}`);
  }

  async createContentItem(
    brandId: string,
    title: string,
    channel: string,
    bodyText: string,
    posterFilePath?: string,
    posterAssetId?: string,
    posterAltText?: string
  ): Promise<ContentItem> {
    return this.request<ContentItem>('/content', {
      method: 'POST',
      body: JSON.stringify({
        brand_id: brandId,
        title,
        channel,
        body_text: bodyText,
        poster_file_path: posterFilePath,
        poster_asset_id: posterAssetId,
        poster_alt_text: posterAltText
      })
    });
  }

  async updateContentItem(
    contentId: string,
    bodyText: string,
    title?: string,
    channel?: string,
    posterFilePath?: string,
    posterAssetId?: string,
    posterAltText?: string
  ): Promise<ContentItem> {
    return this.request<ContentItem>(`/content/${contentId}`, {
      method: 'PUT',
      body: JSON.stringify({
        body_text: bodyText,
        title,
        channel,
        poster_file_path: posterFilePath,
        poster_asset_id: posterAssetId,
        poster_alt_text: posterAltText
      })
    });
  }

  async getContentVersions(contentId: string): Promise<ContentVersion[]> {
    return this.request<ContentVersion[]>(`/content/${contentId}/versions`);
  }

  // Governance Checks
  async runGovernanceCheck(contentVersionId: string): Promise<GovernanceRun> {
    return this.request<GovernanceRun>('/governance/run', {
      method: 'POST',
      body: JSON.stringify({ content_version_id: contentVersionId })
    });
  }

  async getLatestGovernanceRun(versionId: string): Promise<GovernanceRun> {
    return this.request<GovernanceRun>(`/governance/runs/${versionId}/latest`);
  }

  async checkImageGovernance(payload: { asset_id?: string; image_url?: string; channel?: string; alt_text?: string }): Promise<ImageGovernanceResult> {
    return this.request<ImageGovernanceResult>('/governance/image-check', {
      method: 'POST',
      body: JSON.stringify(payload)
    });
  }

  // Milestone 5D: Context-Preserving Correction Suggestions
  async getSuggestions(versionId: string): Promise<CorrectionSuggestion[]> {
    return this.request<CorrectionSuggestion[]>(`/governance/runs/${versionId}/suggestions`);
  }

  async acceptSuggestion(suggestionId: string): Promise<CorrectionSuggestionApplyResponse> {
    return this.request<CorrectionSuggestionApplyResponse>(`/governance/suggestions/${suggestionId}/accept`, {
      method: 'POST'
    });
  }

  async rejectSuggestion(suggestionId: string): Promise<CorrectionSuggestion> {
    return this.request<CorrectionSuggestion>(`/governance/suggestions/${suggestionId}/reject`, {
      method: 'POST'
    });
  }

  async applyCustomSuggestion(suggestionId: string, customText: string): Promise<CorrectionSuggestionApplyResponse> {
    return this.request<CorrectionSuggestionApplyResponse>(`/governance/suggestions/${suggestionId}/apply-custom`, {
      method: 'POST',
      body: JSON.stringify({ custom_text: customText })
    });
  }

  // Approvals
  async submitForApproval(contentItemId: string, contentVersionId: string, submissionNotes?: string): Promise<ApprovalSubmission> {
    return this.request<ApprovalSubmission>('/approvals/submit', {
      method: 'POST',
      body: JSON.stringify({ content_item_id: contentItemId, content_version_id: contentVersionId, submission_notes: submissionNotes })
    });
  }

  async getApprovalQueue(statusFilter?: string): Promise<ApprovalSubmission[]> {
    const q = statusFilter ? `?status_filter=${statusFilter}` : '';
    return this.request<ApprovalSubmission[]>(`/approvals/queue${q}`);
  }

  async decideApproval(submissionId: string, decision: string, comments: string): Promise<ApprovalDecision> {
    return this.request<ApprovalDecision>(`/approvals/submissions/${submissionId}/decide`, {
      method: 'POST',
      body: JSON.stringify({ decision, comments })
    });
  }

  // Audit Events
  async getAuditEvents(limit: number = 50, eventType?: string): Promise<AuditEvent[]> {
    let url = `/audit?limit=${limit}`;
    if (eventType) url += `&event_type=${eventType}`;
    return this.request<AuditEvent[]>(url);
  }

  // Analytics & Ambiguity Signals (Milestone 5B)
  async getAnalyticsOverview(params?: Record<string, string>): Promise<AnalyticsOverview> {
    const qs = params ? '?' + new URLSearchParams(params).toString() : '';
    return this.request<AnalyticsOverview>(`/analytics/overview${qs}`);
  }

  async getRepeatedMistakes(params?: Record<string, string>): Promise<RepeatedMistakesData> {
    const qs = params ? '?' + new URLSearchParams(params).toString() : '';
    return this.request<RepeatedMistakesData>(`/analytics/repeated-mistakes${qs}`);
  }

  async getAmbiguitySignals(params?: Record<string, string>): Promise<AmbiguityReportData> {
    const qs = params ? '?' + new URLSearchParams(params).toString() : '';
    return this.request<AmbiguityReportData>(`/analytics/ambiguity-signals${qs}`);
  }

  async submitFindingDisposition(findingId: string, disposition: string, explanation: string): Promise<ReviewerFindingDisposition> {
    return this.request<ReviewerFindingDisposition>(`/analytics/findings/${findingId}/feedback`, {
      method: 'POST',
      body: JSON.stringify({ disposition, explanation })
    });
  }

  async getFindingDispositions(findingId: string): Promise<ReviewerFindingDisposition[]> {
    return this.request<ReviewerFindingDisposition[]>(`/analytics/findings/${findingId}/feedback`);
  }
}

export const api = new ApiService();

