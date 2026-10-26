import {
  User, AuthState, Organization, Member, Brand,
  KnowledgeSource, KnowledgeRule, KnowledgeFact, BrandAsset,
  ContentItem, ContentVersion, GovernanceRun, ApprovalSubmission,
  ApprovalDecision, AuditEvent, ImageGovernanceResult
} from '../types';

const API_BASE = '/api/v1';

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
  async login(email: string, password: string) {
    return this.request<any>('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password })
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

  async addMember(userEmail: string, role: string): Promise<Member> {
    return this.request<Member>('/organizations/members', {
      method: 'POST',
      body: JSON.stringify({ user_email: userEmail, role })
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

  async reviewFact(factId: string, status: string, reviewNotes?: string): Promise<KnowledgeFact> {
    return this.request<KnowledgeFact>(`/knowledge/facts/${factId}/review`, {
      method: 'POST',
      body: JSON.stringify({ status, review_notes: reviewNotes })
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
  async getContentItems(): Promise<ContentItem[]> {
    return this.request<ContentItem[]>('/content');
  }

  async getContentItem(contentId: string): Promise<ContentItem> {
    return this.request<ContentItem>(`/content/${contentId}`);
  }

  async createContentItem(brandId: string, title: string, channel: string, bodyText: string): Promise<ContentItem> {
    return this.request<ContentItem>('/content', {
      method: 'POST',
      body: JSON.stringify({ brand_id: brandId, title, channel, body_text: bodyText })
    });
  }

  async updateContentItem(contentId: string, bodyText: string, title?: string, channel?: string): Promise<ContentItem> {
    return this.request<ContentItem>(`/content/${contentId}`, {
      method: 'PUT',
      body: JSON.stringify({ body_text: bodyText, title, channel })
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
}

export const api = new ApiService();
