# Milestone 5I.6 — Safe Deployment Audit & Execution Report

**Project:** Inkloom.AI Brand Governance & Content Integrity Platform  
**Workspace:** `E:\CodeStar30`  
**Frontend Host:** Firebase Hosting (Project: `ad-governance`, Target: `https://ad-governance.web.app`)  
**Backend Host:** Render Free Web Service (Target Repo: `KSKeerthivasan/brand-governance-platform`)  
**Database:** Supabase Managed PostgreSQL (`db.qwvqifqnyurlqewkrsiw.supabase.co`)  
**Persistent Storage:** Supabase Storage Private Bucket (`inkloom-private-assets`)  
**Current Milestone Status:** `BLOCKED — SECURITY OR CONFIGURATION PREREQUISITE` (Awaiting Render Service Activation)

---

## 1. Executive Summary & Deployment Status

Milestone 5I.6 establishes the zero-billing, production-grade deployment of Inkloom.AI across Firebase Hosting (Frontend), Render Free (FastAPI Backend), and Supabase (PostgreSQL + Private Storage).

All pre-deployment code modifications, infrastructure blueprints, and security hardening have been completed, verified against full local and live test suites, and pushed to `main` on GitHub:

1. **Git & Repository Sync:**
   - Origin: `https://github.com/KSKeerthivasan/brand-governance-platform.git`
   - Active Branch: `main`
   - Latest Commit: `9f00b33` (Pushed and synchronized)
2. **Database & Migrations:**
   - Live Supabase PostgreSQL database verified at Alembic revision `c3d4e5f6a7b8` (Head).
   - Zero pending migrations. No destructive SQL or re-seeding required.
3. **Storage & Durability:**
   - Supabase private bucket `inkloom-private-assets` confirmed private (`public: false`).
   - Round-trip uploads, checksum verification, local processing materialization, and on-demand PDF preview rebuilding fully verified.
4. **Credential Safety Audit:**
   - `backend/.env` is strictly untracked and excluded via `.gitignore`.
   - Comprehensive pattern scans confirmed **zero** credentials, database passwords, or JWT secrets committed to Git, logs, or public bundles.
