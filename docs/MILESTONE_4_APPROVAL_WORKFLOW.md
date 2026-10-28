# Milestone 4 — Fail-Closed Approval Workflow, Version Integrity and Reviewer Transparency

**Date:** October 28, 2026  
**Workspace:** `E:\CodeStar30`  
**System:** Brand Governance Platform — Inkloom  
**Author:** AI Agent (Antigravity) & Pair Programmer  

---

## 1. Verified Preflight Findings

Before making modifications for Milestone 4, the existing implementation across the backend models, APIs, and frontend review workflow was audited against the Milestone 1–3 baselines:

1. **Submission Bypass Vulnerability:**
   - In `app/api/v1/approvals.py`, `POST /api/v1/approvals/submit` allowed content creators to submit content drafts without ever executing a governance check or even if unresolved critical violations existed.
   - Status checks only verified `item.status != 'submitted'`. No precondition bound submission eligibility to a passing governance run.

2. **Decisions Lacked Version Binding:**
   - Decisions (`POST /api/v1/approvals/submissions/{id}/decide`) updated `content_item.status = decision`, but did not assert that the reviewed version was still the current version of the content item.
   - If a creator edited the body or changed posters while a submission was pending, the manager's approval would inadvertently approve the newer, un-reviewed version.

3. **Context Modification Version Invalidation Gap:**
   - In `app/api/v1/content.py`, `PUT /api/v1/content/{id}` only created a new version if `body_text` changed or `poster_file_path`/`poster_asset_id` changed. Modifying `channel` or `title` updated the record in-place without incrementing `version_num`, allowing channel-specific governance bypasses.

4. **Reviewer Visibility Limitations:**
   - `ApprovalSubmissionOut` returned only `content_item_title`, `body_text`, `checksum`, and `poster_file_path`.
   - The approval queue did not expose governance run results, rule citations, OCR bounding boxes/confidence scores, or categorized findings to the reviewing manager. Reviewers were expected to make blind decisions or navigate away to other screens.

5. **Investigation of the 60% OCR Confidence Threshold:**
   - The rapidocr confidence threshold configured at `0.60` (60%) was investigated.
   - **Finding:** The threshold was established as an operational heuristic during Milestone 3 implementation. High-contrast test posters score 96%–99%, whereas synthetic noise/blurred fixtures score under 40%–55%. However, it has **not** been formally benchmarked against an externally labelled, representative dataset across varied fonts, lighting, and compressions.
   - **Documented Status:** The 60% threshold is officially documented as a **provisional operational heuristic**, and is not presented as an independently validated accuracy threshold.

6. **Baseline Test Results:**
   - Backend prior to edits: **81 passed**, 0 failed.
   - Frontend tests: **9 passed**, 0 failed (`npm test -- --run`).
   - Frontend build: **Succeeded** (`tsc -b && vite build`).

---

## 2. Files Modified and Why

| File | Type | Reason for Modification |
|---|---|---|
| `backend/app/schemas/approval.py` | Schema | Enriched `ApprovalSubmissionOut` with `channel`, `governance_run_id`, `governance_status`, `rules_evaluated_count`, `facts_evaluated_count`, `findings_count`, `critical_findings_count`, `warning_findings_count`, `info_findings_count`, and `findings` list. |
| `backend/app/api/v1/content.py` | API | Updated `update_content_item` so changing `channel` or `title` creates a new version (`version_num + 1`), resets status to `draft`, and invalidates prior governance runs. |
| `backend/app/api/v1/approvals.py` | API | Implemented fail-closed submission preconditions (P1–P6), role-based decision invariants, checksum verification, hard block on critical violations, and mandatory written justification for warning overrides. |
| `frontend/src/types/index.ts` | Types | Added governance findings and counts to `ApprovalSubmission` and added `ocr_confidence`, `bounding_box`, `is_blocker` to `GovernanceFinding`. |
| `frontend/src/pages/ApprovalQueue.tsx` | UI | Full reviewer transparency overhaul: displays grouped findings (blockers, warnings, info), rule codes, exact citations, text excerpts, OCR metrics with provisional disclaimer, disables approve button on critical blockers, and enforces warning override rationale. |
| `backend/tests/conftest.py` | Tests | Added `db_session` fixture to support database-level transaction integrity and tampering tests. |
| `backend/tests/test_approval_workflow.py` | Tests | Updated existing approval tests to execute governance checks prior to submitting compliant content. |
| `backend/tests/test_content_versions.py` | Tests | Updated version lifecycle tests to satisfy newly enforced fail-closed submission preconditions. |
| `backend/tests/test_poster_governance_integration.py` | Tests | Added governance run on `v2` before submission in the multi-version visual test. |
| `backend/tests/test_milestone4_approval_regression.py` | Tests | Created comprehensive 20-test regression suite covering all Section 7 requirements. |
| `backend/tests/test_milestone4_workflow_scenarios.py` | Tests | Created automated workflow tests for Scenarios A through F. |

---

## 3. Approval Preconditions and Blocker Semantics

