# Milestone 5B: Historical Governance Analytics and Guideline Ambiguity Signals

**Platform:** Inkloom.AI Brand Governance Platform  
**Workspace:** `E:\CodeStar30`  
**Milestone:** 5B  
**Status:** Implemented, Deterministically Tested, and Verified  
**Date:** October 28, 2026  

---

## 1. Executive Summary

Milestone 5B elevates Inkloom.AI from an isolated, real-time check validator into a self-improving platform that learns from its recorded governance history. Rather than adding arbitrary decorative charts, this milestone establishes an evidence-grounded analytics and ambiguity feedback pipeline that enables knowledge managers, reviewers, and brand stewards to:

1. **Track governance performance:** Monitor overall governance runs, clean compliance pass rates, and violation severity distributions with mathematically strict denominators.
2. **Isolate repeated mistakes across content items:** Separate raw violation counts from distinct content drafts affected, preventing single heavily flawed drafts from distorting recurrence metrics.
3. **Capture structured reviewer dispositions:** Empower authorized reviewers to tag findings with standardized dispositions (`confirmed_issue`, `false_positive`, `guideline_unclear`, `conflicting_guidelines`, `insufficient_evidence`, `other`) backed by mandatory justification gates.
4. **Surface evidence-based guideline ambiguity signals:** Alert knowledge managers to vague, conflicting, or over-triggering rules based on reviewer feedback patterns and justified warning overrides—without automatically modifying canonical rules.

All existing subsystems from Milestones 1 through 5A.2—canonical knowledge facts, context-sensitive rules, local OCR, localized WCAG contrast thresholds, raster typography classifications, version integrity checksums, and reviewer approval gates—remain intact and 100% operational.

---

## 2. Pre-Implementation Codebase Audit

Before introducing schema or API changes, the codebase was audited to determine what historical governance data was already persisted and where gaps existed:

### 2.1 Existing Persisted Entities
- **Content Item & Version Tracking (`content_items`, `content_versions`):** Drafts have distinct UUIDs, organization boundaries, brands, channels (e.g. `instagram`, `web`, `email`, `print`), incremental `version_num`, and immutable SHA-256 `checksum`s.
- **Governance Runs (`governance_runs`):** Captures `overall_status` (`passed`, `warnings`, `failed`), `rules_evaluated_count`, `facts_evaluated_count`, `findings_count`, and execution timestamp `created_at`.
- **Governance Findings (`governance_findings`):** Captures `matched_rule_id`, `matched_fact_id`, `category`, `severity` (`critical`, `warning`, `info`), `title`, `explanation`, `text_excerpt`, and status (`unresolved`).
- **Approval Decisions (`approval_decisions`):** Captures `decision` (`approved`, `rejected`, `changes_requested`), `decided_by`, `comments`, and timestamps. Warning overrides are recorded when an item with warnings is approved with written justification.

### 2.2 Audit Findings & Gaps
1. **Raw Counts vs Distinct Content Items:** Previously, there was no aggregate view distinguishing repeated occurrences within a single document from recurring errors across separate marketing campaigns.
2. **Missing Reviewer Dispositions:** While approval managers could approve or reject submissions, there was no structured way to record whether a specific triggered rule was a genuine violation, an ambiguous guideline, a conflict with another policy, or an over-triggering false positive.
3. **Absence of Ambiguity Reporting:** Knowledge managers lacked aggregated visibility into which approved guidelines were generating reviewer friction, false positives, or repeated override justifications.

### 2.3 Minimal Additive Design
To address these gaps without fabricating historical data or resetting databases:
- Created an additive table: `reviewer_finding_dispositions` via safe Alembic migration `9b0c1d2e3f4a`.
- Reused all existing `governance_runs`, `governance_findings`, `content_items`, and `approval_decisions` records.
- Preserved legacy findings with null rule linkage without crashing analytics endpoints.

---

## 3. Metrics and Precise Definitions

Every metric displayed on the dashboard defines its exact mathematical formula and denominator:

