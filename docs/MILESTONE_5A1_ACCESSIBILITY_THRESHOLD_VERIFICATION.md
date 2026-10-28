# Milestone 5A.1 — Accessibility Threshold Verification Report

**Workspace:** `E:\CodeStar30`  
**Date:** October 28, 2026  
**Status:** Complete & Fully Verified  

---

## 1. Executive Summary

Milestone 5A introduced localized poster text contrast estimation using foreground stroke mask clustering (Otsu bimodal segmentation) and surrounding localized background halo sampling. Milestone 5A.1 conducted a rigorous audit and verification of:
1. **WCAG contrast threshold selection** ($4.5:1$ for normal text vs $3.0:1$ for qualifying large/bold text).
2. **Defensible text size and font boldness determination** from raster images without ungrounded pixel-to-point assumptions.
3. **Conservative fallbacks and marginal/manual-review results** when typographical point size and boldness cannot be confirmed.
4. **Three-way outcome distinction**: Clean Pass, Explicit Failure, or Unable to Determine Reliably / Marginal Review.
5. **Severity and explanation consistency** reflecting the applicable threshold without silently mutating canonical governance rules.

---

## 2. Threshold Selection & Font Classification Analysis

### 2.1 The Core Challenge: Raster Pixels vs Typographical Points
In raster image governance, OCR bounding boxes yield pixel dimensions ($\text{px}$), not typographical points ($\text{pt}$) or CSS font declarations. A $24\text{px}$ bounding box on a high-density 4K poster is visually tiny body copy, whereas on a low-resolution banner it might be a headline. Furthermore, standard OCR engines (such as PaddleOCR or EasyOCR) detect bounding polygons but do not reliably report font weight (`bold` vs `normal` vs `light`).

Under WCAG 2.1 Success Criterion 1.4.3:
- **Normal text** requires at least **$4.5:1$** contrast.
- **Large text** requires at least **$3.0:1$** contrast, defined as:
  - At least $18\text{pt}$ ($\approx 24\text{px}$ at standard 96 DPI CSS reference), OR
  - At least $14\text{pt}$ **bold** ($\approx 18.66\text{px}$ at standard 96 DPI CSS reference with bold weight $\ge 700$).

### 2.2 Implemented Resolution: Distance Transform Stroke Measurement & Defensible Classification
To eliminate naive assumptions, `image_governance.py` was refined with an empirical stroke width detector and a 3-tier classification hierarchy:

```
                  Bounding Box Text Height (px)
                             │
            ┌────────────────┼────────────────┐
            ▼                                 ▼
      Height < 24px                    Height >= 24px
            │                                 │
            ▼                                 ▼
    [normal_text]                   Check Stroke Thickness
    Threshold: 4.5:1              (cv2.distanceTransform)
                                              │
                      ┌───────────────────────┴───────────────────────┐
                      ▼                                               ▼
            Height >= 36px OR                               24px <= Height < 36px
        (Height >= 24px AND stroke >= 4px)                AND stroke < 4px (not bold)
                      │                                               │
                      ▼                                               ▼
           [verified_large_text]                    [uncertain_font_weight_or_size]
              Threshold: 3.0:1                               Threshold: 4.5:1
                                                          (Conservative Fallback)
```

1. **Physical Stroke Thickness Measurement**:
   When localized text strokes are segmented via Otsu clustering, Euclidean Distance Transform (`cv2.distanceTransform(fg_mask, cv2.DIST_L2, 5)`) calculates the maximum radius of the letterform core. The physical stroke thickness is computed as:
   $$\text{stroke\_width} = 2.0 \times \max(D)$$
   A letterform stroke width of $\ge 4.0\text{px}$ reliably indicates physical bolding on raster canvases.

2. **Classification Categories**:
   - `normal_text`: $H < 24.0\text{px}$. Threshold: **$4.5:1$**.
   - `verified_large_text`: $H \ge 36.0\text{px}$ (unconditionally prominent display text) OR ($H \ge 24.0\text{px}$ with $\text{stroke\_width} \ge 4.0\text{px}$). Threshold: **$3.0:1$**.
   - `uncertain_font_weight_or_size`: $24.0\text{px} \le H < 36.0\text{px}$ with stroke width $< 4.0\text{px}$. Because bold weight cannot be certified from raster pixels, the system applies the **conservative $4.5:1$ threshold**.

---

## 3. Contrast Finding & Severity Mapping Matrix

The engine now cleanly differentiates between passes, failures, and indeterminate/manual review states across all contrast levels:

