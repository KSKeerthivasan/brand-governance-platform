# Milestone 5I — Deploy Inkloom.AI Using Firebase + Cloud Run + Supabase

**Workspace:** `E:\CodeStar30`  
**Target Project ID:** `ad-governance`  
**Date:** October 28, 2026  
**Platform Version:** Inkloom.AI v1.0.0  
**Status:** **DEPLOYMENT BLOCKED — BILLING OR ACCESS PREREQUISITES**

---

## 1. Executive Summary

Milestone 5I establishes the deployment strategy, cloud resource audit, and operational readiness for deploying **Inkloom.AI** using **Firebase Hosting** for the React 19 frontend SPA, **Google Cloud Run** for the containerised FastAPI backend, and **Supabase Managed PostgreSQL** for database persistence.

Following the successful completion of user authentication on the Firebase CLI, the Firebase MCP server and CLI tools were able to conduct a complete inspection of project `ad-governance`.

### Key Verification Highlights
1. **Authentication Verified:** The Firebase CLI and MCP server are authenticated as `kskvasan2007@gmail.com` with active project `ad-governance` (Project Number: `669764480364`).
2. **Registered Web App & Hosting Verified:** Web app `Ad-govern` (`1:669764480364:web:3b0f50b12e7fcafb53d749`) is active and linked to the Firebase Hosting site `https://ad-governance.web.app`.
3. **Billing Status Verified:** The Firebase environment inspection confirmed **`Billing Enabled: No`** (Firebase Spark plan).
4. **Cloud Run Blocker:** While static Firebase Hosting is fully functional under the free Spark plan, deploying the containerized FastAPI backend to Google Cloud Run strictly requires an active Google Cloud Billing account (Blaze plan).
5. **Storage Bucket Usability:** The configured bucket `ad-governance.firebasestorage.app` returned HTTP 404 (Not Found), confirming Firebase Storage has not yet been initialized in the Firebase Console.
6. **Secrets Remediated:** All real database passwords and static signing keys were excised from deployment examples and replaced with Google Cloud Secret Manager references.

---

## 2. Project Inspection Results via Firebase MCP & CLI

### 2.1 Authenticated Environment Summary
- **Authenticated Account:** `kskvasan2007@gmail.com`
- **Active Project ID:** `ad-governance` (configured as `default` in `.firebaserc`)
- **Project Number:** `669764480364`
- **Project Name:** `AD-governance`
- **Created:** `2026-10-28T17:05:50.485Z`
- **Project Directory:** `E:\CodeStar30`
- **Billing State:** **`Billing Enabled: No`** (Spark Tier)
- **Gemini in Firebase Terms of Service:** `Accepted`

### 2.2 Discovered Project Resources

| Resource | Identifier / URL | Status | Details |
| :--- | :--- | :---: | :--- |
| **Firebase Project** | `ad-governance` (`669764480364`) | **ACTIVE** | Lifecycle: ACTIVE, Labels: firebase: enabled |
| **Registered Web App** | `1:669764480364:web:3b0f50b12e7fcafb53d749` | **ACTIVE** | Display Name: `Ad-govern`, Web ID registered |
| **Firebase Hosting Site** | `ad-governance` | **ACTIVE** | Default URL: `https://ad-governance.web.app` |
| **Live Hosting Channel** | `live` channel on `ad-governance` | **READY** | Provisioned, waiting for initial bundle deployment |
| **Firebase Storage** | `ad-governance.firebasestorage.app` | **NOT FOUND (404)** | Bucket not yet initialized in Firebase Console |
| **Google Cloud Billing** | Billing Account on `ad-governance` | **DISABLED** | Free Spark plan active; Cloud Run blocked |
| **Google Cloud CLI** | `gcloud` executable on local host | **NOT INSTALLED** | Managed via Firebase CLI & MCP server |

---

## 3. Remediated Deployment Secrets & Security Policy

### 3.1 Secret Sanitization
In accordance with Phase 3 safety requirements:
1. All literal credentials (including database connection strings and fixed signing keys) were purged from repository examples and documentation.
2. Production deployment commands now specify Secret Manager references:
   ```bash
   --set-secrets "DATABASE_URL=INKLOOM_PROD_DATABASE_URL:latest,SECRET_KEY=INKLOOM_PROD_SECRET_KEY:latest"
   ```
3. **Database Password Rotation Recommendation:** The project owner should rotate the database password in the Supabase Dashboard (`Project Settings -> Database -> Reset database password`) to ensure absolute zero-exposure hygiene.
4. **JWT Invalidation:** Generating a new production `SECRET_KEY` will automatically invalidate any prior mock or dev tokens, ensuring clean session isolation in the hosted environment.

---

## 4. Storage Architecture & Usability Assessment

### 4.1 Storage Bucket Usability Test
Direct API inspection against the configured Firebase Storage endpoint:
```python
httpx.get('https://firebasestorage.googleapis.com/v0/b/ad-governance.firebasestorage.app/o')
# Result: Status 404 Not Found
```
**Conclusion:** The Firebase Storage bucket has not yet been provisioned in the Firebase Console.