| Metric | Formula | Denominator | Interpretation |
| :--- | :--- | :--- | :--- |
| **Total Governance Runs** | $\sum \text{runs}$ in filter window | N/A | Total execution volume of governance engine. |
| **Runs With Findings (%)** | $\frac{\text{Runs with } \ge 1 \text{ finding}}{\text{Total Runs}} \times 100$ | Total Runs | Proportion of checked drafts that flagged at least one violation or warning. |
| **Clean Runs Pass Rate (%)** | $\frac{\text{Runs with } 0 \text{ findings}}{\text{Total Runs}} \times 100$ | Total Runs | Proportion of checked drafts achieving a 100% clean compliance pass. |
| **Severity Distribution (%)** | $\frac{\text{Findings of Severity } S}{\text{Total Findings}} \times 100$ | Total Findings | Relative severity breakdown (`critical`, `warning`, `info`). |
| **Distinct Content Items Affected** | $\text{Count}(\text{distinct } \text{content\_item\_id})$ | Unique Content Items | Measures breadth of rule recurrence across drafts, avoiding multi-finding distortion. |
| **Recurrence Across Revisions** | $\text{Count}(\text{items with rule in } >1 \text{ version})$ | Unique Content Items | Identifies issues that persisted or resurfaced after an author attempted revision. |
| **False-Positive Rate (%)** | $\frac{\text{Dispositions: } \texttt{false\_positive}}{\text{Total Dispositions for Rule}} \times 100$ | Total Rule Dispositions | Proportion of reviewed rule triggers flagged as inaccurate by human reviewers. |

---

## 4. Evidence-Based Guideline Ambiguity Signals

A high violation count alone does **not** prove that a brand guideline is ambiguous; frequent violations often indicate effective rule enforcement or need for creator training.

To avoid false conclusions, ambiguity signals are computed exclusively from **empirical reviewer actions**:

### 4.1 Reviewer Finding Dispositions
Authorized reviewers can record structured feedback on any finding with one of six standardized dispositions:

| Disposition | Purpose | Justification Gate |
| :--- | :--- | :--- |
| `confirmed_issue` | Confirms accurate rule violation | Optional note |
| `false_positive` | Flags compliant content over-triggered | $\ge 10$ characters required |
| `guideline_unclear` | Flags guideline as vague or ambiguous | $\ge 10$ characters required |
| `conflicting_guidelines` | Identifies contradiction with another rule | $\ge 10$ characters required |
| `insufficient_evidence` | Notes rule lacks context or citation evidence | $\ge 10$ characters required |
| `other` | General reviewer observation | Optional note |

### 4.2 Ambiguity Scoring and Thresholds
The Knowledge Manager Ambiguity Report evaluates active rules against 5 evidence signals:
1. **Guideline Unclear Signal:** $\ge 1$ `guideline_unclear` disposition recorded.
2. **Conflicting Guidance Signal:** $\ge 1$ `conflicting_guidelines` disposition recorded.
3. **Elevated False-Positive Frequency:** $\ge 2$ false positive dispositions or $\ge 25\%$ false-positive rate among reviewed findings.
4. **Insufficient Rule Evidence:** $\ge 1$ `insufficient_evidence` disposition recorded.
5. **Frequent Warning Overrides:** $\ge 2$ instances where approval managers approved content with justified warning overrides against this rule.

**Ambiguity Score Formula:**
$$\text{Score} = (\text{Signals} \times 20) + (\text{Unclear} \times 15) + (\text{Conflicts} \times 25) + (\text{FalsePositives} \times 10)$$

- **High Ambiguity ($\text{Score} \ge 60$ or Conflicts $\ge 1$ or Unclear $\ge 2$):** High Priority: Knowledge Manager should review rule wording, define exceptions, and clarify pattern in Knowledge Library.
- **Medium Ambiguity ($\text{Score} \ge 30$ or FalsePositives $\ge 1$):** Medium Priority: Inspect rule examples and verify pattern precision against legitimate phrasing.
- **Low Ambiguity:** Monitor future reviewer feedback.

> [!IMPORTANT]
> Ambiguity reports represent **potential signals for human review**. The system **never** automatically modifies, deletes, or deactivates canonical rules based on analytics.

---

## 5. Architectural Implementation & Safeguards

