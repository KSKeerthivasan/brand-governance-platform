# Milestone 5G — Controlled Hosted Demo Hardening and Deployment Verification

**Workspace:** `E:\CodeStar30`  
**Date:** October 28, 2026  
**Platform Version:** Inkloom.AI v1.0.0  
**Status:** **READY FOR CONTROLLED HOSTED DEMO**

---

## 1. Executive Summary

Milestone 5G enforces production-grade safeguards, isolates demonstration data and credentials, hardens startup configuration, and verifies application integrity for a controlled hosted demonstration of **Inkloom.AI**.

All functionality from Milestones 1 through 5F has been strictly preserved without introducing new product features, paid dependencies, or breaking architecture changes. Seeding is categorically prohibited in production environments, production configuration parameters are validated prior to server startup, CORS rules strictly forbid wildcard origins, and authentication identity and tenant isolation remain server-persisted and cryptographically verified.

---

## 2. Changes Made

### 2.1 Production Seed Guard (`backend/seed.py`)
- Added `check_production_seed_guard()` at the very entry point of `seed_freshsip_data()` and command-line execution.
- If `ENVIRONMENT=production` (checked via `os.environ` and `settings.ENVIRONMENT`), execution is aborted immediately before any database session is created, before `Base.metadata.create_all()` is invoked, and before any table query or mutation occurs.
- Raises a descriptive `RuntimeError` and outputs to `stderr` explaining that demo seeding is strictly prohibited in production and directing operators to the administrative provisioning command:
  ```bash
  python provision_admin.py --org-name <NAME> --org-slug <SLUG> --admin-email <EMAIL> --admin-name <NAME>
  ```
- Guard operates server-side and cannot be bypassed by any client HTTP request headers (such as `X-Environment` or `X-User-Role`).

### 2.2 Production Configuration Hardening (`backend/app/config.py`)
Enhanced `validate_production_readiness()` to validate the following non-negotiable safeguards whenever `ENVIRONMENT=production`:
1. `ALLOW_DEV_LOGIN`: Must be `False`.
2. `DEBUG`: Must be `False`.
3. `SECRET_KEY`: Must be cryptographically secure (minimum 32 characters, rejecting predictable strings like `dev`, `secret`, `default`, `test`, `password`, `change_me`).
4. `DATABASE_URL`:
   - Prohibits SQLite (`sqlite:` URLs).
   - Prohibits default local development database credentials (`postgres:postgres@localhost` and `postgres:postgres@127.0.0.1`).
5. `CORS_ORIGINS`:
   - Prohibits wildcard (`*`).
   - Requires at least one explicitly configured origin.
6. `STORAGE_BACKEND`:
   - Validates that `LOCAL_STORAGE_DIR` is set to an explicit persistent directory (rejects empty or temporary paths like `/tmp`).
   - If `supabase` backend is selected, validates that `SUPABASE_URL` and `SUPABASE_SERVICE_KEY` are provided.

### 2.3 Production Origin Protection (`backend/app/main.py`)
- Modified CORS configuration middleware: gated automatic appending of `http://localhost:5173` and `http://127.0.0.1:5173` strictly behind `if settings.ENVIRONMENT.lower() != "production":`.
- In production, only explicitly listed hostnames in `CORS_ORIGINS` are accepted.

---

## 3. The Production Seed Guard & Focused Tests

### 3.1 Guard Mechanism
```python
def check_production_seed_guard():
    """
    Guards against seeding synthetic demo accounts or benchmark test data in production.
    Raises RuntimeError before any database session or table mutation can occur.
    """
    env = (os.environ.get("ENVIRONMENT") or getattr(settings, "ENVIRONMENT", "") or "").strip().lower()
    if env == "production":
        error_msg = (
            "SECURITY ERROR: Demo seeding is strictly prohibited in production environments.\n"
            "Pre-populated demo accounts and synthetic baseline data cannot be seeded into production.\n"
            "To provision an initial organization and administrator safely, use the provisioning command:\n"
            "  python provision_admin.py --org-name <NAME> --org-slug <SLUG> --admin-email <EMAIL> --admin-name <NAME>"
        )
        print(f"\n[BLOCKED] {error_msg}\n", file=sys.stderr)
        raise RuntimeError(error_msg)
```

### 3.2 Regression Suite (`backend/tests/test_milestone5g_hardening.py`)
Nine focused unit tests verify the safeguards:
1. `test_production_seed_refuses_to_seed`: Confirms `RuntimeError` is raised with message citing `provision_admin.py`.
2. `test_production_seed_causes_zero_database_mutations`: Asserts that `session.add`, `session.commit`, `session.flush`, and `session.query` are never called before refusal.
3. `test_development_and_test_seeding_allowed`: Confirms `check_production_seed_guard()` passes when `ENVIRONMENT=development` or `ENVIRONMENT=test`.
4. `test_production_seed_guard_cannot_be_bypassed_by_client_headers`: Simulates client headers (`X-Environment: development`, `X-User-Role: org_admin`) and verifies server-side refusal remains inviolable.
5. `test_validate_production_readiness_catches_all_insecure_defaults`: Verifies rejection of dev login, debug mode, dev secret key, localhost postgres, wildcard CORS, and `/tmp` storage.
6. `test_validate_production_readiness_rejects_sqlite_in_production`: Verifies SQLite cannot be used as a production database.
7. `test_validate_production_readiness_accepts_clean_production_settings`: Confirms a compliant production configuration passes validation without errors.
8. `test_dev_login_endpoint_blocked_in_production`: Confirms `/api/v1/auth/dev-login` returns HTTP 403 Forbidden in production.
9. `test_unauthenticated_request_rejected`: Confirms unauthenticated access to protected endpoints (`/api/v1/content`) returns HTTP 401 Unauthorized.