### 4.2 Application Storage Abstraction
Inspection of `backend/app/services/storage.py` confirms that the backend currently uses local filesystem storage (`settings.LOCAL_STORAGE_DIR`).

**Recommended Durable Storage Options for Cloud Run:**
- **Option A (Google Cloud Storage FUSE Mount - Zero Code Changes):** When billing is linked, initialize a GCS bucket (`ad-governance-assets`) and attach it as a Cloud Run volume mount to `/var/lib/inkloom/storage`. This provides durable persistence for uploaded assets, PDFs, and rendered page caches with zero modifications to FastAPI code.
- **Option B (Private Supabase Storage):** Implement a backend-only Supabase Storage client in `StorageService` using the private service key, storing files in `inkloom-private-assets`.

---

## 5. Deployment Architecture & Cloud Run Constraints

```
                      ┌──────────────────────────────────────┐
                      │          Public Web Browser          │
                      └──────────────────┬───────────────────┘
                                         │ HTTPS (Port 443)
                                         ▼
                      ┌──────────────────────────────────────┐
                      │    Firebase Hosting (ad-governance)  │
                      │    - URL: https://ad-governance.web.app│
                      │    - Static React 19 Frontend SPA    │
                      │    - Rewrites: /api/** -> Cloud Run  │
                      └──────────────────┬───────────────────┘
                                         │ Internal Proxy
                                         ▼
┌────────────────────────────────────────────────────────────────────────────┐
│  Google Cloud Run (Service: inkloom-api, Region: us-central1)             │
│                                                                            │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │ Container: python:3.12-slim                                          │  │
│  │                                                                      │  │
│  │  - Single-Worker Uvicorn: uvicorn app.main:app --workers 1           │  │
│  │  - Single Instance Cap: --max-instances 1 (Rate limiter integrity)  │  │
│  │  - Native Dependencies: libgl1, libgomp1, libglib2.0-0               │  │
│  │  - Document Pipeline: PyMuPDF, Pillow, RapidOCR, ONNX Runtime        │  │
│  └──────────────────────────────────┬───────────────────────────────────┘  │
│                                     │                                      │
└─────────────────────────────────────┼──────────────────────────────────────┘
                                      │ Encrypted TLS (Port 5432)
                                      ▼
┌────────────────────────────────────────────────────────────────────────────┐
│  Supabase Managed PostgreSQL                                               │
│  - Host: db.qwvqifqnyurlqewkrsiw.supabase.co                               │
│  - Migration Revision: c3d4e5f6a7b8 (head) - 19 tables verified             │
│  - Auth Tokens, Content Versions, Audit Logs, Governance Findings          │
└────────────────────────────────────────────────────────────────────────────┘
```

### Critical Cloud Run Operating Constraints:
1. **Single-Instance Enforcement (`--max-instances 1`):** Required to ensure `LoginRateLimiter` (`backend/app/services/auth.py`) state remains synchronized in memory across requests without an external Redis instance.
2. **Container Memory & CPU:** Recommended `--memory 2Gi --cpu 2` to accommodate ONNX Runtime OCR and multi-page PDF rendering under concurrent requests.
3. **Timeout Constraint:** Firebase Hosting rewrites time out after 60 seconds. Multi-page PDF evaluation batches must be capped or monitored to ensure completions within 60s.

---

## 6. Billing Prerequisites & Cost Estimates

In accordance with Phase 4 guidelines, **no billing upgrade or billable resource was initiated**.

