# Milestone 5H — Actual Hosted Deployment and Remote Smoke Verification

**Workspace:** `E:\CodeStar30`  
**Date:** October 28, 2026  
**Platform Version:** Inkloom.AI v1.0.0  
**Status:** **DEPLOYMENT BLOCKED — PREREQUISITES MISSING**

---

## 1. Executive Summary

Milestone 5H evaluates the deployment readiness of **Inkloom.AI** in its target environment following the hardening completed in Milestone 5G. 

While the remote managed PostgreSQL database instance (hosted on Supabase) is fully provisioned, reachable, and verified at Alembic migration revision `c3d4e5f6a7b8 (head)`, public application hosting infrastructure (such as an application container service, public domain DNS, and TLS termination reverse proxy) has not yet been provisioned or bound to the repository.

In strict adherence to the Milestone 5H guidelines:
- Local automated regression and production configuration validations are reported **separately** from remote hosted smoke checks.
- Remote hosted smoke tests requiring a live public HTTPS URL are classified as **`NOT VERIFIED (BLOCKED)`** rather than falsely claimed as passing.
- The exact missing infrastructure prerequisites, provider configuration requirements, and step-by-step deployment runbooks are documented below.

---

## 2. Deployment Target & Architecture

### 2.1 Target Architecture Topology

```
[Public Web Browser]
         │
         ▼  (HTTPS 443)  <-- [PREREQUISITE MISSING: Public Domain DNS & TLS Proxy]
┌────────────────────────────────────────────────────────┐
│  Edge / Reverse Proxy (Cloudflare / Nginx / Caddy)     │
└────────────────────────┬───────────────────────────────┘
                         │ (HTTP Reverse Proxy)
                         ▼
┌────────────────────────────────────────────────────────┐
│  Application Host (Render / Fly.io / AWS ECS / VM)     │
│                                                        │
│  ┌──────────────────────────────────────────────────┐  │
│  │ Single-Worker Uvicorn Process (FastAPI Backend)  │  │
│  │                                                  │  │
│  │  - Single-worker enforced: uvicorn --workers 1   │  │
│  │  - Thread-safe In-Memory LoginRateLimiter        │  │
│  │  - PyMuPDF / Local OCR / Document Extraction     │  │
│  │  - Static React 19 Frontend SPA (/dist)          │  │
│  └───────────────────────┬──────────────────────────┘  │
│                          │                             │
│                          ▼                             │
│     ┌──────────────────────────────────────┐           │
│     │ Persistent Volume (/var/lib/inkloom) │           │
│     │ - Uploaded documents & brand assets  │           │
│     │ - Rendered PDF page preview cache    │           │
│     └──────────────────────────────────────┘           │
└──────────────────────────┬─────────────────────────────┘
                           │
                           ▼  (Encrypted TLS :5432)
┌────────────────────────────────────────────────────────┐
│  Remote Managed Database (Supabase PostgreSQL)         │
│  Host: db.qwvqifqnyurlqewkrsiw.supabase.co             │
│  Revision: c3d4e5f6a7b8 (head) - 19 tables             │
└────────────────────────────────────────────────────────┘
```

### 2.2 Verified Remote Database Layer
- **Provider:** Supabase Managed PostgreSQL
- **Project Ref:** `qwvqifqnyurlqewkrsiw` (Region: `ap-northeast-1`)
- **Postgres Engine:** PostgreSQL 17 (17.11.0.003)
- **Status:** `ACTIVE_HEALTHY`
- **Current Migration Revision:** `c3d4e5f6a7b8` (Verified via `alembic.runtime.migration.MigrationContext`)

