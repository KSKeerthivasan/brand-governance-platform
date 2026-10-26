# Inkloom AI — The Three Declared Round 3 Improvements

This document details the design, implementation, and verified test results for the three improvements declared in the Round 1 proposal and delivered in Round 3.

---

## Improvement 1: Stronger Evidence-Linked Findings

### Problem Addressed
Generic compliance linters and LLM-based checkers frequently produce "hallucinated" citations, ambiguous explanations, or false-positive alarms by flagging words out of context (e.g., flagging "not a miracle cure" as a violation).

### Technical Implementation
1. **Traceable Knowledge Citations**:
   - Every finding produced by the governance engine references the exact approved source document and page number (e.g., `freshsip_brand_guidelines.pdf, p. 4`).
2. **Explicit Missing Evidence Handling**:
   - When promotional or health claims lack verification in the knowledge base, the engine explicitly reports:
     `source_citation: "SUPPORTING EVIDENCE NOT FOUND"`.
   - The platform never fabricates or infers citations.
3. **Context-Sensitive Matching**:
   - The deterministic engine inspects preceding lexical tokens for negations (e.g., `not`, `never`, `no`, `without`, `isn't`).
   - If a prohibited keyword is detected within a negated context, the severity is downgraded from `critical` to `warning`, and an explainable note is appended advising human reviewer inspection rather than throwing a false-positive blocker.
4. **Automated Verification**:
   - Verified via `tests/test_governance_engine.py`:
     - `test_governance_detects_prohibited_words_and_citations` (PASSED)
     - `test_governance_detects_unsupported_health_claims` (PASSED)
     - `test_governance_detects_product_fact_mismatch` (PASSED)

---

## Improvement 2: Reliable Version-Aware Review & Approval

### Problem Addressed
In traditional review workflows, content is frequently edited *after* manager sign-off, silently inheriting approvals for unauthorized copy. Alternatively, edits to drafts mutate existing versions, corrupting historical auditability.

### Technical Implementation
1. **Cryptographic Version Identity**:
   - Every content revision generates an immutable `ContentVersion` entity with an automated SHA-256 checksum computed over the exact body text.
2. **Approval Version Locking**:
   - `ApprovalSubmission` and `ApprovalDecision` records bind strictly to a specific `content_version_id` and its checksum.
   - An Approval Manager can only approve the exact submitted revision.
3. **No Approval Inheritance**:
   - If a creator edits an item that has been submitted or approved, the engine creates a new version (`v_{n+1}`), resets the status back to `draft`, and forces a complete re-run of governance checks.
4. **Separation of Duties (Anti-Self-Approval)**:
   - Backend authorization explicitly prohibits a content creator from approving their own submission (`HTTP 403 Conflict of Interest`), enforced regardless of UI state.
5. **Standardized State Labeling**:
   - Successful approvals issue the official label: **"Approved — Ready to Publish"**, clarifying that governance sign-off does not imply automated publication.
6. **Automated Verification**:
   - Verified via `tests/test_content_versions.py` and `tests/test_approval_workflow.py`:
     - `test_content_versioning_and_checksum` (PASSED)
     - `test_editing_submitted_content_resets_status_and_creates_new_version` (PASSED)
     - `test_creator_cannot_approve_own_content` (PASSED)
     - `test_approval_manager_approves_submission_with_official_label` (PASSED)

---

## Improvement 3: Static-Image Governance

### Problem Addressed
Brand guidelines govern visual assets (logos, campaign images, color profiles) and accessibility, not merely text. Non-compliant aspect ratios, incorrect print color modes, and missing alt-text often escape governance until post-launch.

### Technical Implementation
1. **Static-Image Governance Engine (`ImageGovernanceService`)**:
   - Automated inspection of image resolution, aspect ratios, and color spaces using on-disk Pillow (PIL) parsing.
2. **Channel-Specific Standards**:
   - **Instagram Post**: Checks minimum 1080x1080px and 1:1 aspect ratio.
   - **Instagram Story**: Checks minimum 1080x1920px and 9:16 aspect ratio.
   - **Website Banner**: Checks minimum 1200x675px and 16:9 aspect ratio.
   - **Print Ad**: Validates that asset uses `CMYK` color space rather than screen RGB.
3. **Logo Isolation & Clearspace Perimeter**:
   - Detects logo assets and verifies compliance with minimum clearspace perimeter standards (e.g., 24px clearspace perimeter around logos to prevent headline collision).
4. **Accessibility Compliance (Alt-Text)**:
   - Enforces descriptive screen-reader alternative text. Flags missing or deficient alt-text as an accessibility compliance deficiency.
5. **Automated Verification**:
   - Verified via `tests/test_image_governance.py`:
     - `test_image_governance_alt_text_and_dimensions` (PASSED)
   - Tested in browser via the **Image Governance Studio** UI.