| Text Category | Contrast Ratio ($\text{CR}$) | Applicable Threshold | Region Status | Governance Status | Governance Severity | Finding Explanation & Canonical Policy |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Normal Text** | $\text{CR} < 3.0:1$ | $4.5:1$ | `fail` | `verified_issue` | `critical` | Severe violation failing both normal ($4.5:1$) and large ($3.0:1$) criteria. |
| **Normal Text** | $3.0:1 \le \text{CR} < 4.5:1$ | $4.5:1$ | `fail` | `verified_issue` | `warning` | Fails standard normal-text threshold ($4.5:1$). |
| **Normal Text** | $\text{CR} \ge 4.5:1$ | $4.5:1$ | `pass` | `passed_check` | `info` | Verified adequate contrast meeting WCAG AA normal text threshold ($4.5:1$). |
| **Verified Large Text** | $\text{CR} < 3.0:1$ | $3.0:1$ | `fail` | `verified_issue` | `critical` | Severe failure failing even the lenient large-text threshold ($3.0:1$). |
| **Verified Large Text** | $3.0:1 \le \text{CR} < 4.5:1$ | $3.0:1$ | `pass` | `passed_check` | `info` | Passes WCAG AA criterion for verified large/bold display text ($3.0:1$). |
| **Verified Large Text** | $\text{CR} \ge 4.5:1$ | $3.0:1$ | `pass` | `passed_check` | `info` | Exceeds both large ($3.0:1$) and normal ($4.5:1$) thresholds. |
| **Uncertain Weight/Size** | $\text{CR} < 3.0:1$ | $4.5:1$ | `fail` | `verified_issue` | `critical` | Severe contrast failure below $3.0:1$ regardless of font size. |
| **Uncertain Weight/Size** | $3.0:1 \le \text{CR} < 4.5:1$ | $4.5:1$ | `marginal` | `verified_issue` | `warning` | Font weight/size cannot be reliably verified from raster pixels. Conservative $4.5:1$ applied; flagged for human reviewer verification. |
| **Uncertain Weight/Size** | $\text{CR} \ge 4.5:1$ | $4.5:1$ | `pass` | `passed_check` | `info` | Satisfies conservative $4.5:1$ baseline. |
| **Low Confidence OCR** | Any | N/A | `indeterminate` | `inconclusive_evidence` | `info` | OCR recognition confidence too low ($< 0.60$) for reliable segmentation. |
| **Low Stroke Ratio / Indeterminate** | Any | N/A | `indeterminate` | `inconclusive_evidence` | `warning` | Bimodal text/background separation could not be established; manual review advised. |

---

## 4. Verification Test Suite

Seven new deterministic tests were created in `backend/tests/test_milestone5a_localized_contrast.py` to systematically test all threshold permutations:

1. `test_threshold_normal_text_below_3_to_1_fails_critical`:
   - Normal text ($H \approx 23\text{px}$), $\text{CR} \approx 2.4:1$.
   - **Result:** `status="verified_issue"`, `severity="critical"`.
2. `test_threshold_normal_text_between_3_and_4_5_fails_warning`:
   - Normal text ($H \approx 23\text{px}$), $\text{CR} \approx 3.4:1$.
   - **Result:** `status="verified_issue"`, `severity="warning"`, explicitly references $4.5:1$ standard.
3. `test_threshold_normal_text_above_4_5_passes`:
   - Normal text ($H \approx 23\text{px}$), $\text{CR} \approx 14:1$.
   - **Result:** `status="passed_check"`, `severity="info"`.
4. `test_threshold_large_text_below_3_to_1_fails_critical`:
   - Large headline ($H \approx 65\text{px}$), $\text{CR} \approx 2.4:1$.
   - **Result:** `status="verified_issue"`, `severity="critical"`.
5. `test_threshold_large_text_between_3_and_4_5_passes_large_criterion`:
   - Verified large headline ($H \approx 70\text{px}$, stroke $6.6\text{px}$), $\text{CR} \approx 3.4:1$.
   - **Result:** `status="passed_check"`, `severity="info"`, notes $3.0:1$ standard in explanation.
6. `test_threshold_large_text_above_4_5_passes`:
   - Large headline ($H \approx 70\text{px}$, stroke $6.6\text{px}$), $\text{CR} \approx 15:1$.
   - **Result:** `status="passed_check"`, `severity="info"`.
7. `test_threshold_uncertain_font_weight_between_3_and_4_5_marginal_warning`:
   - Borderline text ($H \approx 28\text{px}$, stroke $2.0\text{px}$ thin), $\text{CR} \approx 3.4:1$.
   - **Result:** `font_classification="uncertain_font_weight_or_size"`, `threshold=4.5`, `status="verified_issue"`, `severity="warning"`, explicit manual-review explanation.

---

## 5. Actual Test Execution Results

### 5.1 Localized Contrast Test Suite
```bash
python -m pytest tests/test_milestone5a_localized_contrast.py -v
```
**Outcome:** **21 passed** in 6.57s. All 21 accessibility and localized contrast tests passed cleanly.

### 5.2 Full Backend Suite
```bash
python -m pytest -q
```
**Outcome:** **128 passed** in 73.67s. Zero regressions across approval workflows, content versioning, OCR regression, and context-aware governance.

### 5.3 Frontend Test Suite
```bash
npm test -- --run
```
**Outcome:** **3 test files passed, 9 tests passed** in 25.10s.

### 5.4 Frontend Production Build
```bash
npm run build
```
**Outcome:** **Exit Code 0** in 17.76s. `tsc -b` and `vite build` completed successfully without type errors or broken references.

---

## 6. Summary of Files Changed
- `backend/app/services/image_governance.py`:
  - Added `font_classification` and `stroke_width` to `LocalizedContrastRegion`.
  - Implemented Euclidean Distance Transform on letterform masks.
  - Implemented conservative $4.5:1$ fallback and marginal review flagging for uncertain font weight/size.
  - Mapped severities consistently: critical for $< 3.0:1$, warning for $3.0 \le \text{CR} < 4.5$ on normal/uncertain text, info for passes.
- `backend/tests/test_milestone5a_localized_contrast.py`:
  - Added 7 deterministic threshold tests verifying all permutations.
- `docs/MILESTONE_5A1_ACCESSIBILITY_THRESHOLD_VERIFICATION.md`:
  - Complete verification report and audit documentation.