### 6.1 Prerequisites for Cloud Run Backend
1. **Action Required:** Link a Google Cloud Billing account to project `ad-governance` via [Google Cloud Console Billing](https://console.cloud.google.com/billing).
2. **Plan:** Blaze Plan (Pay as you go).
3. **Estimated Demo Operating Costs:**
   - **Cloud Run:** Free tier includes 2 million requests/month, 360,000 vCPU-seconds, and 180,000 GiB-seconds. For a single-instance controlled demo with scale-to-zero when idle, estimated cost is **$0.00 / month**.
   - **Artifact Registry:** Free tier includes 0.5 GB/month storage.
   - **Firebase Hosting:** Free tier includes 10 GB storage and 360 MB/day transfer (Spark plan).
   - **Total Estimated Demo Cost:** **$0.00** under normal demonstration workloads.

---

## 7. The 18-Point End-to-End Verification Matrix

| # | Checkpoint | Local Automated Status | Remote Hosted Status | Blocker / Reason |
| :---: | :--- | :---: | :---: | :--- |
| **1** | Firebase Hosting URL loads over HTTPS | **PASS** *(Build clean)* | **NOT VERIFIED** | Blocked: Initial hosting release pending backend URL decision |
| **2** | SPA routes reload without 404 | **PASS** *(Rewrites configured)* | **NOT VERIFIED** | Blocked: Hosting site not deployed yet |
| **3** | API health endpoint returns healthy | **PASS** *(Local /health OK)* | **NOT VERIFIED** | Blocked: Cloud Run container requires billing to deploy |
| **4** | Unauthenticated request receives HTTP 401 | **PASS** *(Verified)* | **NOT VERIFIED** | Blocked: Requires public Cloud Run API |
| **5** | Real user signs in and signs out | **PASS** *(JWT verified)* | **NOT VERIFIED** | Blocked: Requires remote hosted session |
| **6** | Forged identity headers cannot escalate role | **PASS** *(RoleChecker verified)* | **NOT VERIFIED** | Blocked: Requires remote API test |
| **7** | Creator creates draft & runs governance | **PASS** *(E2E cycle passed)* | **NOT VERIFIED** | Blocked: Requires hosted endpoint |
| **8** | Correction creates version & invalidates run | **PASS** *(M5D verified)* | **NOT VERIFIED** | Blocked: Requires hosted endpoint |
| **9** | Raster image upload & visual governance | **PASS** *(PIL analysis passed)* | **NOT VERIFIED** | Blocked: Requires hosted endpoint |
| **10** | Multi-page PDF upload, OCR & findings | **PASS** *(PyMuPDF verified)* | **NOT VERIFIED** | Blocked: Requires hosted endpoint |
| **11** | PDF previews & assets persist on restart | **PASS** *(Local disk OK)* | **NOT VERIFIED** | Blocked: Cloud Run volume mount not attached |
| **12** | Creator cannot approve own content | **PASS** *(HTTP 403 verified)* | **NOT VERIFIED** | Blocked: Requires hosted endpoint |
| **13** | Approval manager approves submission | **PASS** *(Passed)* | **NOT VERIFIED** | Blocked: Requires hosted endpoint |
| **14** | Cross-organization access rejected | **PASS** *(Tenant isolation passed)* | **NOT VERIFIED** | Blocked: Requires hosted endpoint |
| **15** | Reviewer dispositions & analytics work | **PASS** *(Passed)* | **NOT VERIFIED** | Blocked: Requires hosted endpoint |
| **16** | Logout token revocation effective | **PASS** *(Revocation store passed)* | **NOT VERIFIED** | Blocked: Requires remote sign-out test |
| **17** | Production mode hides dev login, docs & traces | **PASS** *(M5G checks passed)* | **NOT VERIFIED** | Blocked: Requires public URL inspection |
| **18** | Supabase Data API access constrained | **PASS** *(No direct frontend calls)* | **NOT VERIFIED** | Blocked: Supabase RLS policies unapplied |

---

## 8. Automated Local Test Verification Results

### 8.1 Backend Regression Suite
- **Focused Hardening Tests:** `python -m pytest tests/test_milestone5g_hardening.py -q` — **9 passed, 0 failed** in 0.76s.
- **Full Backend Suite:** 208 passed, 0 failed across all 27 test files in 393.18s.
- **Dependencies:** Updated `backend/requirements.txt` with `rapidocr-onnxruntime>=1.4.0` and `onnxruntime>=1.20.0`.

### 8.2 Frontend Production Build
```bash
npm run build
```
- **Outcome:** Clean production bundle generated in `frontend/dist` in 554ms without errors:
  - `dist/index.html` (0.45 kB)
  - `dist/assets/index-BYXwF3wO.js` (497.25 kB │ gzip: 130.46 kB)
  - `dist/assets/index-BCiOho1k.css` (5.01 kB │ gzip: 1.69 kB)

---

## 9. Next Steps to Complete Deployment

Once the project owner authorizes and completes billing setup:

1. **Enable Google Cloud Billing:** Link a billing account to project `ad-governance`.
2. **Initialize Storage Bucket:** In Firebase Console, click Storage -> Get Started to provision the default storage bucket, or configure a GCS bucket for Cloud Run mounting.
3. **Deploy Backend to Cloud Run:**
   ```powershell
   cd E:\CodeStar30\backend
   gcloud run deploy inkloom-api `
     --source . `
     --project ad-governance `
     --region us-central1 `
     --platform managed `
     --allow-unauthenticated `
     --max-instances 1 `
     --memory 2Gi `
     --set-env-vars "ENVIRONMENT=production,DEBUG=False,ALLOW_DEV_LOGIN=False,CORS_ORIGINS=https://ad-governance.web.app,https://ad-governance.firebaseapp.com" `
     --set-secrets "DATABASE_URL=INKLOOM_PROD_DATABASE_URL:latest,SECRET_KEY=INKLOOM_PROD_SECRET_KEY:latest"
   ```
4. **Deploy Frontend to Firebase Hosting:**
   ```powershell
   cd E:\CodeStar30
   firebase deploy --only hosting --project ad-governance
   ```
5. **Execute Smoke Verification:** Run the 18-point verification matrix against `https://ad-governance.web.app`.

---

## 10. Final Release Status

**Release Status:** **DEPLOYMENT BLOCKED — BILLING OR ACCESS PREREQUISITES**

The repository is completely prepared, hardened, containerized, and verified locally. Full remote deployment will proceed immediately once Google Cloud billing is linked to project `ad-governance`.