### Server-Side Preconditions for Submission (`POST /api/v1/approvals/submit`)
The backend API enforces six fail-closed gates before creating a pending approval submission:

1. **Version Staleness Gate:**
   - `version.version_num == item.current_version_num`. Obsolete versions (e.g. v1 when draft has moved to v2) are rejected with HTTP 400.
2. **On-Disk Checksum Integrity Gate:**
   - Re-computes SHA-256 over `(body_text + poster_file_bytes)`. If current hash differs from `version.checksum`, rejected with HTTP 400 (`Integrity Checksum Mismatch`).
3. **Completed Governance Run Exists:**
   - Queries `GovernanceRun` for `content_version_id == version.id`. If no run exists, rejected with HTTP 400 (`No completed governance run exists for content version`).
4. **Exact Version Binding:**
   - Governance result must belong to the exact `content_version_id`. An older run cannot authorize a newer version.
5. **No Unresolved Critical Blockers:**
   - Findings with `severity in ("critical", "high")` and `status != "passed_check"` cause immediate rejection with HTTP 400, detailing the exact rule code, title, and violation excerpt.
6. **No Failed Governance Execution:**
   - If `latest_run.overall_status == "failed"`, submission is rejected.

### Decision Policy & Blocker Semantics (`POST /api/v1/approvals/submissions/{id}/decide`)
- **Critical Prohibitions:** Prohibited health claims (e.g. `detox`, `cure`), fabricated organic certifications, or unauthorized price discounts are **Hard Blockers**. They cannot be overridden by any user, including the Approval Manager. The approve button is disabled in the UI and hard-rejected with HTTP 400 in the API.
- **Warning Overrides:** Warning findings (e.g. non-standard image dimensions, alt-text warnings, or minor context deviations) may be approved only if the Approval Manager provides a substantive written justification (minimum 10 non-whitespace characters) explaining why the exception is acceptable.
- **Rejections & Change Requests:** Explicit comments explaining the required revisions are strictly required.

---

## 4. Content-Version and Asset-Integrity Checks

- **Snapshot Invariance:** Each `ContentVersion` stores the immutable `body_text`, `poster_file_path`, `poster_asset_id`, `poster_alt_text`, and SHA-256 `checksum`.
- **Invalidation Trigger:** Any call to `PUT /api/v1/content/{id}` that modifies `body_text`, `poster_file_path`, `poster_asset_id`, `title`, or `channel`:
  1. Increments `current_version_num` by 1.
  2. Resets `status` to `draft`.
  3. Creates a new immutable `ContentVersion` record with a newly computed SHA-256 hash.
  4. Automatically invalidates prior governance runs, requiring a fresh check on the new version.
- **Tampering & In-Flight Protection:**
  - Before an approval decision is committed, the backend re-validates the on-disk checksum of the asset and body against `version.checksum`. Out-of-band file replacements or direct database modifications are caught immediately.

---

## 5. Reviewer Visibility and Role Enforcement

### Multi-Tenant & Role Isolation
- **Tenant Isolation:** Enforced via `organization_id` filters on all database queries. Requests from another tenant with a mismatched `X-Organization-Id` return HTTP 403/404.
- **Conflict of Interest Gate:** Creators cannot approve their own submissions (`submission.submitted_by == current_user.id`). Attempting self-approval returns HTTP 403 (`Conflict of Interest`).
- **Authority Gate:** Only users with `role == "approval_manager"` (Marcus Manager) can record approval decisions. Other roles (`content_creator`, `knowledge_reviewer`, `org_admin`) receive HTTP 403 (`Permission Denied`).

### Approval Queue Transparency Features
In `frontend/src/pages/ApprovalQueue.tsx`, reviewers now inspect:
1. **Header & Context:** Content title, brand, channel, submission timestamp, and submitter name.
2. **Immutable Version Lock Pill:** Version number and full SHA-256 hash.
3. **Creative Asset & Copy Side-by-Side:** Live image rendering and full text copy.
4. **Governance Evidence Inspector:**
   - Active rules evaluated and facts checked count.
   - **Critical Blockers:** High-visibility red cards displaying rule code, rule title, violation explanation, verbatim violation excerpt, OCR confidence (with provisional heuristic tag), bounding box coordinates, source citation (e.g., *Freshsip Brand Guidelines page 5*), and recommended action.
   - **Warnings:** Amber cards detailing overrideable issues with required follow-up action.
   - **Informational:** Blue/gray cards highlighting passed contextual checks.
   - **Clean Pass Banner:** Green shield indicator when 0 violations or warnings exist.
5. **Decision Form:** Dynamic justification requirements, conflict-of-interest warnings, and disabled approve button with explanatory tooltips when critical blockers exist.

---

## 6. Audit Trail Behaviour

Every state change across the approval workflow emits an immutable `AuditEvent`:
- `APPROVAL_SUBMITTED`: Records submitter user ID, content version, version number, governance run ID, and findings count.
- `APPROVAL_DECIDED`: Records deciding manager user ID, submission ID, content version, decision (`approved`, `rejected`, `changes_requested`), decision label, and reviewer comments/justification.
- Historical submissions and decisions remain permanently attached to their historical versions and are never deleted or rewritten when content is edited.