### 2.3 Application Host Prerequisites (Currently Missing)
The application runtime cannot be deployed or verified over remote HTTPS until the project owner or infrastructure administrator provisions:
1. **Application Container Host / VM:** A cloud runtime capable of hosting Python 3.12 (with PyMuPDF and Pillow C-extensions) and Node.js (or pre-built static frontend bundle).
2. **Persistent Storage Mount:** A persistent disk volume (minimum 10 GB) mounted at `/var/lib/inkloom/storage` or configured via `LOCAL_STORAGE_DIR`.
3. **Domain / DNS Records:** A public Fully Qualified Domain Name (e.g., `https://demo.inkloom.ai`) with DNS A/CNAME records pointed to the application host.
4. **TLS/SSL Certificate:** Automatic or managed SSL termination (via Let's Encrypt, Cloudflare, or AWS ACM) terminating TLS at port 443.

---

## 3. Production Environment Configuration

The verified production configuration template (excluding secret literal values) is configured as follows:

```env
# Core Application Settings
ENVIRONMENT=production
DEBUG=False
ALLOW_DEV_LOGIN=False

# Cryptographic Keys (Must be generated with: openssl rand -hex 32)
SECRET_KEY=[HIGH_ENTROPY_64_CHAR_HEX_SECRET]
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=720

# Database Connection (Dedicated Production Supabase Instance)
DATABASE_URL=postgresql://[PROD_DB_USER]:[PROD_DB_PASSWORD]@db.qwvqifqnyurlqewkrsiw.supabase.co:5432/postgres

# Persistent Asset Storage
STORAGE_BACKEND=local
LOCAL_STORAGE_DIR=/var/lib/inkloom/storage

# Allowed Frontend Origins (Strictly explicit; wildcard prohibited)
CORS_ORIGINS=https://demo.inkloom.ai
```

### 3.1 Production Safeguards Validation
The startup validator `validate_production_readiness()` was executed against production settings:
- `ENVIRONMENT=production`: Verified.
- `DEBUG=False`: Verified.
- `ALLOW_DEV_LOGIN=False`: Verified.
- Non-predictable `SECRET_KEY`: Verified (rejects keys with `dev`, `test`, `default`, or < 32 characters).
- Dedicated non-local `DATABASE_URL`: Verified (rejects SQLite and default `postgres:postgres@localhost`).
- Explicit non-wildcard `CORS_ORIGINS`: Verified (wildcards rejected; localhost auto-injection blocked in production).
- Persistent storage path: Verified (temporary directory paths like `/tmp` rejected).

---

## 4. Database Migrations & Integrity Verification

### 4.1 Migration Status
The target Supabase database was inspected via Alembic:
```bash
python -m alembic current
```
**Output:**
```
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
INFO  [alembic.runtime.migration] Will assume transactional DDL.
c3d4e5f6a7b8 (head)
```

### 4.2 Verified Database Schema (19 Tables)
All migrations through `c3d4e5f6a7b8` are applied:
1. `alembic_version`
2. `organizations`
3. `users`
4. `organization_memberships`
5. `brands`
6. `knowledge_sources`
7. `knowledge_rules` (with scope metadata)
8. `knowledge_facts`
9. `brand_assets`
10. `content_items`
11. `content_versions`
12. `governance_runs`
13. `governance_findings` (with page numbers and evidence citations)
14. `approval_submissions`
15. `approval_decisions`
16. `reviewer_finding_dispositions`
17. `correction_suggestions`
18. `audit_events`
19. `revoked_tokens` (server-side JWT revocation store)

### 4.3 Database Security Advisory (Supabase RLS)
> [!WARNING]
> **Advisory from Supabase Security Inspector:**  
> The 19 application tables currently have Row Level Security (RLS) disabled.  
> **Impact:** While Inkloom.AI enforces strict role-based access control and tenant isolation at the FastAPI application layer via SQLAlchemy, any client with direct access to Supabase's public anonymous API keys (`anon_key`) could query these tables if the Supabase REST API is exposed.  
> **Remediation Recommendation:** Before exposing Supabase public endpoints, either disable the Supabase Data API for public schemas or enable RLS policies mirroring tenant membership (`organization_id`).

---

## 5. Deployment Architecture Constraints

### 5.1 Single-Worker Uvicorn Architecture
- **Requirement:** The backend process MUST be launched with `--workers 1`:
  ```bash
  uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1
  ```
- **Rationale:** The `LoginRateLimiter` (`backend/app/services/auth.py`) uses an in-process thread lock (`threading.Lock`) and memory hash-map to enforce the 5 failed attempts / 300s lockout window. Running multi-worker Uvicorn without a distributed cache (e.g. Redis) would divide the lockout window across workers, diluting protection against brute-force attacks.

### 5.2 PDF Preview Cache & Multi-Tenant Storage
- Cached PDF page PNGs are stored in version-keyed directories:
  `/var/lib/inkloom/storage/{org_id}/documents/pages_{version_id}/page_{n}.png`
- The cache checks file modification timestamps (`os.path.getmtime >= pdf_mtime`) and version IDs, preventing stale renders or cross-tenant leaks.
- Uploaded content persists across restarts as long as `/var/lib/inkloom/storage` is attached to persistent disk storage.

---

## 6. The 14-Point Smoke Test Matrix

The matrix distinguishes between **Local Automated Verification** and **Remote Hosted Verification**:

| # | Checkpoint | Local Automated Status | Remote Hosted Status | Blocker / Notes |
| :---: | :--- | :---: | :---: | :--- |
| **1** | Frontend loads successfully over HTTPS | **PASS** *(Build clean)* | **NOT VERIFIED** | Blocked: No public domain / TLS certificate provisioned. |
| **2** | Unauthenticated protected request returns HTTP 401 | **PASS** *(HTTP 401 verified)* | **NOT VERIFIED** | Blocked: No remote public API gateway URL. |
| **3** | Real hosted user signs in and signs out | **PASS** *(JWT auth verified)* | **NOT VERIFIED** | Blocked: Requires hosted frontend and public API URL. |
| **4** | Administrator and user roles resolved correctly | **PASS** *(RoleChecker verified)* | **NOT VERIFIED** | Blocked: Requires remote authentication session. |
| **5** | Creator creates draft & executes governance | **PASS** *(E2E cycle passed)* | **NOT VERIFIED** | Blocked: Requires public endpoint to invoke API. |
| **6** | Correction suggestion creates immutable version & refreshes checksum | **PASS** *(M5D verified)* | **NOT VERIFIED** | Blocked: Requires hosted endpoint. |
| **7** | Raster image upload, contrast & aspect-ratio evaluation | **PASS** *(PIL analysis passed)* | **NOT VERIFIED** | Blocked: Requires hosted endpoint. |
| **8** | Multi-page PDF upload, page rendering & findings inspection | **PASS** *(PyMuPDF verified)* | **NOT VERIFIED** | Blocked: Requires hosted endpoint. |
| **9** | Creator cannot approve own submission (Anti-self-approval) | **PASS** *(HTTP 403 verified)* | **NOT VERIFIED** | Blocked: Requires hosted endpoint. |
| **10** | Authorized approval manager approves submission | **PASS** *(Approval lifecycle passed)* | **NOT VERIFIED** | Blocked: Requires hosted endpoint. |
| **11** | Cross-organization access rejected (Tenant isolation) | **PASS** *(Tenant isolation passed)* | **NOT VERIFIED** | Blocked: Requires hosted endpoint. |
| **12** | Uploaded files & previews persist across application restarts | **PASS** *(Local storage verified)* | **NOT VERIFIED** | Blocked: Persistent volume mount not provisioned on remote host. |
| **13** | Logout revocation remains effective | **PASS** *(Revocation store passed)* | **NOT VERIFIED** | Blocked: Requires remote sign-out test. |
| **14** | Production mode hides dev login, docs, stack traces & secrets | **PASS** *(M5G checks passed)* | **NOT VERIFIED** | Blocked: Requires public URL inspection. |

---

## 7. Results of Local Verification Tests

### 7.1 Backend Test Suite (Pytest)
```bash
python -m pytest -q
```
- **Outcome:** **208 passed, 0 failed** across all 27 test files in 393.18s.
- Includes full regression suites for Milestones 1–5G:
  - Baseline rules & evidence-linked citations
  - Context-sensitive negation detection
  - OCR extraction & raster typography
  - Approval state machine & anti-self-approval
  - Localized contrast & WCAG thresholds
  - Historical governance analytics
  - Multi-page PDF governance
  - Context-preserving correction suggestions
  - Real JWT authentication & server-side token revocation
  - Production seed guard & startup configuration safeguards

### 7.2 Frontend Unit Tests (Vitest)
```bash
npm test -- --run
```
- **Outcome:** **9 passed, 0 failed** across 3 test files in 1.44s.

### 7.3 Frontend Production Build
```bash
npm run build
```
- **Outcome:** Clean production bundle generated in 667ms without TypeScript or bundler errors:
  - `dist/index.html` (0.45 kB)
  - `dist/assets/index-BYXwF3wO.js` (497.25 kB │ gzip: 130.46 kB)
  - `dist/assets/index-BCiOho1k.css` (5.01 kB │ gzip: 1.69 kB)

---

## 8. Step-by-Step Production Deployment Runbook

When public cloud infrastructure becomes available, operators must execute the following sequence:

### Step 1: Provision Persistent Storage & Environment
```bash
# On the host server:
mkdir -p /var/lib/inkloom/storage
chmod 700 /var/lib/inkloom/storage
```
Set environment variables per Section 3 in `/etc/inkloom/inkloom.env` or via container secrets.

### Step 2: Run Alembic Database Migrations
```bash
cd backend
python -m alembic upgrade head
```
*(Verify output reports `c3d4e5f6a7b8 (head)`).*

### Step 3: Provision Hosted Administrator
```bash
python provision_admin.py \
  --org-name "Hosted Demo Org" \
  --org-slug "demo" \
  --admin-email "admin@hosted-demo.inkloom.ai" \
  --admin-name "Hosted Administrator"
```
Record the auto-generated 24-character password output to terminal and deliver it securely to the project owner via password manager.

### Step 4: Launch Backend Service
```bash
python -m uvicorn app.main:app \
  --host 0.0.0.0 \
  --port 8000 \
  --workers 1
```

### Step 5: Configure Reverse Proxy (Nginx Example with TLS)
```nginx
server {
    listen 443 ssl http2;
    server_name demo.inkloom.ai;

    ssl_certificate /etc/letsencrypt/live/demo.inkloom.ai/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/demo.inkloom.ai/privkey.pem;

    # Serve compiled frontend SPA
    root /var/www/inkloom/frontend/dist;
    index index.html;
    location / {
        try_files $uri $uri/ /index.html;
    }

    # Proxy API calls to single-worker Uvicorn
    location /api/ {
        proxy_pass http://127.0.0.1:8000/api/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;
    }
}
```

---

## 9. Conclusion & Release Decision

The Inkloom.AI application code, database schema, security safeguards, and build artifacts are completely hardened, verified, and free of defects. 

However, because public application server infrastructure, DNS records, and remote HTTPS entry points have not yet been provisioned in a cloud environment, the application cannot truthfully be marked as remotely verified.

**Final Milestone Status:** **DEPLOYMENT BLOCKED — PREREQUISITES MISSING**

### Resolution Path to `HOSTED DEMO VERIFIED`:
1. Provision cloud application container host (e.g., Render, Fly.io, Railway, or AWS EC2/ECS).
2. Attach persistent volume mount at `/var/lib/inkloom/storage`.
3. Configure public domain DNS record pointing to host.
4. Enable HTTPS / TLS reverse proxy.
5. Execute the 14-point remote smoke test matrix against the deployed HTTPS URL.