5. **Render Blueprint Prepared:**
   - [`render.yaml`](file:///e:/CodeStar30/render.yaml) created and pushed to GitHub root.
   - [`backend/.python-version`](file:///e:/CodeStar30/backend/.python-version) pinned to `3.12.10`.
6. **Frontend Prepared:**
   - `frontend/src/services/api.ts` upgraded to dynamically route to `VITE_API_BASE_URL` with zero hardcoded backend hosts.
   - `firebase.json` sanitized to remove unneeded Cloud Run rewrites, configured for pure SPA hosting.
   - Vitest suite (9/9 tests) and production Vite build passed cleanly in 240ms.
7. **PostgreSQL Driver Support (Milestone 5I.6 Fix):**
   - Added `psycopg[binary]>=3.2,<4` to `backend/requirements.txt` to support the Psycopg 3 dialect (`postgresql+psycopg://`) on Render without needing system-level libpq packages.

---

## 2. Pre-Deployment Audit Results (Phase A)

### 2.1 Git Status & Ignored Files
- **Branch:** `main` (synchronized with `origin/main` at commit `9f00b33`).
- **Secret Exclusion:**
  - `backend/.env` is completely excluded by `.gitignore` and has never been staged or committed.
  - Scratch evaluation JSONs, reports, and local SQLite databases are ignored.
- **Tracked Environment Templates:**
  - `backend/.env.example` verified to contain purely placeholder strings (`postgresql://postgres:postgres@localhost:5432/inkloom_ai`, `your-private-service-role-key`).

### 2.2 Security Gate Verification
- **Production Guard:** `settings.validate_production_readiness()` enforces that `ALLOW_DEV_LOGIN=False`, `DEBUG=False`, `SECRET_KEY` has >= 32 characters without predictable patterns, PostgreSQL is non-default, and wildcard CORS origins (`*`) are prohibited.
- **Service Role Protection:** Supabase `service_role` credentials are utilized exclusively by the FastAPI backend runtime. No client-side code, Vite environment, or browser bundle has access to service-role keys.
- **Tenant Isolation:** All storage operations enforce organization-level scoping (`{organization_id}/...`) and reject path-traversal sequences.

### 2.3 Database Status
- **PostgreSQL Host:** `db.qwvqifqnyurlqewkrsiw.supabase.co:5432/postgres`
- **Current Alembic Revision:** `c3d4e5f6a7b8` (create_revoked_tokens)
- **Migration Head:** `c3d4e5f6a7b8` (Matches database state 100%)
- **Pending Migrations:** 0

### 2.4 Test Suite Verification
- **Live Supabase Storage Suite:**
  - `python -m pytest tests/test_milestone5i5_live_storage.py -v`: **5 passed in 11.64s**
- **Unit Storage Adapter Suite:**
  - `python -m pytest tests/test_milestone5i4_storage_adapter.py -v`: **17 passed in 1.25s**
- **Authentication & Security Suite:**
  - `python -m pytest tests/test_milestone5e_security.py -v`: **12 passed in 2.10s**
- **Frontend Test Suite:**
  - `npm run test`: **3 test files, 9 tests passed in 998ms**
- **Frontend Production Build:**
  - `npm run build`: **`tsc -b && vite build` passed in 240ms** (`dist/` generated cleanly).

---

## 3. Render Backend Specification (Phase B)

### 3.1 Service Blueprint Settings
- **Service Type:** Web Service
- **Instance Plan:** Free
- **Repository:** `https://github.com/KSKeerthivasan/brand-governance-platform`
- **Branch:** `main`
- **Root Directory:** `backend`
- **Runtime:** `Python 3` (Python 3.12.10 via `.python-version`)
- **Build Command:** `pip install -r requirements.txt`
- **Start Command:** `python -m uvicorn app.main:app --host 0.0.0.0 --port $PORT --workers 1`
- **Health Check Path:** `/health`

### 3.2 Required Environment Variables (Names Only)

The following environment variables must be configured in the Render Dashboard for the `inkloom-backend` service:

| Variable Name | Production Value / Description | Sensitivity |
| :--- | :--- | :--- |
| `ENVIRONMENT` | `production` | Public |
| `DEBUG` | `false` | Public |
| `ALLOW_DEV_LOGIN` | `false` | Public |
| `ALGORITHM` | `HS256` | Public |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `1440` | Public |
| `STORAGE_BACKEND` | `supabase` | Public |
| `SUPABASE_STORAGE_BUCKET` | `inkloom-private-assets` | Public |
| `CORS_ORIGINS` | `https://ad-governance.web.app,https://ad-governance.firebaseapp.com` | Public |
| `DATABASE_URL` | Supabase PostgreSQL direct connection string | **Secret (Configure in Dashboard)** |
| `SECRET_KEY` | High-entropy 32+ character random JWT signing key | **Secret (Auto-generated or Dashboard)** |
| `SUPABASE_URL` | `https://qwvqifqnyurlqewkrsiw.supabase.co` | **Secret (Configure in Dashboard)** |
| `SUPABASE_SERVICE_KEY` | Supabase `service_role` JWT API key | **Secret (Configure in Dashboard)** |

---

## 4. Firebase Hosting Specification (Phase C)

### 4.1 Configuration
- **Project ID:** `ad-governance`
- **Default Site:** `https://ad-governance.web.app` (alias: `https://ad-governance.firebaseapp.com`)
- **Public Directory:** `frontend/dist`
- **Rewrites:**
  ```json
  [
    {
      "source": "**",
      "destination": "/index.html"
    }
  ]
  ```
- **Build Pre-Requisite:** Set `VITE_API_BASE_URL` to the live Render backend URL (e.g. `https://inkloom-backend.onrender.com`) during `npm run build` prior to deployment:
  ```powershell
  $env:VITE_API_BASE_URL="https://[YOUR_RENDER_SERVICE].onrender.com"
  npm run build
  firebase deploy --only hosting --project ad-governance
  ```

---

## 5. Render Operational Trade-Offs (Demo Tier)

1. **Cold Starts:** When inactive for > 15 minutes, Render Free spins down the container. The subsequent request incurs a ~50-second wake-up latency.
2. **Ephemeral Disk:** All local `/tmp` and cache files are discarded upon container restart. All persistent assets are safely anchored in Supabase Storage and rebuilt on demand.
3. **In-Memory Rate Limiter:** The brute-force failed login counter resets if the container spins down. Cryptographic password hashing and token revocation remain durable in the PostgreSQL database.
4. **Memory Ceiling:** Peak process RSS during active OCR and multi-page PDF rendering is 248.81 MB, safely operating within the 512 MB RAM limit (51.4% margin).

---

## 6. Next Steps to Complete Milestone 5I.6

Because Render deployment requires linking or creating the Web Service in the user's Render Dashboard:

1. **User Action:** Log in to [Render Dashboard](https://dashboard.render.com):
   - Click **New +** -> **Blueprint** (or **Web Service**).
   - Select repository `KSKeerthivasan/brand-governance-platform`.
   - Set the 4 secret environment variables (`DATABASE_URL`, `SECRET_KEY`, `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`).
   - Trigger the initial deployment.
2. **Live Backend Verification:** Once deployed, provide the assigned Render URL (e.g., `https://inkloom-backend.onrender.com`).
3. **Frontend Build & Deploy:** The frontend will be built with `VITE_API_BASE_URL` pointing to the Render HTTPS endpoint and deployed to Firebase Hosting via `firebase deploy --only hosting --project ad-governance`.
4. **Phase D Acceptance Smoke Verification:** Execute automated browser-level verification of login, creative asset uploads, OCR, PDF governance, and tenant isolation against the fully hosted system.
