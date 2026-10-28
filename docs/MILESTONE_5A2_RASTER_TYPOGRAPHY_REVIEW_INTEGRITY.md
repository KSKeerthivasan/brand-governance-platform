# Milestone 5A.2 — Raster Typography Classification and Manual-Review Integrity Report

**Workspace:** `E:\CodeStar30`  
**Date:** October 28, 2026  
**Status:** Complete & Fully Verified  

---

## 1. Executive Summary & Rationale

During review of Milestone 5A.1, a core correctness gap was identified: bounding-box pixel height and Euclidean distance-transform stroke measurements from raster images were treated as sufficient proof to classify text as WCAG-qualified "large text" (granting an automatic 3.0:1 threshold pass).

In digital publishing and raster image governance:
- **Pixel height does not equal typographical point size ($pt$):** A $36\text{px}$ text box on a high-density 4K poster ($3840 \times 2160$) represents tiny, unreadable sub-body copy, whereas on a tiny banner ($300 \times 100$) it is a major display headline.
- **Estimated stroke width does not prove bold font weight:** A physical raster stroke width of $4\text{px}$ is an artifact of image resolution and antialiasing, not a certified typographical font weight ($\ge 700$).
- **Silent approval bypass:** Inconclusive measurements and unverified typography previously generated informational findings (`severity="info"`), which caused the governance run status to remain `"passed"` and allowed content to reach approval without reviewer awareness or mandatory recorded justifications.

Milestone 5A.2 resolved this correctness gap without rebuilding the accessibility subsystem:
1. Re-classified raster-only measurements as heuristic unverified estimates rather than certified WCAG typography.
2. Required trustworthy source typography metadata to apply the lenient $3.0:1$ large-text threshold.
3. Enforced the conservative $4.5:1$ threshold for all automatic passing decisions when source typography cannot be verified.
4. Elevated inconclusive measurements and borderline unverified typography ($3.0:1 \le \text{CR} < 4.5:1$) to `severity="warning"` and `status="unable_to_verify"`, ensuring they remain visible in the approval workflow and require a recorded reviewer justification before publication.

---

## 2. Typography Classification & Threshold Decision Hierarchy

```
                            OCR Region Evaluated
                                     │
           Does trustworthy source typography metadata exist?
      (e.g., is_known_large_text=True OR font_size_pt >= 18 OR bold >= 14pt)
                                     │
                    ┌────────────────┴────────────────┐
                   YES                                NO
                    │                                 │
                    ▼                                 ▼
         [verified_large_text]           [unverified_raster_estimate]
           Threshold: 3.0:1                   Threshold: 4.5:1
                                            (Conservative Baseline)
                    │                                 │
        ┌───────────┴───────────┐         ┌───────────┴───────────┐
        │                       │         │           │           │
     CR >= 3.0               CR < 3.0   CR >= 4.5  3.0<=CR<4.5  CR < 3.0
        │                       │         │           │           │
        ▼                       ▼         ▼           ▼           ▼
   Passed Check          Critical Blocker Passed    Review Req. Critical
    (info pass)          (verified_issue) Check      (warning)   Blocker
                                        (info pass)
```

### 2.1 Trustworthy Source Typography vs Heuristic Raster Estimates
- **Trustworthy Large Text (`verified_large_text`):**
  - Text region has documented source metadata establishing $\ge 18\text{pt}$ or $\ge 14\text{pt}$ bold (`is_known_large_text=True` or `typography_metadata`).
  - Applicable threshold: **$3.0:1$**.
  - Contrast $\ge 3.0:1$ passes with `status="passed_check"`, `severity="info"`.
  - Contrast $< 3.0:1$ fails with `status="verified_issue"`, `severity="critical"`.

- **Unverified Raster Estimates (`unverified_raster_estimate`):**
  - When no source metadata is attached, the bounding-box height and stroke thickness are recorded strictly as heuristic supporting evidence (e.g. `~70px height, stroke 6.6px; heuristic only, not verified typography`).
  - Applicable threshold for automatic decisions: **$4.5:1$** (conservative baseline).
  - Contrast $\ge 4.5:1$: Receives a **conservative pass** (`status="passed_check"`, `severity="info"`), noting that compliance does not depend on uncertified font size/weight assumptions.
  - Contrast $3.0:1 \le \text{CR} < 4.5:1$: **Does NOT receive an automatic pass**. It is flagged as `status="unable_to_verify"`, `severity="warning"`, requiring reviewer inspection.
  - Contrast $< 3.0:1$: Fails as `status="verified_issue"`, `severity="critical"` (violates both normal and large criteria).

---

## 3. Approval Workflow & Manual-Review Integrity

The four distinct outcome semantics are mapped to the platform's multi-tier approval gate:

| Outcome State | Contrast Level | Governance Status | Governance Severity | Approval Gate Effect | Reviewer Transparency |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Verified Contrast Failure** | $\text{CR} < 3.0:1$ | `verified_issue` | `critical` | **Hard Blocker.** Draft submission rejected; approval impossible under any override. | Displayed under "Unresolved Critical Blockers". |
| **Verified Large Text Pass** | $\text{CR} \ge 3.0:1$ (source confirmed) | `passed_check` | `info` | **Clean Pass.** Does not impede submission or approval. | Displayed under "Passed Checks". |
| **Conservative Pass** | $\text{CR} \ge 4.5:1$ (unverified raster) | `passed_check` | `info` | **Clean Pass.** Meets normal-text threshold regardless of font size. | Displayed under "Passed Checks". |
| **Unverified Typography Review** | $3.0:1 \le \text{CR} < 4.5:1$ (unverified raster) | `unable_to_verify` | `warning` | **Review Required.** Content may be submitted, but approval requires recorded justification comment ($\ge 10$ chars). | Displayed under "Warnings & Human Review Requirements". |
| **Inconclusive Measurement** | Low OCR confidence or unseparable strokes | `unable_to_verify` | `warning` | **Review Required.** Approval requires recorded justification comment ($\ge 10$ chars). | Displayed under "Warnings & Human Review Requirements". |

---

## 4. Verification Test Matrix

Twenty-six targeted tests in [test_milestone5a_localized_contrast.py](file:///E:/CodeStar30/backend/tests/test_milestone5a_localized_contrast.py) verify the system across all typography and approval scenarios:

1. `test_threshold_large_text_between_3_and_4_5_passes_large_criterion`: Confirmed large text ($3.4:1$) passes with `passed_check` and `info`.
2. `test_unknown_raster_typography_between_3_and_4_5_requires_manual_review`: Unknown raster typography ($70\text{px}$ bbox, $3.4:1$) does not pass automatically; emits `unable_to_verify` with `warning` severity.
3. `test_unknown_raster_typography_above_4_5_passes_conservative_threshold`: Unknown typography ($21:1$) passes conservative $4.5:1$ threshold with `passed_check` and `info`.
4. `test_threshold_normal_text_below_3_to_1_fails_critical` & `test_threshold_large_text_below_3_to_1_fails_critical`: Contrast below $3.0:1$ is consistently flagged as critical failure.
5. `test_inconclusive_separation_emits_warning_not_silent_pass`: Ambiguous text/background separation emits `unable_to_verify` and `warning` rather than a fabricated pass.
6. `test_raster_only_pixel_measurements_labeled_as_heuristic_estimates`: Verifies `unverified_raster_estimate` classification and notes.
7. `test_resolution_variation_does_not_forge_large_text_qualification`: Demonstrates that scaling an image $4\times$ ($30\text{px}$ vs $120\text{px}$ text height) at $3.4:1$ contrast consistently treats both as unverified raster estimates requiring review, rather than certifying the $120\text{px}$ box as WCAG large text.
8. `test_unresolved_accessibility_in_approval_workflow_requires_justification`: End-to-end integration test demonstrating that content with unverified contrast warnings sets governance status to `"warnings"`, blocks approval without justification (HTTP 400), and allows approval when a valid explanation is recorded (HTTP 200).

---

## 5. Actual Test Execution Results

### 5.1 Localized Contrast Test Suite
```bash
python -m pytest tests/test_milestone5a_localized_contrast.py -v
```
**Outcome:** **26 passed** in 32.29s (100% pass rate).

### 5.2 Full Backend Regression Suite
```bash
python -m pytest -q
```
**Outcome:** **133 passed** in 198.70s across all modules (approval workflow, content versioning, local OCR, context-aware rules, and tenant isolation).

### 5.3 Frontend Test Suite
```bash
npm test -- --run
```
**Outcome:** **3 test files passed, 9 tests passed** in 1.89s.

### 5.4 Frontend Production Build
```bash
npm run build
```
**Outcome:** **Exit code 0** in 448ms (`tsc -b && vite build` completed cleanly).

---

## 6. Known Limitations

1. **Standalone Raster Images Lack Typography Metadata:** Most public image formats (.png, .jpg, .webp) contain pixel matrices without CSS or vector font declarations. Unless upstream design tools export embedded metadata, images with contrast between $3.0:1$ and $4.5:1$ will appropriately require human reviewer confirmation.
2. **Extreme Kerning or Connected Scripts:** Script typefaces and cursive scripts where foreground strokes touch adjacent characters may yield minor variations in local background halo sampling. High background variance triggers inconclusive warnings rather than guessing.
3. **No Automated Font Licensing Check:** Automated checks inspect pixel contrast and readability, but cannot determine proprietary font licensing compliance.
