# Inkloom AI — Brand Governance & Content Integrity Platform

> **Hackathon MVP Deliverable**: A standalone pre-publication brand-governance and content-integrity workspace with deterministic rule validation, version-aware revision history, and human-in-the-loop approval workflows.

---

## 🚀 Overview

**Inkloom AI** empowers organizations to upload brand guidelines, product specifications, and creative assets, inspect extracted candidate rules, and evaluate marketing copy against verified truth before publication.

Unlike black-box generative linters that hallucinate policies, Inkloom AI uses a **modular deterministic governance engine** that produces explainable findings tied directly to verified document sources or explicitly reports missing evidence.

---

## 🌟 The Three Declared Round 3 Improvements

1. **Improvement 1 — Stronger Evidence-Linked Findings**:
   - Traceable source citations (`freshsip_brand_guidelines.pdf, p. 4`).
   - Explicit reporting for unsupported claims: `source_citation: "SUPPORTING EVIDENCE NOT FOUND"`. Never fabricates citations.
   - Context-sensitive negation detection (e.g., "not a miracle cure" avoids false positives).
2. **Improvement 2 — Reliable Version-Aware Review and Approval**:
   - Cryptographic SHA-256 version checksums on every saved draft revision.
   - Human approvals are permanently bound to the exact submitted version.
   - Editing submitted or approved content creates a new version and resets status to `draft` (no inherited approvals).
   - Official completion state label: **"Approved — Ready to Publish"**.
   - Strict separation of duties: Content creators cannot approve their own copy.
3. **Improvement 3 — Static-Image Governance**:
   - On-disk Pillow (PIL) parsing of brand assets and campaign creatives.
   - Channel aspect-ratio validation (Instagram 1:1, Story 9:16, Web 16:9).
   - Color mode inspection (sRGB for screen vs CMYK for print).
   - Logo clearspace perimeter isolation checks.
   - Mandatory alt-text accessibility validation for screen-readers.

---

## 🛠️ Technology Stack

- **Frontend**: React 19, TypeScript, Vite, React Router, Lucide Icons, Custom Design System
- **Backend**: Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2.0, Alembic, Native Bcrypt, PyJWT
- **Database**: PostgreSQL 18 (with automatic zero-friction SQLite fallback for local development)
- **Document & Media Extraction**: PyPDF (PDF text parsing), Pillow (image inspection)
- **Automated Testing**: Pytest (backend), Vitest (frontend)

---

## 📊 Completed Feature Matrix

| Feature Area | Status | Verification |
|---|---|---|
| **Authentication & RBAC** | ✅ Complete | 4 roles (`org_admin`, `knowledge_reviewer`, `content_creator`, `approval_manager`) enforced by backend |
| **Tenant Isolation** | ✅ Complete | Cross-organization access denied via `X-Organization-Id` middleware |
| **Knowledge Upload & Extraction** | ✅ Complete | PyPDF parsing of PDF guidelines into pending candidate rules and facts |
| **Human Knowledge Review** | ✅ Complete | Reviewers approve/reject candidate rules before engine evaluates them |
| **Content Studio & Versioning** | ✅ Complete | Draft creation, immutable revision history, and SHA-256 checksums |
| **Deterministic Governance Engine** | ✅ Complete | Prohibited wording, fact mismatches, mandatory terms, unsupported claims |
| **Explainable Findings** | ✅ Complete | Findings with severity, excerpt, document citation, and next actions |
| **Approval Workflow** | ✅ Complete | Version-locked approval queue with "Approved — Ready to Publish" label |
| **Anti-Self-Approval** | ✅ Complete | Creators cannot approve their own submissions (`HTTP 403`) |
| **Static-Image Governance** | ✅ Complete | Aspect ratio, color space, logo clearance, and alt-text checks |
| **Live Audit History** | ✅ Complete | Chronological audit log of all uploads, edits, checks, and approvals |
| **Freshsip Demonstration Seed** | ✅ Complete | Idempotent synthetic demo dataset ready for immediate testing |

---

## 🧪 Test Results (100% Passing)

### Backend Pytest Suite
```
tests/test_auth_permissions.py ......                    [PASS]
tests/test_governance_engine.py ......                   [PASS]
tests/test_content_versions.py ......                    [PASS]
tests/test_approval_workflow.py ......                   [PASS]
tests/test_image_governance.py ......                    [PASS]
tests/test_e2e_freshsip_scenario.py ......               [PASS]

====================== 15 passed in 1.84s ======================
```

### Frontend Vitest Suite
```
src/tests/StatusBadge.test.tsx ...                       [PASS]
src/tests/api.test.ts ...                                [PASS]

====================== 4 passed in 0.89s ======================
```

---

## ⚡ Quick Start

### 1. Backend Server
```powershell
cd backend
pip install -r requirements.txt
python -m alembic upgrade head
python seed.py
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```
Backend API will be live at `http://127.0.0.1:8000` (Docs at `/docs`).

### 2. Frontend Web App
```powershell
cd frontend
npm install
npm run dev
```
Frontend will be live at `http://localhost:5173`.

---

## 👥 Seed Demo Personas (Password for all: `Freshsip2026!`)

- **Chris Creator** (`creator@freshsip.demo`): Authors drafts, runs checks, submits for approval.
- **Rachel Reviewer** (`reviewer@freshsip.demo`): Uploads brand guidelines, reviews candidate facts.
- **Marcus Manager** (`approver@freshsip.demo`): Approves submissions with official sign-off.
- **Alice Administrator** (`admin@freshsip.demo`): Workspace settings and team role assignment.

*(Judges can use the 1-click **"Persona"** dropdown in the web app header to instantly switch roles without re-authenticating).*

---

## ⚠️ Known Limitations & Planned Enhancements
- **Multi-lingual Brand Rules**: Current deterministic pattern matching targets English guidelines. Multi-lingual tokenization is planned for post-MVP.
- **Complex Vector PDF Graphics**: Vector graphics (SVG/EPS) are validated by dimensions and metadata; full vector curve extraction is planned for enterprise phase.
- **Cloud Object Storage**: Local private storage is used by default; Supabase S3 storage adapter is implemented and can be activated via environment variables.
