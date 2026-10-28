# Milestone 5D — Context-Preserving Correction Suggestions

**Status:** Completed  
**Workspace:** `E:\CodeStar30`  
**Applicable Milestones:** Milestone 1 through Milestone 5D  
**Database Migration:** `alembic/versions/b2c3d4e5f6a7_create_correction_suggestions.py` (`b2c3d4e5f6a7`)  
**Backend Test Suite:** `tests/test_milestone5d_correction_suggestions.py` (15/15 Passed)  
**Full Regression Suite:** 187/187 Tests Passed (0 Failures, 0 Regressions)  
**Browser E2E Recording:** [`m5d_correction_flow_1793199539963.webp`](file:///C:/Users/Keerthivasan%20K%20S/.gemini/antigravity-ide/brain/bdc72709-48b3-451c-8856-74f130e8093d/m5d_correction_flow_1793199539963.webp)  

---

## Executive Summary

Milestone 5D introduces an explainable, evidence-grounded correction suggestion engine into Inkloom AI's pre-publication brand governance platform. The engine assists marketing creators in resolving compliance findings across text drafts, raster posters, and multi-page PDF creative decks without inventing approved facts, silently rewriting creator content, suppressing governance findings, or bypassing reviewer approval gates.

Every correction suggestion is tied directly to a specific evaluated `ContentVersion`, its source SHA-256 checksum, and an explicit canonical brand rule or approved product fact. When creators accept an automated correction for editable body copy, an immutable new version (`v{N+1}`) is minted, prior governance results are marked stale/invalidated, and fresh governance evaluation is required before approval submission. For non-editable creative assets (raster PNG/JPEG posters and multi-page PDFs), the system provides precise visual remediation and authoring-tool guidance (`can_auto_apply = False`) without making fraudulent claims of automated image or document reconstruction.

---

## 1. Initial Audit Findings & Existing Architecture

Prior to implementing Milestone 5D, an audit of the existing codebase identified the following capabilities and boundaries:

| Subsystem | Existing Implementation | Milestone 5D Integration |
| :--- | :--- | :--- |
| **Governance Engine** | [`governance_engine.py`](file:///e:/CodeStar30/backend/app/services/governance_engine.py): Evaluates copy, poster OCR, and PDF pages against `KnowledgeRule` and `KnowledgeFact` tables. | Automatically invokes [`suggestion_service.py`](file:///e:/CodeStar30/backend/app/services/suggestion_service.py) upon completing a governance run to attach grounded suggestions to findings. |
| **Canonical Knowledge Base** | 21 canonical brand rules (`FR-RULE-001` through `FR-RULE-021`), 6 product SKUs (`FS-PROD-001` to `FS-PROD-006`), 13 claims, and brand assets. | Used exclusively as the ground-truth authority for replacements, insertions, and price/nutrition assertions. Never allows client-supplied or invented facts. |
| **Content Versioning** | [`ContentVersion`](file:///e:/CodeStar30/backend/app/models/content.py): Stores immutable `body_text`, `checksum` (SHA-256), `poster_file_path`, and `version_num`. | Accepting an automated suggestion mints a new `ContentVersion` record with updated checksum and increments `current_version_num`. Original versions and audit trails remain immutable. |
| **Artwork Governance** | Single-image raster posters (PNG/JPG/WEBP) and multi-page PDFs (PyMuPDF rendering with localized OCR and contrast). | Clearly demarcated as **non-editable artwork**. Suggestions for artwork provide visual remediation guidance (`can_auto_apply = False`), instructing creators to revise source files in Figma/InDesign and re-upload. |
| **Approval Gates** | Approval submissions require zero blocker findings and justification for warnings. | Accepting a suggestion never grants approval. Governance results for prior versions are invalidated, requiring a re-run on the newly minted version before submission. |

---

## 2. Supported Correction Categories & Evidence Grounding

The correction service strictly defines evidence requirements for 5 distinct categories:

### Category A: Terminology & Prohibited Wording
- **Evidence Requirement:** Exact rule match from canonical brand rules (`FR-RULE-005`, `FR-RULE-004`, `FR-RULE-006`, `FR-RULE-001`, `FR-RULE-010`, `FR-RULE-011`).
- **Correction Method:** Deterministic regex substitution preserving surrounding text, capitalization, and punctuation.
- **Example:**
  - *Original:* `"Freshsip Valencia Orange is 100% sugar-free, perfectly chilled for your morning breakfast."`
  - *Proposed:* `"Freshsip Valencia Orange is no added sugar (contains naturally occurring fruit sugars), perfectly chilled for your morning breakfast."`
  - *Evidence Citation:* `freshsip_brand_guidelines.pdf, Section C, p. 3`
  - *Confidence:* `high`, `can_auto_apply = True`.

### Category B: Promotional Claims & Product Facts
- **Evidence Requirement:** Approved product specifications (`freshsip_products.csv`) or approved marketing claims (`freshsip_approved_claims.csv`) strictly scoped to the target product SKU (`FS-PROD-001` through `FS-PROD-006`).
- **Scoping Safeguard:** Never substitutes SKU A claims for SKU B.
- **Unsupported Claims:** If an ad claims medical cures (e.g. `"cures cardiovascular disease"`), the system **never invents clinical evidence or certifications**. Instead, it generates a `manual_review` guidance suggestion recommending removal or substantiation request.
- **Pricing & Discounts:** Detects pricing contradictions against catalogue MRP (`FR-RULE-015`) and unapproved discount percentages (`FR-RULE-016`), grounding replacements in approved catalogue price points.

### Category C: Mandatory Disclosures & Required Terms
- **Evidence Requirement:** Canonical rule specifying mandatory wording (e.g. `FR-RULE-014` allergen & storage declaration for celery juice blend `FS-PROD-003`).
- **Correction Method:** Controlled insertion appended to body copy without duplicating existing declarations.
- **Placement Notice:** When applied to social captions, clearly notes that packaging and visual deck listings must also contain the disclosure.

### Category D: Tone, Voice & Context
- **Evidence Requirement:** Tone and brand voice guidelines (`FR-RULE-002`) prohibiting fear-based or sensationalist health claims (`"toxic sludge"`, `"poisoning your organs"`).
- **Correction Method:** Deterministic brand-aligned substitution replacing aggressive framing with positive, refreshing wording while preserving creator context.
- **No External LLM:** Implemented via deterministic mappings and explicit guidance; avoids black-box hallucination, paid API dependencies, and unverified equivalence claims.

### Category E: Visual, Contrast & Accessibility Remediation
- **Evidence Requirement:** Measured contrast ratios, pixel dimensions, colour palettes, and logo clearspace from [`image_governance.py`](file:///e:/CodeStar30/backend/app/services/image_governance.py).
- **Target Type:** `poster_image` or `pdf_page` (includes `page_number`).
- **Enforcement:** `can_auto_apply = False`. Clearly instructs creators that raster pixels cannot be safely rewritten in-place and requires revising source creative files in external tools.

---

## 3. Data Model & Architecture

### Schema Migration: `correction_suggestions` (`b2c3d4e5f6a7`)

```sql
CREATE TABLE correction_suggestions (
    id VARCHAR(36) PRIMARY KEY,
    finding_id VARCHAR(36) NOT NULL REFERENCES governance_findings(id) ON DELETE CASCADE,
    content_item_id VARCHAR(36) NOT NULL REFERENCES content_items(id) ON DELETE CASCADE,
    content_version_id VARCHAR(36) NOT NULL REFERENCES content_versions(id) ON DELETE CASCADE,
    source_checksum VARCHAR(64) NOT NULL,
    target_type VARCHAR(50) NOT NULL,            -- body_text, poster_image, pdf_page
    page_number INTEGER NULL,                    -- 1-indexed for PDF pages
    rule_id VARCHAR(36) NULL REFERENCES knowledge_rules(id) ON DELETE SET NULL,
    rule_code VARCHAR(50) NULL,
    fact_id VARCHAR(36) NULL REFERENCES knowledge_facts(id) ON DELETE SET NULL,
    fact_key VARCHAR(100) NULL,
    original_text TEXT NOT NULL,
    proposed_text TEXT NULL,
    diff_preview TEXT NULL,
    explanation TEXT NOT NULL,
    evidence_source VARCHAR(255) NOT NULL,
    correction_type VARCHAR(50) NOT NULL,        -- deterministic_replacement, mandatory_disclosure_insertion, factual_correction, tone_refinement, visual_remediation, manual_guidance
    confidence VARCHAR(20) NOT NULL DEFAULT 'high', -- high, medium, manual_review
    can_auto_apply BOOLEAN NOT NULL DEFAULT FALSE,
    status VARCHAR(50) NOT NULL DEFAULT 'pending', -- pending, accepted, rejected, stale, applied
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    resolved_at TIMESTAMP NULL
);
```

### Staleness & Integrity Invalidation

A suggestion becomes **stale** whenever:
1. The content item's `current_version_num` changes.
2. The evaluated `content_version_id` does not match the active draft version.
3. The SHA-256 checksum of the draft no longer matches `source_checksum`.

Attempting to accept a stale suggestion returns `HTTP 409 Conflict`:
```json
{
  "detail": "Suggestion is stale: content was modified after evaluation (checksum mismatch). Please run governance on the current version."
}
```

---

## 4. REST API Endpoints

| Method | Endpoint | Description | Access Control |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/v1/governance/runs/{version_id}/suggestions` | List all suggestions for a governance run | Member of content organization |
| `GET` | `/api/v1/governance/suggestions/{suggestion_id}` | Fetch a single suggestion with evidence | Member of content organization |
| `POST` | `/api/v1/governance/suggestions/{suggestion_id}/accept` | Accept and apply suggestion (mints new version if editable) | Creator or Admin role |
| `POST` | `/api/v1/governance/suggestions/{suggestion_id}/reject` | Reject suggestion without altering content | Creator or Admin role |
| `POST` | `/api/v1/governance/suggestions/{suggestion_id}/apply-custom` | Apply creator-customized replacement copy | Creator or Admin role |

---

## 5. Verification & Test Outcomes

### Focused Milestone 5D Regression Suite (`tests/test_milestone5d_correction_suggestions.py`)

All 15 specification-mandated test scenarios passed deterministically:

```
tests/test_milestone5d_correction_suggestions.py::test_1_exact_terminology_replacement_preserving_surrounding_text PASSED [  6%]
tests/test_milestone5d_correction_suggestions.py::test_2_required_disclosure_insertion_using_canonical_wording PASSED [ 13%]
tests/test_milestone5d_correction_suggestions.py::test_3_unsupported_claims_without_approved_replacement_never_receive_invented_facts PASSED [ 20%]
tests/test_milestone5d_correction_suggestions.py::test_4_product_and_sku_scoping_for_suggestions PASSED [ 26%]
tests/test_milestone5d_correction_suggestions.py::test_5_tone_or_messaging_suggestions_preserving_intended_factual_meaning PASSED [ 33%]
tests/test_milestone5d_correction_suggestions.py::test_6_suggestions_linked_to_finding_version_checksum_and_pdf_page PASSED [ 40%]
tests/test_milestone5d_correction_suggestions.py::test_7_stale_suggestions_rejected_after_content_or_checksum_changes PASSED [ 46%]
tests/test_milestone5d_correction_suggestions.py::test_8_explicit_acceptance_and_rejection_behaviour PASSED [ 53%]
tests/test_milestone5d_correction_suggestions.py::test_9_correct_version_creation_checksum_refresh_and_governance_invalidation PASSED [ 60%]
tests/test_milestone5d_correction_suggestions.py::test_10_governance_re_evaluation_after_an_applied_correction PASSED [ 66%]
tests/test_milestone5d_correction_suggestions.py::test_11_new_or_remaining_violations_after_a_correction_remain_visible PASSED [ 73%]
tests/test_milestone5d_correction_suggestions.py::test_12_critical_blockers_and_approval_gates_remain_intact PASSED [ 80%]
tests/test_milestone5d_correction_suggestions.py::test_13_pdf_and_raster_suggestions_not_falsely_claiming_to_modify_artwork PASSED [ 86%]
tests/test_milestone5d_correction_suggestions.py::test_14_tenant_isolation_role_enforcement_and_audit_history PASSED [ 93%]
tests/test_milestone5d_correction_suggestions.py::test_15_existing_text_image_pdf_accessibility_and_analytics_workflows PASSED [100%]

====================== 15 passed in 25.24s ======================
```

### Full Backend Suite Regression
```
187 passed, 2634 warnings in 269.71s (0:04:29)
```
- **Milestone 1:** Baseline ingestion & canonical repair (Passed)
- **Milestone 2:** Context-aware governance engine (Passed)
- **Milestone 3:** Local OCR & poster governance (Passed)
- **Milestone 4:** Approval workflow & integrity gates (Passed)
- **Milestone 5A:** Localized contrast & WCAG typography (Passed)
- **Milestone 5B:** Historical governance analytics & disposition integrity (Passed)
- **Milestone 5C:** Multi-page PDF creative deck governance (Passed)
- **Milestone 5D:** Context-preserving correction suggestions (Passed)

### Frontend Vitest & Production Build
```
 RUN  v5.0.5 E:/CodeStar30/frontend
 Test Files  3 passed (3)
      Tests  9 passed (9)
      
> tsc -b && vite build
✓ 1958 modules transformed.
dist/assets/index-TxSpNwyJ.js   497.08 kB │ gzip: 130.40 kB
✓ built in 332ms
```

---

## 6. Browser Verification

End-to-end browser verification was executed on the running frontend (`http://localhost:5173/content`):

1. **Draft Authoring:** Creator created `"Valencia Orange Sugar Free Campaign"` with body copy:
   `"Valencia Orange Cold-Pressed Juice is 100% sugar-free and revitalizes your day with pure organic citrus energy."`
2. **Initial Governance Evaluation:** Engine flagged critical finding `[FR-RULE-005] Prohibited Term Detected: '100% sugar-free'`.
3. **Suggestion Rendering:** Content Studio rendered the **Context-Preserving Correction** card:
   - Type: `Deterministic Replacement (High Confidence)`
   - Citation: `freshsip_brand_guidelines.pdf, Section C: Terminology Rules, p. 3`
   - Diff Preview: `- 100% sugar-free` / `+ no added sugar (contains naturally occurring fruit sugars)`
   - Action Buttons: `Accept & Create Revision`, `Edit Before Applying`, `Reject`
4. **Acceptance & Version Minting:** Clicked `Accept & Create Revision`. System minted `v3`, updated the editor textarea with compliant copy, displayed prior governance invalidation notice, and prompted re-evaluation.
5. **Re-evaluation:** Creator ran governance check on `v3` -> **PASSED with 0 findings**.
6. **Artifact Recording:** Browser session video recorded to [`m5d_correction_flow_1793199539963.webp`](file:///C:/Users/Keerthivasan%20K%20S/.gemini/antigravity-ide/brain/bdc72709-48b3-451c-8856-74f130e8093d/m5d_correction_flow_1793199539963.webp).

---

## 7. Files Modified & Created

### Backend
- [`backend/alembic/versions/b2c3d4e5f6a7_create_correction_suggestions.py`](file:///e:/CodeStar30/backend/alembic/versions/b2c3d4e5f6a7_create_correction_suggestions.py): Additive migration for `correction_suggestions` table.
- [`backend/app/models/content.py`](file:///e:/CodeStar30/backend/app/models/content.py): Added `CorrectionSuggestion` model and relationship on `GovernanceFinding`.
- [`backend/app/models/__init__.py`](file:///e:/CodeStar30/backend/app/models/__init__.py): Exported `CorrectionSuggestion`.
- [`backend/app/schemas/governance.py`](file:///e:/CodeStar30/backend/app/schemas/governance.py): Added suggestion request/response schemas.
- [`backend/app/services/suggestion_service.py`](file:///e:/CodeStar30/backend/app/services/suggestion_service.py): Core suggestion generation and lifecycle service.
- [`backend/app/services/governance_engine.py`](file:///e:/CodeStar30/backend/app/services/governance_engine.py): Fixed price comparison against approved price digits across caption, poster, and PDF pages.
- [`backend/app/api/v1/governance.py`](file:///e:/CodeStar30/backend/app/api/v1/governance.py): Suggestion retrieval, acceptance, rejection, and custom edit endpoints.
- [`backend/tests/test_milestone5d_correction_suggestions.py`](file:///e:/CodeStar30/backend/tests/test_milestone5d_correction_suggestions.py): 15 deterministic regression tests.

### Frontend
- [`frontend/src/types/index.ts`](file:///e:/CodeStar30/frontend/src/types/index.ts): Added `CorrectionSuggestion` interfaces.
- [`frontend/src/services/api.ts`](file:///e:/CodeStar30/frontend/src/services/api.ts): Added suggestion client methods (`getSuggestions`, `acceptSuggestion`, `rejectSuggestion`, `applyCustomSuggestion`).
- [`frontend/src/pages/ContentStudio.tsx`](file:///e:/CodeStar30/frontend/src/pages/ContentStudio.tsx): Suggestion card rendering, diff preview, artwork notices, staleness indicators, and custom-edit modal.

---

## 8. Known Limitations & Manual Intervention Boundaries

1. **Non-Editable Artwork Formats:** Raster posters (PNG/JPG/WEBP) and compiled PDF documents cannot have text rewritten in-place without corrupting design layout, kerning, and vector layers. These findings receive actionable remediation guidance (`can_auto_apply = False`) requiring creators to modify source creative files and re-upload.
2. **Unsubstantiated Clinical/Health Claims:** The engine never generates fictional medical or clinical claims. If marketing copy claims to cure diseases or guarantee weight loss without approved knowledge records, the suggestion requires manual reviewer action or copy removal.
3. **No External LLM Dependencies:** All suggestions are generated locally via deterministic rules and approved product catalogue facts, ensuring 100% reproducible, zero-cost, and private governance execution.