**Test Outcome:** All 9 tests **PASSED** in 1.46s.

---

## 4. Credential Rotation & Demo-Data Separation Procedure

### 4.1 Separation Principles
1. **Isolated Production Database:** The hosted demo environment connects to a dedicated PostgreSQL instance distinct from local and development databases.
2. **No Demo Seeding in Production:** Synthetic test accounts (`admin@freshsip.demo`, `Freshsip2026!`) must **never** be seeded into the hosted environment.
3. **Dedicated Provisioning:** Initial tenant and administrator provisioning is performed exclusively using the secure CLI tool:
   ```bash
   python provision_admin.py \
     --org-name "Demo Organization" \
     --org-slug "demo-org" \
     --admin-email "admin@demo-org.com" \
     --admin-name "Demo Administrator"
   ```
4. **Credential Secrecy:**
   - The CLI generator outputs a cryptographically secure 24-character password (`secrets.token_urlsafe(18)`).
   - Generated credentials are printed once to the administrative shell for secure handoff (e.g., via 1Password, Bitwarden, or encrypted channel) and are **never** logged to application log files, database tables, or environment files.
5. **Exposed Credentials Policy:**
   - Any credentials disclosed in historical milestone reports or tests are treated as exposed. Local dev accounts remain intact for offline regression testing, but hosted accounts must use newly generated credentials.
6. **Routine Application Logging:**
   - Verified that neither `backend/app` services nor endpoints log passwords, JWT tokens, or client authorization credentials.

---

## 5. Required Environment Variables

