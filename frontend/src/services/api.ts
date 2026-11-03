import {
  User, AuthState, Organization, Member, Brand,
  KnowledgeSource, KnowledgeRule, KnowledgeFact, BrandAsset,
  ContentItem, ContentVersion, GovernanceRun, ApprovalSubmission,
  ApprovalDecision, AuditEvent, ImageGovernanceResult,
  AnalyticsOverview, RepeatedMistakesData, AmbiguityReportData, ReviewerFindingDisposition,
  CorrectionSuggestion, CorrectionSuggestionApplyResponse,
  BrandProfile, StagedImportPreview, KnowledgeBaseActivation, OrganizationInvitation, InvitationVerifyData,
  ProductItem, ClaimItem, RequiredDisclosureItem, StagedImportHistoryItem
} from '../types';

let rawBase = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/+$/, '');
if (rawBase.endsWith('/api/v1')) {
  rawBase = rawBase.slice(0, -7);
}
const API_ROOT = rawBase;
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

    let res: Response;
    try {
      res = await fetch(`${API_BASE}${endpoint}`, {
        ...options,
        headers
      });
    } catch (netErr: any) {
      const isFetchError = netErr?.name === 'TypeError' || netErr?.message?.toLowerCase().includes('fetch');
      if (isFetchError) {
        throw new Error(
          `Unable to connect to backend (${API_BASE || 'local server'}). If the service is warming up (e.g. Render free tier cold-start), please wait ~30 seconds and retry.`
        );
      }
      throw netErr;
    }

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

  async getSourceText(sourceId: string): Promise<any> {
    return this.request<any>(`/knowledge/sources/${sourceId}/text`);
  }

  getSourceDownloadUrl(sourceId: string): string {
    const token = this.token || localStorage.getItem('inkloom_token');
    return `${API_BASE}/knowledge/sources/${sourceId}/download${token ? `?token=${encodeURIComponent(token)}` : ''}`;
  }

  // Knowledge Rules
  async createRule(payload: any): Promise<KnowledgeRule> {
    return this.request<KnowledgeRule>('/knowledge/rules', {
      method: 'POST',
      body: JSON.stringify(payload)
    });
  }

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

  async deleteAsset(assetId: string): Promise<any> {
    return this.request(`/knowledge/assets/${assetId}`, {
      method: 'DELETE'
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
    channel: string = 'General',
    bodyText: string = '',
    posterFilePath?: string,
    posterAssetId?: string,
    posterAltText?: string,
    productId?: string
  ): Promise<ContentItem> {
    return this.request<ContentItem>('/content', {
      method: 'POST',
      body: JSON.stringify({
        brand_id: brandId,
        product_id: productId || null,
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
    bodyText: string = '',
    title?: string,
    channel?: string,
    posterFilePath?: string,
    posterAssetId?: string,
    posterAltText?: string,
    productId?: string
  ): Promise<ContentItem> {
    return this.request<ContentItem>(`/content/${contentId}`, {
      method: 'PUT',
      body: JSON.stringify({
        body_text: bodyText,
        title,
        channel,
        product_id: productId !== undefined ? productId : null,
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
  async runGovernanceCheck(contentVersionId: string, productId?: string): Promise<GovernanceRun> {
    const payload: { content_version_id: string; product_id?: string } = {
      content_version_id: contentVersionId
    };
    if (productId) {
      payload.product_id = productId;
    }

    try {
      return await this.request<GovernanceRun>('/governance/run', {
        method: 'POST',
        body: JSON.stringify(payload)
      });
    } catch (err: any) {
      if (err.message && err.message.toLowerCase().includes('unable to connect to backend')) {
        await new Promise((resolve) => setTimeout(resolve, 2000));
        return await this.request<GovernanceRun>('/governance/run', {
          method: 'POST',
          body: JSON.stringify(payload)
        });
      }
      throw err;
    }
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

  // -------------------------------------------------------------------------
  // ROUND 3: BRAND PROFILE, EXCEL STAGING & INVITATIONS
  // -------------------------------------------------------------------------

  getExcelTemplateUrl(templateType: 'product_catalogue' | 'claims_and_disclosures'): string {
    return `${API_BASE}/knowledge/templates/${templateType}`;
  }

  async downloadExcelTemplate(templateType: 'product_catalogue' | 'claims_and_disclosures'): Promise<void> {
    const headers = new Headers();
    if (this.token) {
      headers.set('Authorization', `Bearer ${this.token}`);
    }
    if (this.organizationId) {
      headers.set('X-Organization-Id', this.organizationId);
    }
    const res = await fetch(`${API_BASE}/knowledge/templates/${templateType}`, {
      headers
    });
    if (!res.ok) {
      throw new Error(`Failed to download template (${res.status}): ${res.statusText}`);
    }
    const blob = await res.blob();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${templateType}.xlsx`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    window.URL.revokeObjectURL(url);
  }

  async previewExcelImport(
    importType: 'product_catalogue' | 'claims_and_disclosures',
    file: File,
    idempotencyKey?: string
  ): Promise<StagedImportPreview> {
    const formData = new FormData();
    formData.append('file', file);
    if (idempotencyKey) {
      formData.append('idempotency_key', idempotencyKey);
    }

    return this.request<StagedImportPreview>(`/knowledge/import/${importType}/preview`, {
      method: 'POST',
      body: formData
    });
  }

  async getImportPreview(importId: string): Promise<StagedImportPreview> {
    return this.request<StagedImportPreview>(`/knowledge/import/${importId}/preview`);
  }

  async confirmImport(importId: string): Promise<{ status: string; committed_products?: number; committed_claims?: number; committed_disclosures?: number }> {
    return this.request<{ status: string; committed_products?: number; committed_claims?: number; committed_disclosures?: number }>(`/knowledge/import/${importId}/confirm`, {
      method: 'POST'
    });
  }

  async discardImport(importId: string): Promise<{ status: string }> {
    return this.request<{ status: string }>(`/knowledge/import/${importId}/discard`, {
      method: 'POST'
    });
  }

  async getBrandProfile(): Promise<BrandProfile | null> {
    try {
      return await this.request<BrandProfile>('/knowledge/brand-profile');
    } catch (e: any) {
      if (e.message && e.message.includes('404')) return null;
      throw e;
    }
  }

  async saveBrandProfile(profile: Partial<BrandProfile>): Promise<BrandProfile> {
    return this.request<BrandProfile>('/knowledge/brand-profile', {
      method: 'POST',
      body: JSON.stringify(profile)
    });
  }

  async activateKnowledgeBase(reason?: string): Promise<KnowledgeBaseActivation> {
    return this.request<KnowledgeBaseActivation>('/knowledge/activate', {
      method: 'POST',
      body: JSON.stringify({ activation_reason: reason })
    });
  }

  // Team Invitations
  async getInvitations(orgId: string): Promise<OrganizationInvitation[]> {
    return this.request<OrganizationInvitation[]>(`/organizations/${orgId}/invitations`);
  }

  async createInvitation(
    orgId: string,
    email: string,
    role: string,
    inviteeName?: string
  ): Promise<OrganizationInvitation> {
    return this.request<OrganizationInvitation>(`/organizations/${orgId}/invitations`, {
      method: 'POST',
      body: JSON.stringify({ email, role, invitee_name: inviteeName })
    });
  }

  async resendInvitation(orgId: string, invitationId: string): Promise<OrganizationInvitation> {
    return this.request<OrganizationInvitation>(`/organizations/${orgId}/invitations/${invitationId}/resend`, {
      method: 'POST'
    });
  }

  async revokeInvitation(orgId: string, invitationId: string): Promise<OrganizationInvitation> {
    return this.request<OrganizationInvitation>(`/organizations/${orgId}/invitations/${invitationId}/revoke`, {
      method: 'POST'
    });
  }

  async verifyInvitation(token: string): Promise<InvitationVerifyData> {
    const res = await fetch(`${API_BASE}/invitations/verify?token=${encodeURIComponent(token)}`);
    if (!res.ok) {
      let msg = `Verification failed (${res.status})`;
      try {
        const errJson = await res.json();
        msg = errJson.detail || msg;
      } catch {}
      throw new Error(msg);
    }
    return res.json();
  }

  async acceptInvitation(payload: { token: string; full_name?: string; password?: string }): Promise<any> {
    const res = await fetch(`${API_BASE}/invitations/accept`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    if (!res.ok) {
      let msg = `Acceptance failed (${res.status})`;
      try {
        const errJson = await res.json();
        msg = errJson.detail || msg;
      } catch {}
      throw new Error(msg);
    }
    return res.json();
  }

  // Products, Claims, Disclosures
  async getProducts(): Promise<ProductItem[]> {
    return this.request<ProductItem[]>('/knowledge/products');
  }

  async getClaims(): Promise<ClaimItem[]> {
    return this.request<ClaimItem[]>('/knowledge/claims');
  }

  async getDisclosures(): Promise<RequiredDisclosureItem[]> {
    return this.request<RequiredDisclosureItem[]>('/knowledge/disclosures');
  }

  async getStagedImports(): Promise<StagedImportHistoryItem[]> {
    return this.request<StagedImportHistoryItem[]>('/knowledge/imports');
  }

  // Real-Time In-Editor Assistant (Round 2 Commitment 1)
  async liveCheck(payload: {
    brand_id?: string;
    product_id?: string;
    channel?: string;
    title?: string;
    body_text: string;
  }): Promise<{
    status: string;
    infractions: Array<{
      id: string;
      rule_code?: string;
      category: string;
      severity: string;
      title: string;
      explanation: string;
      matched_text?: string;
      replacement_text?: string;
      can_autofix: boolean;
    }>;
    total_infractions: number;
  }> {
    return this.request('/knowledge/live-check', {
      method: 'POST',
      body: JSON.stringify(payload)
    });
  }

  // Guideline Impact Rescoring (Round 2 Commitment 3)
  async getRescoreJobs(): Promise<any[]> {
    return this.request<any[]>('/knowledge/rescore-jobs');
  }

  async getRescoreJob(jobId: string): Promise<any> {
    return this.request<any>(`/knowledge/rescore-jobs/${jobId}`);
  }

  async triggerRescoreJob(payload?: {
    knowledge_base_version_id?: string;
    scope?: string;
    channel?: string;
  }): Promise<any> {
    return this.request('/knowledge/rescore-trigger', {
      method: 'POST',
      body: JSON.stringify(payload || {})
    });
  }

  async getKnowledgeBaseVersions(): Promise<any[]> {
    return this.request<any[]>('/knowledge/versions');
  }
}

export const api = new ApiService();