---

## 7. Before-and-After Test Results

### Test Execution Summary

| Test Suite | Pre-Milestone 4 | Post-Milestone 4 | Status |
|---|---|---|---|
| Existing Backend Suite (`pytest -q`) | 81 passed | 81 passed | **PASS** |
| Milestone 4 Regression Suite (`test_milestone4_approval_regression.py`) | N/A | 20 passed | **PASS** |
| Milestone 4 Scenarios Suite (`test_milestone4_workflow_scenarios.py`) | N/A | 6 passed | **PASS** |
| **Total Backend Test Suite** | **81 passed** | **107 passed** | **100% PASS** |
| Frontend Vitest Suite (`npm test -- --run`) | 9 passed | 9 passed | **PASS** |
| Frontend Production Build (`npm run build`) | Built (436 kB) | Built (439 kB) | **PASS (0 errors)** |

### Exact Commands Run
```bash
# 1. Targeted Milestone 4 Regressions (20 tests)
pytest tests/test_milestone4_approval_regression.py -v
# Result: 20 passed in 22.05s

# 2. Workflow Scenarios A-F (6 tests)
pytest tests/test_milestone4_workflow_scenarios.py -v
# Result: 6 passed in 22.71s

# 3. Complete Backend Suite (107 tests)
pytest -q
# Result: 107 passed, 1415 deprecation warnings in 210.07s

# 4. Frontend Vitest Suite
npm test -- --run
# Result: 3 test files passed, 9 tests passed in 1.28s

# 5. Frontend Production Bundle Build
npm run build
# Result: vite v8.3.5 built client environment for production in 360ms
```

---

## 8. End-to-End Scenarios Actually Executed

Automated end-to-end tests were executed and validated in `tests/test_milestone4_workflow_scenarios.py`:

- **Scenario A — Compliant Content:**
  - *Journey:* Created Valencia Orange Cold-Pressed Juice draft -> Attached clean poster -> Ran governance (status `passed`) -> Submitted for approval -> Inspected queue as Approval Manager -> Approved with comments -> Verified content status transitioned to `approved` with official label `Approved — Ready to Publish`.
- **Scenario B — Prohibited Claim:**
  - *Journey:* Created poster with `48-Hour Detox Cleanse` -> Ran governance -> RapidOCR detected `detox` -> Critical blocker `FR-RULE-008` raised -> Attempted submission -> Server rejected with HTTP 400 (`Submission Rejected: Content version v1 contains 1 unresolved blocking violation(s)`).
- **Scenario C — Revision After Review:**
  - *Journey:* Ran governance on v1 -> Edited copy to v2 -> Attempted submission of v2 -> Server rejected with HTTP 400 (stale ungoverned version) -> Re-ran governance on v2 -> Submitted v2 -> Successfully submitted bound to version 2 checksum.
- **Scenario D — Uncertain Evidence:**
  - *Journey:* Attached low-contrast blurred graphic -> Ran governance -> OCR uncertainty recorded in findings -> Verified draft was not treated as a clean pass.
- **Scenario E — Reviewer Permissions:**
  - *Journey:* Content Creator submitted draft -> Content Creator attempted self-approval -> Server returned HTTP 403 (`Conflict of Interest`). Reviewer from foreign tenant attempted approval -> Server returned HTTP 403 (`Permission Denied`).
- **Scenario F — Rejection and Resubmission:**
  - *Journey:* Submitted v1 -> Approval Manager rejected v1 with specific tone feedback -> Creator revised to v2 -> Re-ran governance on v2 -> Resubmitted v2 -> Approval Manager approved v2 -> Verified both v1 rejection and v2 approval decisions remain permanently accessible in audit history.

---

## 9. Remaining Limitations and Policy Decisions

1. **OCR Confidence Threshold:**
   - The 60% confidence threshold is operational and provisional. While effective for synthetic test fixtures and standard marketing posters, it has not been validated against a labelled benchmark of real-world photography and distorted typography.
2. **Warning Justification Minimum Length:**
   - The minimum justification length is configured at 10 characters as a policy heuristic to prevent accidental single-word approvals (e.g. "ok"). Organizations may wish to enforce structured reason codes in future policy iterations.
3. **Offline OCR Performance:**
   - RapidOCR runs locally on CPU via ONNX Runtime without external cloud calls. Full test suites running multiple OCR checks take ~20–30 seconds. Production deployments with GPUs will achieve sub-second OCR latency.

---

## 10. Confirmation of Record Preservation and Tree Integrity

- **Database Integrity:** No historical content records, audit logs, or seed rules were reset or deleted.
- **Git Working Tree:** All pre-existing user modifications across other files and documentation were strictly preserved.
- **Aesthetic & UX Continuity:** The Dark Mode glassmorphic theme and component structure in `ApprovalQueue.tsx` were preserved, enhancing reviewer transparency without disruptive redesigns.
