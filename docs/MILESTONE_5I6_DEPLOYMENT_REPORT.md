# Milestone 5I.6 — Safe Deployment Audit & Execution Report

**Project:** Inkloom.AI Brand Governance & Content Integrity Platform  
**Workspace:** `E:\CodeStar30`  
**Frontend Host:** Firebase Hosting (Project: `ad-governance`, Live URL: `https://ad-governance.web.app`)  
**Backend Host:** Render Free Web Service (Service URL: `https://inkloom-backend-6k9u.onrender.com`)  
**Database:** Supabase Managed PostgreSQL (`db.qwvqifqnyurlqewkrsiw.supabase.co`)  
**Persistent Storage:** Supabase Storage Private Bucket (`inkloom-private-assets`)  
**Current Milestone Status:** `DEPLOYMENT COMPLETE — SMOKE TESTS PASSED`

---

## 1. Executive Summary

Milestone 5I.6 completes the hosted deployment of Inkloom.AI without billable infrastructure dependencies. The application is live and accessible at:

- **Frontend (Firebase Hosting):** [`https://ad-governance.web.app`](https://ad-governance.web.app) (Alias: `https://ad-governance.firebaseapp.com`)
- **Backend (Render Web Service):** [`https://inkloom-backend-6k9u.onrender.com`](https://inkloom-backend-6k9u.onrender.com)
- **Database (Supabase PostgreSQL):** Revision `c3d4e5f6a7b8` (Head)
- **Object Storage (Supabase Storage):** `inkloom-private-assets` (Private bucket)

All phases (Pre-Deployment Audit, Render Backend Activation, Firebase Frontend Deployment, and Live Acceptance Smoke Verification) have passed with zero security defects, zero credential leaks, and complete tenant isolation.

---

## 2. Infrastructure & Service Topology

```
┌────────────────────────────────────────────────────────────────────────┐
│                        USER BROWSER / CLIENT                          │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
           ┌────────────────────────┴────────────────────────┐
           │ HTTPS Assets & SPA                              │ HTTPS API Requests (CORS)
           ▼                                                 ▼
┌──────────────────────────────┐                  ┌──────────────────────────────┐
│       FIREBASE HOSTING       │                  │       RENDER WEB SERVICE     │
│   ad-governance.web.app      │                  │ inkloom-backend-6k9u.onrender│
│  - React 19 + Vite 8 SPA     │                  │  - FastAPI + Python 3.12.10  │
│  - Static CDN distribution   │                  │  - RapidOCR + PyMuPDF        │
│  - SPA rewrites to index.html│                  │  - In-memory rate limiting   │
└──────────────────────────────┘                  └──────┬────────────────┬──────┘
                                                         │                │
                                  Direct SQL (Alembic)   │                │ S3 REST API
                                                         ▼                ▼
                                  ┌─────────────────────────┐  ┌─────────────────────────┐
                                  │   SUPABASE POSTGRESQL   │  │    SUPABASE STORAGE     │
                                  │ db.qwvqifqnyurlqewkrsiw │  │  inkloom-private-assets │
                                  │ 19 normalized tables    │  │  Strictly private       │
                                  │ Head: c3d4e5f6a7b8      │  │  Tenant scoped paths    │
                                  └─────────────────────────┘  └─────────────────────────┘
```

---

## 3. Phase A — Pre-Deployment Audit Results

### 3.1 Credential & Secret Hygiene
- **`.env` Exclusion:** Verified that `backend/.env` is completely excluded via `.gitignore` and has never been tracked, staged, or committed to Git.
- **Leak Scans:** Scanned all tracked files, frontend distribution bundles, and commit history for sensitive tokens (`Keerthi%26`, `y7oY_`, `SECRET_KEY`, `gemini`). **Zero matches found.**
- **Safe Templates:** `backend/.env.example` verified to contain purely placeholder strings.

### 3.2 Database & Migration Integrity
- **PostgreSQL Connection:** Connected directly to `db.qwvqifqnyurlqewkrsiw.supabase.co:5432/postgres`.
- **Alembic Revision:** Current database head is `c3d4e5f6a7b8` (`create_revoked_tokens`).
- **Pending Migrations:** 0. No schema changes, table drops, or re-seeding required.

### 3.3 Dependency Manifest Hardening
During initial container startup on Render, three missing runtime packages were diagnosed and added to [`backend/requirements.txt`](file:///e:/CodeStar30/backend/requirements.txt):
1. `psycopg[binary]>=3.2,<4`: Resolves Psycopg 3 dialect (`postgresql+psycopg://`) without requiring host-level libpq packages.
2. `email-validator>=2.0,<3`: Required by Pydantic v2 for `EmailStr` field validation in `app.schemas.auth`.
3. `google-genai>=2.11.0,<3`: Official Google Gen AI Python SDK used by `app.services.gemini_extractor`.

An AST audit across all 44 Python modules in `backend/app/` verified zero remaining missing dependencies.

---

## 4. Phase B — Render Backend Verification

### 4.1 Service Health
- **Endpoint:** `GET https://inkloom-backend-6k9u.onrender.com/health`
- **HTTP Status:** `200 OK`
- **Payload:**
  ```json
  {
    "status": "healthy",
    "service": "Inkloom AI",
    "version": "1.0.0",
    "environment": "production",
    "database_engine": "postgresql"
  }
  ```

### 4.2 Production Security Guardrails
- `ALLOW_DEV_LOGIN=False`: Enforced. Dev login shortcuts rejected with HTTP 403.
- `DEBUG=False`: Enforced. Unhandled exceptions return generic sanitized JSON errors (`{"detail": "Internal server error. Incident has been recorded for review."}`).
- `docs_url=None`, `redoc_url=None`: Swagger and OpenAPI documentation disabled in production.

### 4.3 CORS Configuration
Verified via preflight `OPTIONS` requests:
- Allowed Origin `https://ad-governance.web.app`: **Status 200**, `Access-Control-Allow-Credentials: true`, headers `authorization,content-type,x-organization-id` accepted.
- Allowed Origin `https://ad-governance.firebaseapp.com`: **Status 200**, `Access-Control-Allow-Credentials: true`.
- Arbitrary Origin `https://malicious-site.example.com`: **Status 400**, rejected without access headers. Wildcard CORS (`*`) is strictly blocked.

---

## 5. Phase C — Firebase Frontend Build & Deployment

### 5.1 Dynamic API Base URL Configuration
[`frontend/src/services/api.ts`](file:///e:/CodeStar30/frontend/src/services/api.ts) was updated with a resilient URL resolution strategy:
```typescript
let rawBase = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/+$/, '');
if (rawBase.endsWith('/api/v1')) {
  rawBase = rawBase.slice(0, -7);
}
const API_ROOT = rawBase;
const API_BASE = `${API_ROOT}/api/v1`;
```
- Local development fallback: Defaults to `/api/v1` via Vite proxy when `VITE_API_BASE_URL` is omitted.
- Production build: `frontend/.env.production` sets `VITE_API_BASE_URL=https://inkloom-backend-6k9u.onrender.com`.

### 5.2 Build & Bundle Inspection
- **Test Command:** `npm run test` (Vitest: 3 test files, 9 tests passed in 1.76s).
- **Build Command:** `npm run build` (`tsc -b && vite build` completed in 357ms).
- **Bundle Verification:**
  - Embedded API Target: Confirmed string `https://inkloom-backend-6k9u.onrender.com` present in JS bundle.
  - Secret Leak Audit: Confirmed zero database passwords, secret keys, or service-role keys in bundle.

### 5.3 Hosting Deployment
- **Command:** `firebase deploy --only hosting --project ad-governance --non-interactive`
- **Output:**
  ```
  === Deploying to 'ad-governance'...
  i  deploying hosting
  i  hosting[ad-governance]: beginning deploy...
  i  hosting[ad-governance]: found 6 files in frontend/dist
  +  hosting[ad-governance]: file upload complete
  +  hosting[ad-governance]: version finalized
  +  hosting[ad-governance]: release complete
  Deploy complete!
  Hosting URL: https://ad-governance.web.app
  ```
- **SPA Routing:** Verified that all paths (`/login`, `/content`, `/knowledge`, `/approvals`, `/analytics`, `/onboarding`) return `index.html` with HTTP 200.

---

## 6. Phase D — Live Acceptance Smoke Verification

A comprehensive 12-point automated verification script (`backend/scratch/live_hosted_smoke_test.py`) was executed against the live Render and Supabase services:

| Step | Test Objective | Result | Verification Details |
| :---: | :--- | :---: | :--- |
| **1** | Admin Authentication | **PASSED** | Logged in as `admin@freshsip.demo` via `POST /api/v1/auth/login`. Received JWT access token for Alice Administrator (`org_admin`). |
| **2** | Rule Retrieval | **PASSED** | Retrieved 29 active governance rules from live PostgreSQL database (`GET /api/v1/knowledge/rules`). |
| **3** | Content Item Indexing | **PASSED** | Retrieved existing organization content drafts (`GET /api/v1/content`). |
| **4** | Governance Analytics | **PASSED** | Verified analytics calculation (`GET /api/v1/analytics/overview`). |
| **5** | Creator Authentication | **PASSED** | Logged in as `creator@freshsip.demo` (`content_creator`). Verified brand resolution for Freshsip (`GET /api/v1/brands`). |
| **6** | Remote Storage Upload | **PASSED** | Uploaded synthetic PNG asset via `POST /api/v1/content/upload-poster`. Stored in Supabase Storage at `242a35c5-8f93-4bf3-a23b-3787838c2449/posters/smoke_ec89796f.png`. |
| **7** | Content Draft Creation | **PASSED** | Created draft content item referencing remote poster key (`POST /api/v1/content`). Generated draft `98c11f07-232e-4300-9011-e4503184f290` (v1). |
| **8** | Remote Storage Retrieval | **PASSED** | Streamed poster image bytes via `GET /api/v1/content/versions/{id}/poster`. Confirmed 100% byte-for-byte size equality from Supabase Storage through Render. |
| **9** | Tenant Isolation | **PASSED** | Attempted to access Solis Botanical Brews data using Freshsip creator token. Request strictly rejected with **HTTP 403 Forbidden**. |
| **10** | Compensating Cleanup | **PASSED** | Safely deleted synthetic smoke draft and audit records from database. Existing demo data completely untouched. |
| **11** | Token Revocation | **PASSED** | Logged out via `POST /api/v1/auth/logout`. Token registered in `revoked_tokens` table. |
| **12** | Revocation Enforcement | **PASSED** | Subsequent request with revoked token rejected with **HTTP 401 Unauthorized**. |

---

## 7. Operational Trade-Offs (Demo Tier)

1. **Cold Starts:** Render Free spins down after 15 minutes of inactivity. The initial wake-up request takes ~50 seconds; subsequent requests respond in under 50ms.
2. **Ephemeral Disk Durability:** Local `/tmp` and cache directories are wiped upon container restart. All persistent assets (PDF manuals, posters, guidelines) reside durably in private Supabase Storage, and preview PNGs are rebuilt on demand.
3. **In-Memory Rate Limiting:** The failed-login brute-force counter resets when the container restarts. Password hashing (bcrypt) and token revocation (PostgreSQL) remain durable.
4. **Memory Ceiling:** Peak RSS memory under active OCR and multi-page PDF rendering is 248.81 MB, operating safely within Render Free's 512 MB limit (51.4% safety margin).

---

## 8. Summary of Commits

| Commit Hash | Description |
| :--- | :--- |
| [`9f00b33`](https://github.com/KSKeerthivasan/brand-governance-platform/commit/9f00b33) | `feat: complete Milestones 1-5I.5 with Supabase private storage adapter, live verification, and render deployment blueprint` |
| [`aae3d67`](https://github.com/KSKeerthivasan/brand-governance-platform/commit/aae3d67) | `fix(backend): add psycopg[binary] dependency for psycopg 3 driver compatibility on Render` |
| [`3851661`](https://github.com/KSKeerthivasan/brand-governance-platform/commit/3851661) | `fix(backend): add email-validator dependency for Pydantic EmailStr validation` |
| [`7f6f5dc`](https://github.com/KSKeerthivasan/brand-governance-platform/commit/7f6f5dc) | `fix(backend): add google-genai dependency for Gemini extraction service` |

---

## 9. Final Milestone Conclusion

Inkloom.AI is fully deployed, validated, and operational under a 100% zero-billing architecture:
- **Web App:** [`https://ad-governance.web.app`](https://ad-governance.web.app)
- **API Backend:** [`https://inkloom-backend-6k9u.onrender.com`](https://inkloom-backend-6k9u.onrender.com)
- **Status:** **`DEPLOYMENT COMPLETE — SMOKE TESTS PASSED`**