### 5.1 Data Model Changes
- **Model:** `ReviewerFindingDisposition` in [`backend/app/models/content.py`](file:///e:/CodeStar30/backend/app/models/content.py).
  - Columns: `id`, `organization_id`, `governance_run_id`, `finding_id`, `rule_id`, `content_item_id`, `content_version_id`, `disposition`, `reviewer_id`, `explanation`, `created_at`.
  - Indexes: Explicit indexes on `organization_id`, `governance_run_id`, `finding_id`, `rule_id`, `content_item_id`, `content_version_id`.
  - Migration: `9b0c1d2e3f4a_add_reviewer_finding_dispositions.py`.

### 5.2 API Surface ([`backend/app/api/v1/analytics.py`](file:///e:/CodeStar30/backend/app/api/v1/analytics.py))
- `POST /api/v1/analytics/findings/{finding_id}/feedback`: Records reviewer disposition with role check, tenant verification, and explanation length validation.
- `GET /api/v1/analytics/findings/{finding_id}/feedback`: Fetches audit history of dispositions for a specific finding.
- `GET /api/v1/analytics/overview`: Aggregated run volumes, findings breakdown, and chronological activity.
- `GET /api/v1/analytics/repeated-mistakes`: Grouped recurrence analysis, distinct content items vs findings count, revision recurrences, and chronological trend signals (`increasing`, `decreasing`, `stable`, `insufficient_history`).
- `GET /api/v1/analytics/ambiguity-signals`: Knowledge Manager report surfacing flagged rules with supporting evidence quotes.

### 5.3 RBAC and Tenant Isolation
- **Role Enforcement:** Only `approval_manager`, `knowledge_reviewer`, and `org_admin` can submit finding dispositions. Content creators attempting to submit receive HTTP 403 Forbidden.
- **Tenant Isolation:** All queries filter by caller's `membership.organization_id`. Finding submission verifies parent content belongs to caller's organization; cross-tenant attempts return HTTP 404 Not Found.

### 5.4 Frontend Integration
- **Dashboard ([`frontend/src/pages/Dashboard.tsx`](file:///e:/CodeStar30/frontend/src/pages/Dashboard.tsx)):**
  - Added primary navigation tabs: **Governance Overview**, **Recurring Violations**, **Guideline Ambiguity Signals**.
  - Added filter bar: Date Range (All time, 7d, 30d, 90d), Channel (`instagram`, `print`, `web`, `email`), Severity (`critical`, `warning`, `info`).
  - Added drill-down panels to inspect rule citations, trend rationales, and reviewer quotes.
- **Reviewer Feedback Modal ([`frontend/src/components/FindingFeedbackModal.tsx`](file:///e:/CodeStar30/frontend/src/components/FindingFeedbackModal.tsx)):**
  - Integrated into [`frontend/src/pages/ApprovalQueue.tsx`](file:///e:/CodeStar30/frontend/src/pages/ApprovalQueue.tsx) on critical blockers, warnings, and informational findings.
  - Reviewers can select dispositions, submit minimum 10-character explanations, and view historical audit logs inline.

---

## 6. Verification and Test Results

### 6.1 Targeted Test Suite: `test_milestone5b_analytics.py`
Command:
```bash
python -m pytest tests/test_milestone5b_analytics.py -v
```
Results:
```
tests/test_milestone5b_analytics.py::test_01_historical_aggregates_and_denominators PASSED [ 10%]
tests/test_milestone5b_analytics.py::test_02_repeated_mistakes_distinct_content_items_distinction PASSED [ 20%]
tests/test_milestone5b_analytics.py::test_03_analytics_filters PASSED    [ 30%]
tests/test_milestone5b_analytics.py::test_04_trend_determination_with_insufficient_and_sufficient_history PASSED [ 40%]
tests/test_milestone5b_analytics.py::test_05_reviewer_feedback_recording_and_role_enforcement PASSED [ 50%]
tests/test_milestone5b_analytics.py::test_06_reviewer_feedback_justification_gate PASSED [ 60%]
tests/test_milestone5b_analytics.py::test_07_tenant_isolation_analytics_and_feedback PASSED [ 70%]
tests/test_milestone5b_analytics.py::test_08_guideline_ambiguity_signals_derived_from_evidence PASSED [ 80%]
tests/test_milestone5b_analytics.py::test_09_legacy_and_empty_records_handling PASSED [ 90%]
tests/test_milestone5b_analytics.py::test_10_existing_governance_and_approval_workflow_unbroken PASSED [100%]

====================== 10 passed in 1.34s =======================
```

### 6.2 Full Regression Test Suite
Command:
```bash
python -m pytest -q
```
Results:
```
143 passed, 1701 warnings in 78.38s (0:01:18)
```
**Outcome:** All 143 test cases across the entire platform passed with zero regressions.

### 6.3 Frontend Verification
- **Unit Tests:** `npm test -- --run` $\rightarrow$ 9 passed in 1.14s.
- **Production Build:** `npm run build` $\rightarrow$ built cleanly in 251ms.
- **Browser Subagent:** Verified active views, tabs, modal interaction, and RBAC persona switching on `http://localhost:5173/`.

---

## 7. Acceptance Criteria Evaluation

| Criterion | Status | Implementation Details |
| :--- | :--- | :--- |
| **1. Historical Aggregates & Denominators** | **Implemented** | Strict mathematical definitions: `runs_with_findings_pct` and `clean_runs_pct` explicitly use `total_runs` as denominator; severity percentages use `total_findings`. |
| **2. Findings vs Distinct Content Items** | **Implemented** | Multiple findings within one draft do not inflate distinct items affected count. |
| **3. Filters** | **Implemented** | Date range, channel, and severity filters update queries consistently across backend and frontend. |
| **4. Recurrence Trends & No Fabricated Trends** | **Implemented** | Rules with $< 3$ occurrences or narrow timeframes return `insufficient_history` with explanatory notes. |
| **5. Reviewer Feedback Mechanism** | **Implemented** | Reviewers can record `confirmed_issue`, `false_positive`, `guideline_unclear`, `conflicting_guidelines`, `insufficient_evidence`, `other`. |
| **6. Justification Gate** | **Implemented** | Dispositions challenging a rule enforce $\ge 10$ characters of explanation; rejects empty submissions with HTTP 400. |
| **7. Role Enforcement** | **Implemented** | Backend rejects content creators with HTTP 403 Forbidden; permits approval managers, knowledge reviewers, org admins. |
| **8. Tenant Isolation** | **Implemented** | Strict organization boundary enforcement across all queries; cross-tenant attempts return HTTP 404/403. |
| **9. Evidence-Based Ambiguity Signals** | **Implemented** | Ambiguity report derives signals from reviewer feedback and justified warning overrides, not violation counts alone. |
| **10. Legacy & Empty Record Handling** | **Implemented** | Endpoints handle null rule IDs, empty timeframes, and legacy data without crashing. |
| **11. Workflow Preservation** | **Implemented** | Version creation, checksum verification, OCR, contrast assessment, and approval gates remain 100% operational. |

---

## 8. Files and Migrations Changed

### Backend Files
- [`backend/app/models/content.py`](file:///e:/CodeStar30/backend/app/models/content.py) — Added `ReviewerFindingDisposition` model.
- [`backend/app/models/__init__.py`](file:///e:/CodeStar30/backend/app/models/__init__.py) — Exported `ReviewerFindingDisposition`.
- [`backend/alembic/versions/9b0c1d2e3f4a_add_reviewer_finding_dispositions.py`](file:///e:/CodeStar30/backend/alembic/versions/9b0c1d2e3f4a_add_reviewer_finding_dispositions.py) — Schema migration.
- [`backend/app/schemas/analytics.py`](file:///e:/CodeStar30/backend/app/schemas/analytics.py) — Schemas for dispositions, overview, recurrence, and ambiguity reports.
- [`backend/app/schemas/__init__.py`](file:///e:/CodeStar30/backend/app/schemas/__init__.py) — Exported analytics schemas.
- [`backend/app/api/v1/analytics.py`](file:///e:/CodeStar30/backend/app/api/v1/analytics.py) — Endpoints for feedback, overview, repeated mistakes, and ambiguity signals.
- [`backend/app/api/v1/__init__.py`](file:///e:/CodeStar30/backend/app/api/v1/__init__.py) — Registered analytics router with prefix `/analytics`.
- [`backend/tests/test_milestone5b_analytics.py`](file:///e:/CodeStar30/backend/tests/test_milestone5b_analytics.py) — Comprehensive 10-test verification suite.

### Frontend Files
- [`frontend/src/types/index.ts`](file:///e:/CodeStar30/frontend/src/types/index.ts) — TypeScript interfaces for dispositions and analytics.
- [`frontend/src/services/api.ts`](file:///e:/CodeStar30/frontend/src/services/api.ts) — API client methods for analytics endpoints.
- [`frontend/src/components/FindingFeedbackModal.tsx`](file:///e:/CodeStar30/frontend/src/components/FindingFeedbackModal.tsx) — Reviewer disposition modal with validation and audit history.
- [`frontend/src/pages/ApprovalQueue.tsx`](file:///e:/CodeStar30/frontend/src/pages/ApprovalQueue.tsx) — Wired feedback triggers to all findings.
- [`frontend/src/pages/Dashboard.tsx`](file:///e:/CodeStar30/frontend/src/pages/Dashboard.tsx) — Three-tab historical analytics dashboard with filters and drilldown.

### Documentation
- [`docs/MILESTONE_5B_HISTORICAL_GOVERNANCE_ANALYTICS.md`](file:///e:/CodeStar30/docs/MILESTONE_5B_HISTORICAL_GOVERNANCE_ANALYTICS.md) — Comprehensive milestone report.

---

## 9. Conclusion

Milestone 5B successfully closes the feedback loop between content reviews and brand knowledge management. Historical governance runs provide clear violation visibility; repeated mistakes are accurately isolated across distinct content items; and reviewer dispositions surface actionable ambiguity signals that help brand stewards refine canonical guidelines based on empirical evidence.