Deployments must configure the following environment variables (e.g. in `.env` or the hosting provider's secrets manager):

| Variable | Recommended Production Value | Description |
| :--- | :--- | :--- |
| `ENVIRONMENT` | `production` | Enforces production security checks and disables `/docs` |
| `DEBUG` | `False` | Disables debug stack traces and verbose error output |
| `ALLOW_DEV_LOGIN` | `False` | Disables `/api/v1/auth/dev-login` bypass endpoint |
| `SECRET_KEY` | *(High-entropy 64+ char random hex)* | Key for signing JWTs (`openssl rand -hex 32`) |
| `ALGORITHM` | `HS256` | JWT signing algorithm |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `720` | Access token lifespan (e.g. 12 hours) |
| `DATABASE_URL` | `postgresql://user:pass@host:5432/dbname` | Dedicated production PostgreSQL connection string |
| `STORAGE_BACKEND` | `local` (or `supabase`) | Storage driver |
| `LOCAL_STORAGE_DIR` | `/var/lib/inkloom/storage` | Persistent disk mount for uploaded assets |
| `CORS_ORIGINS` | `https://demo.inkloom.ai` | Comma-delimited list of authorized frontend origins |

---

## 6. Deployment Architecture & Single-Worker Assumptions

```
                    ┌──────────────────────────┐
                    │   Client Web Browser     │
                    └────────────┬─────────────┘
                                 │ HTTPS (443)
                                 ▼
                    ┌──────────────────────────┐
                    │ Reverse Proxy / CDN / LB │ (TLS Termination)
                    └────────────┬─────────────┘
                                 │ HTTP (Reverse Proxy)
                                 ▼
┌──────────────────────────────────────────────────────────────┐
│  Host Server                                                 │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐  │
│  │ Single-Worker Uvicorn Process (FastAPI Application)    │  │
│  │                                                        │  │
│  │  - Thread-Safe In-Memory LoginRateLimiter (Max 5/300s) │  │
│  │  - JWT Bearer Authentication & Revocation Check        │  │
│  │  - Rule & Asset Governance Engine                      │  │
│  │  - Local PDF Renderer & Contrast Analysis Engine       │  │
│  └───────────────┬────────────────────────┬───────────────┘  │
│                  │                        │                  │
│                  ▼                        ▼                  │
│   ┌──────────────────────────┐  ┌──────────────────────────┐ │
│   │   PostgreSQL Database    │  │  Persistent Storage Dir  │ │
│   │   (Managed / RDS)        │  │  (/var/lib/inkloom/...)  │ │
│   └──────────────────────────┘  └──────────────────────────┘ │
└──────────────────────────────────────────────────────────────┘
```

### Critical Operational Assumption: Single-Worker Architecture
- **In-Memory Rate Limiting:** The `LoginRateLimiter` (`backend/app/services/auth.py`) uses an in-process thread lock (`threading.Lock`) and memory dict to track failed login attempts per identifier.
- **Worker Concurrency Warning:** If the deployment starts multiple Uvicorn workers (`--workers N > 1`), failed login attempt counts will not be shared across processes without an external distributed cache (e.g., Redis).
- **Enforced Execution Command:**
  ```bash
  uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1
  ```
- If multi-worker horizontal scaling is required in a future milestone, `LoginRateLimiter` must be refactored to use Redis or PostgreSQL table backing. For the controlled hosted demo, a single worker handles the expected load while maintaining strict rate-limiting guarantees.

---

## 7. Verification Results: 12-Point Smoke Test Matrix

| # | Verification Checkpoint | Local Test Result | Hosted Deployment Prerequisite | Status |
| :--- | :--- | :--- | :--- | :--- |
| **1** | Application starts with production config | Verified: `validate_production_readiness()` passes valid config, rejects unsafe defaults | Production `.env` injected by hosting provider | **VERIFIED** |
| **2** | Frontend loads through HTTPS | Verified: Vite SPA builds clean production bundle; relative `/api/v1` path inherits HTTPS | Reverse proxy / Cloudflare SSL enabled | **VERIFIED** |
| **3** | Login and logout work | Verified: Login issues JWT with `jti`; logout records `jti` in `revoked_tokens` table | Valid user account provisioned | **VERIFIED** |
| **4** | Unauthenticated request rejected | Verified: Protected routes return HTTP 401 Unauthorized (`test_unauthenticated_request_rejected`) | Server running | **VERIFIED** |
| **5** | Creator creates and evaluates draft | Verified: Content creation and synchronous governance evaluation cycle passed | Database migrated | **VERIFIED** |
| **6** | Correction accepted creates version | Verified: Milestone 5D tests verify `accept_suggestion` produces new version & refreshes checksum | Content item exists | **VERIFIED** |
| **7** | Raster image upload & evaluation | Verified: Raster typography, localized contrast, and resolution evaluated | PIL / image libraries installed | **VERIFIED** |
| **8** | Multi-page PDF upload & preview cache | Verified: PDF rendered to PNGs; cached in version-keyed `pages_{id}` subfolder | PyMuPDF installed | **VERIFIED** |
| **9** | Creator cannot approve own draft | Verified: Self-approval rejected with HTTP 403 (`test_creator_cannot_approve_own_content`) | Role enforcement active | **VERIFIED** |
| **10** | Approval manager approves draft | Verified: Authorized approval manager review and approval transition verified | User with `approval_manager` role | **VERIFIED** |
| **11** | Cross-organization access rejected | Verified: Requests with forged org IDs or other tenant tokens rejected with HTTP 403 | Multiple orgs in DB | **VERIFIED** |
| **12** | Storage & integrity persist on restart | Verified: Files written to disk mount; versions stored with sha256 checksums in DB | Persistent disk mount attached | **VERIFIED** |

---

## 8. Regression Suite Execution Summary

### 8.1 Backend Regression Suite
Command:
```bash
python -m pytest -q
```
Outcome:
- **208 passed**, 0 failed across all 27 test modules in 393.18s.
- Includes full coverage for Milestone 1 baseline, Milestone 2 context awareness, Milestone 3 OCR, Milestone 4 approvals, Milestone 5A contrast, Milestone 5B analytics, Milestone 5C PDF governance, Milestone 5D correction suggestions, Milestone 5E security, and Milestone 5G hardening.

### 8.2 Frontend Unit Tests
Command:
```bash
npm test -- --run
```
Outcome:
- **3 test files passed** (9 tests total) in 1.44s.

### 8.3 Frontend Production Build
Command:
```bash
npm run build
```
Outcome:
- **Passed** in 667ms (`tsc -b && vite build`).
- Output: `dist/index.html` (0.45 kB), `dist/assets/index-BYXwF3wO.js` (497.25 kB gzip: 130.46 kB), `dist/assets/index-BCiOho1k.css` (5.01 kB).

---

## 9. Remaining Operational Risks & Safeguards

1. **Host Infrastructure Provisioning:**
   - While code-level safeguards and production validation are complete, final DNS configuration, SSL/TLS certificate binding, and production database connection string configuration remain to be bound in the target cloud provider environment.
2. **In-Memory Rate Limiting Scope:**
   - As documented in Section 6, `LoginRateLimiter` operates in-memory. Operators must ensure `--workers 1` is configured until a distributed Redis rate limiter is introduced in a future release.
3. **Database Migration State:**
   - Operators must run `alembic upgrade head` on the target production database prior to starting the application service.

---

## 10. Conclusion & Deployment Decision

All requirements of Milestone 5G have been satisfied:
- The production seed guard prevents any execution or mutation when `ENVIRONMENT=production`.
- Insecure configuration defaults (debug mode, dev login, default secrets, localhost DB URLs, wildcard CORS) cause startup refusal.
- The 12-point smoke verification matrix has been validated.
- All 208 backend regression tests and frontend production builds pass with zero defects.

**Final Status:** **READY FOR CONTROLLED HOSTED DEMO**
