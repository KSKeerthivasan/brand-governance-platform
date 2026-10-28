# Milestone 3 Implementation Report: Source Integrity Gate and Local Poster OCR

**Workspace:** `E:\CodeStar30`  
**Date:** 2026-10-28  
**Status:** Completed and Verified  
**Milestone Scope:** Local Poster OCR Engine, Context-Aware Governance Integration, Source Integrity Gate, Uncertainty Handling, and Deterministic Regression Testing.

---

## 1. Source-Integrity Preflight and Rule-Mapping Discrepancies

### Preflight Investigation & Canonical Mapping
Prior to integrating the local OCR pipeline, canonical rule mappings, scopes, actions, and severity levels were inspected across authoritative sources on disk:
- `test_assets/freshsip_inkloom_demo/brand_guidelines/freshsip_brand_guidelines.md` (authoritative Markdown mirror of `freshsip_brand_guidelines.pdf`)
- `test_assets/freshsip_inkloom_demo/brand_rules.csv` (21 canonical rules)
- `test_assets/freshsip_inkloom_demo/freshsip_products.csv` (6 canonical SKUs)
- `test_assets/freshsip_inkloom_demo/freshsip_approved_claims.csv` (13 claims)
- Live database records in table `knowledge_rules` for the Freshsip organization (`slug: freshsip`).

### Investigation of Discrepant Rules (Audit vs Authoritative Sources)
| Rule ID | Rule Name | Canonical Source (PDF / Markdown Mirror) | Canonical CSV (`brand_rules.csv`) | Database Record | Severity | Action | Audit Discrepancy Analysis |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **FR-RULE-007** | Prohibition of Disease Treatment, Prevention, or Cure Claims | Section D.1 (p. 3): "Never claim or imply that any Freshsip beverage treats, prevents, reverses, manages, or cures any disease..." | `prohibition`, Severity: `critical`, Scope: `all_channels`, Action: `block` | `prohibition`, Severity: `critical` | Critical | Block | Consistent across canonical files. Audit accurately recorded `critical`/`block`. |
| **FR-RULE-008** | Prohibition of Detoxification, Cleansing, Weight-Loss, and Immunity Claims | Section D.2 (p. 3): "Do not claim that Freshsip products detoxify the body, cleanse the liver or blood, flush out toxins, burn fat, cause weight loss, or boost/strengthen the immune system." | `prohibition`, Severity: `critical`, Scope: `all_channels`, Action: `block` | `prohibition`, Severity: `critical` | Critical | Block | Consistent across canonical files. Audit accurately recorded `critical`/`block`. |
| **FR-RULE-010** | Prohibition of Unsupported Natural, Organic, or Chemical-Free Claims | Section D.4 (p. 4): "Do not use '100% natural', 'certified organic', 'pesticide-free', 'chemical-free', or 'farm-certified' claims; only state 'No added preservatives' when supported..." | `prohibition`, Severity: `high`, Scope: `all_channels`, Action: `block` | `prohibition`, Severity: `high` | High | Block | **Discrepancy resolved:** An earlier exploratory audit noted FR-RULE-010 as `critical`, whereas both the guideline text (Section D.4) and `brand_rules.csv` classify it as severity `high` with enforcement action `block`. Both severity levels trigger a hard publication block; `high` is the authoritative classification. |
| **FR-RULE-011** | Prohibition of Unsubstantiated Superiority and Superlative Claims | Section D.5 (p. 4): "Do not use comparative superiority or superlative claims such as 'India\'s healthiest juice', 'India\'s #1 cold-pressed brand'..." | `prohibition`, Severity: `high`, Scope: `all_channels`, Action: `block` | `prohibition`, Severity: `high` | High | Block | Consistent across canonical sources (`high`/`block`). |
| **FR-RULE-012** | No Fabricated Certifications, Endorsements, Testimonials, or Awards | Section D.6 (p. 4): "Never invent or cite regulatory license numbers, doctor/nutritionist endorsements, laboratory test certificates, awards, or real customer testimonials." | `prohibition`, Severity: `critical`, Scope: `all_channels`, Action: `block` | `prohibition`, Severity: `critical` | Critical | Block | Consistent across canonical sources (`critical`/`block`). |

**Preflight Gate Conclusion:** The authoritative source assets (`brand_rules.csv` and `freshsip_brand_guidelines.md`) are internally consistent. Earlier discrepancies arose from preliminary manual audit notes conflating `high` with `critical` severity because both mandate a blocking action (`action_on_match: block`). All active database rules faithfully reflect canonical records without synthetic modifications.

---

## 2. OCR Library, Version, Licensing and Execution Mode

- **Selected Engine:** `RapidOCR` with ONNX Runtime (`rapidocr_onnxruntime`).
- **Installed Package Version:** `rapidocr_onnxruntime==1.4.4`.
- **Underlying Engine:** PaddleOCR algorithms ported to high-performance C++ ONNX Runtime inference models.
- **License:** Apache License 2.0 (permissive, open-source, fully commercial-friendly).
- **Execution Mode:**
  - **100% Local and Offline:** Executes locally via CPU execution provider (`CPUExecutionProvider`). Zero network requests, zero telemetry, and zero data transmission to external or cloud APIs.
  - **No External Binary Dependencies:** Unlike Tesseract (which requires a system-level `tesseract.exe` and language traineddata files), RapidOCR is fully self-contained inside Python packages using ONNX models (`ch_PP-OCRv4_det`, `ch_ppocr_mobile_v2.0_cls`, `ch_PP-OCRv4_rec`).
  - **No Headless Conflicts:** Does not conflict with existing `opencv-python==4.13.0`.

---

## 3. Files and Schemas Changed

| File Path | Nature of Change | Summary of Changes |
| :--- | :--- | :--- |
| `backend/app/services/ocr_service.py` | New Service | Implements `OCRService`, `OCRResult`, and `OCRRegion` dataclasses. Safely wraps RapidOCR lazy-loading, raster image validation, bounding-box extraction, and error handling. |
| `backend/app/services/governance_engine.py` | Engine Integration | Integrates local OCR extraction from `content_version.poster_file_path`, combines text into governance evaluation, enables caption-poster deduplication, evaluates mandatory wording in poster images, detects poster price discrepancies, and appends bounding-box coordinates to findings. |
| `backend/tests/test_milestone3_ocr_regression.py` | New Test Suite | Implements 12 end-to-end regression tests validating the 12 criteria specified in Milestone 3 Part E. |

---

## 4. OCR Extraction Format and Governance Integration

### Structured OCR Result Schema
```python
@dataclass
class OCRRegion:
    text: str
    confidence: float
    bbox: List[List[float]]  # [[x1, y1], [x2, y2], [x3, y3], [x4, y4]]

@dataclass
class OCRResult:
    status: str             # "success", "no_text", "low_confidence", "failed", "unsupported_format"
    extracted_text: str = ""
    regions: List[OCRRegion] = field(default_factory=list)
    mean_confidence: float = 0.0
    error_message: Optional[str] = None
    latency_ms: float = 0.0
```

### Governance Engine Integration Architecture
1. **Extraction Step (Step 0):** If `content_version.poster_file_path` is present, `ocr_service.extract_text_from_image(...)` is executed locally.
2. **Context Detection:** Product context detection evaluates `combined_source_text = f"{title} {body_text} {poster_text}"`. This ensures that products visually identified in artwork are correctly targeted by SKU-specific checks.
3. **Prohibited Terminology & Deduplication:**
   - Evaluates patterns across caption and poster.
   - If a prohibited term (e.g., `detox`) appears in **both** caption and poster artwork, the engine produces **one deduplicated finding** titled `"[RULE-ID] Prohibited Term Detected: 'term' (Caption & Poster)"`.
   - The finding records both sources: `text_excerpt="Caption: '...' | Poster: '...' [Poster Region bbox: [...]]"`.
   - If the prohibited term appears only in the poster, the finding specifies `"(Poster Image)"` with exact region bounding box.
4. **Mandatory Wording and Disclosures:**
   - Mandatory disclosures (such as `CONTAINS CELERY` for `FS-PROD-003` under FR-RULE-014, and `No added sugar` under FR-RULE-005) are evaluated against `combined_content` (caption + poster text).
   - If mandatory wording is physically present in the poster artwork, it is satisfied without generating false-positive missing term warnings.
5. **Product Catalogue Price Verification:**
   - Promotional pricing in poster artwork (e.g., `Buy for ₹65 (50% OFF)`) is extracted using regional currency and OCR-resilient regex patterns (`\b(?:buy\s*for|mrp|price|inr|rs\.?)[^\d\w\n\r]*[₹fF\s:.-]*(\d{2,4})\b`).
   - Mismatches against approved catalogue MRP (`₹120` for `FS-PROD-001`) generate a critical `product_fact_mismatch` in poster finding with bounding box.
6. **Preservation of Visual Checks:** Existing dimensions, aspect ratio, color palette, WCAG contrast, logo clearspace, and accessibility checks remain fully active and intact.

---

## 5. Confidence and Uncertainty Handling

The engine explicitly distinguishes between five OCR operational states:
1. **`success`:** Text extracted with average confidence $\ge 0.60$. Text is passed to all context-aware rule checks.
2. **`no_text`:** Zero text detected in image (e.g., decorative background, clean landscape, unbranded graphic). Handled cleanly as valid non-text artwork; does not block publication or generate false OCR errors.
3. **`low_confidence`:** Mean recognition confidence $< 0.60$. Generates a non-blocking governance warning (`category: "missing_evidence"`, title: `"Uncertain OCR Text Recognition: Human Review Recommended"`), flagging the draft for human review.
4. **`failed`:** Corrupt file, unreadable image data, or missing file. Produces a governance warning (`category: "image_guideline_issue"`, title: `"OCR Processing Failed: Poster Text Unverified"`) without unhandled server crashes.
5. **`unsupported_format`:** Unsupported file extension (e.g., `.txt`, `.pdf`). Produces an informative warning instructing the creator to provide standard raster formats (`.png`, `.jpg`, `.webp`).

---

## 6. Test Cases, Commands and Measured Results

### Milestone 3 Regression Test Suite (`test_milestone3_ocr_regression.py`)
Executed with: `pytest tests/test_milestone3_ocr_regression.py -v`

| # | Test Name | Target Requirement / Scenario | Real Asset / Fixture | Result |
| :---: | :--- | :--- | :--- | :---: |
| 1 | `test_1_compliant_poster_with_visible_approved_terminology` | Compliant poster passes governance without blocking findings | `campaign_morning_citrus_approved.png` | **PASSED** |
| 2 | `test_2_poster_with_clearly_prohibited_promotional_claim` | Prohibited detox / fat-loss claim in poster blocked (FR-RULE-008) | `campaign_rejected_detox_claim.png` | **PASSED** |
| 3 | `test_3_poster_with_unsupported_organic_certification_claim` | Unsupported USDA Certified Organic claim in poster blocked (FR-RULE-010) | Synthetic PNG fixture | **PASSED** |
| 4 | `test_4_poster_with_prohibited_sugar_claim` | Prohibited "100% Sugar-Free" claim in poster blocked (FR-RULE-005) | Synthetic PNG fixture | **PASSED** |
| 5 | `test_5_mandatory_disclosure_visibly_present_in_image` | "CONTAINS CELERY" in poster satisfies FR-RULE-014 without false positive | `product_fs_prod_003_tomato_celery.png` | **PASSED** |
| 6 | `test_6_image_with_incorrect_pricing_against_sku` | Poster price ₹65 vs SKU MRP ₹120 triggers critical fact mismatch | Synthetic PNG fixture | **PASSED** |
| 7 | `test_7_same_prohibited_claim_in_caption_and_poster_deduplicated` | Same detox claim in caption + poster produces 1 unified finding | `campaign_rejected_detox_claim.png` | **PASSED** |
| 8 | `test_8_image_with_no_visible_text` | Decorative image with no text passes without OCR failure | Clean solid green PNG | **PASSED** |
| 9 | `test_9_blurred_or_low_confidence_poster_requires_review` | Low confidence (<60%) produces warning for human review | Mocked low-confidence result | **PASSED** |
| 10 | `test_10_unreadable_or_corrupt_image` | Corrupt non-image binary handled gracefully without 500 error | Corrupt binary file | **PASSED** |
| 11 | `test_11_unsupported_image_format` | Unsupported format (.txt) produces warning | Text file fixture | **PASSED** |
| 12 | `test_12_tenant_isolation_and_content_version_integrity` | Content version checksum binds poster, tenant isolation enforced | Multi-version synthetic poster | **PASSED** |

**Suite Result:** 12 passed in 30.66s.

---

## 7. Before-and-After Test Counts

| Test Suite Scope | Milestone 2 Baseline | Milestone 3 Post-Implementation | Status |
| :--- | :---: | :---: | :---: |
| Milestone 1 Baseline Regression (`test_milestone1_baseline_regression.py`) | 9 passed | 9 passed | Preserved |
| Milestone 2 Context-Aware Engine (`test_milestone2_context_aware_regression.py`) | 12 passed | 12 passed | Preserved |
| Milestone 3 Local OCR Regression (`test_milestone3_ocr_regression.py`) | *N/A (new)* | **12 passed** | **New Suite** |
| Existing Poster & Versioning (`test_poster_governance_integration.py`) | 1 passed | 1 passed | Preserved |
| Visual & Recheck Governance (`test_organization_specific_visual_governance.py`) | 3 passed | 3 passed | Preserved |
| Full Backend Test Suite (`pytest -q`) | 69 passed | **81 passed** | **+12 Passed** |
| Frontend Unit & Component Tests (`vitest run --run`) | 9 passed | 9 passed | Preserved |
| Frontend Production Build (`tsc -b && vite build`) | Passed (0 errors) | Passed (0 errors) | Clean |

---

## 8. Measured OCR Latency and Accuracy Evidence

### Measured Inference Benchmarks (Local CPU Execution)
| Asset Evaluated | Dimensions | Resolution | Cold-Start Latency | Warm Latency | Text Extracted | Mean Confidence |
| :--- | :---: | :---: | :---: | :---: | :--- | :---: |
| `campaign_morning_citrus_approved.png` | $1400 \times 780$ | 1.09 MP | 4,708 ms | 2,140 ms | 10 regions ("No added sugar", "Valencia Orange", etc.) | **98.0%** |
| `campaign_rejected_detox_claim.png` | $1400 \times 780$ | 1.09 MP | 2,340 ms | 2,050 ms | 12 regions ("Miracle Detox", "100% Sugar-Free", "Buy for F65") | **96.8%** |
| `product_fs_prod_003_tomato_celery.png` | $1200 \times 1200$ | 1.44 MP | 2,410 ms | 2,180 ms | 7 regions ("Garden Tomato Celery Press", "CONTAINS CELERY") | **97.3%** |
| `freshsip_logo_primary.png` | $600 \times 320$ | 0.19 MP | 1,850 ms | 980 ms | 2 regions ("Freshsip", "BEVERAGES INDIA") | **99.2%** |
| Synthetic High-Contrast Text (PIL) | $900 \times 500$ | 0.45 MP | 1,920 ms | 1,120 ms | 3 regions | **98.7%** |
| Blank Image / Decorative Texture | $600 \times 600$ | 0.36 MP | 1,150 ms | 640 ms | 0 regions (`status: no_text`) | N/A |

### Downscaling and Resource Thresholds
- High-resolution posters up to $1600 \times 1600$ are processed directly by RapidOCR ONNX models without downscaling, ensuring that fine-print statutory disclosures (such as "CONTAINS CELERY (14%)" at 14pt-18pt) remain completely legible.
- Average processing time on standard developer hardware is ~2.0 to 2.2 seconds per creative poster image.

---

## 9. Known False Positives, False Negatives and Limitations

1. **Regional Currency Glyph Substitution:**
   - Standard OCR models trained on global datasets frequently substitute the Indian Rupee symbol (`₹`) with `F`, `Rs`, `fr`, or drop the symbol entirely when stylized fonts are used.
   - *Mitigation implemented:* The engine's pricing regex incorporates `\b(?:buy\s*for|mrp|price|inr|rs\.?)[^\d\w\n\r]*[₹fF\s:.-]*(\d{2,4})\b`, matching both prefixed and symbol-dropped numerical amounts.
2. **Word Spacing and Kerning in Compressed Creative Art:**
   - Tightly kerned display headers (e.g., `FreshsipValenciaOrange` or `100%Sugar-Free`) may have whitespace compressed by OCR text recognizers.
   - *Mitigation implemented:* Governance patterns use word-boundary matching on sub-words (`\bsugar[ -]free\b`) and regex flexibility (`(?:100%\s*)?sugar[ -]free`) rather than strictly requiring inter-word spaces.
3. **Curved and Highly Stylized Artistic Lettering:**
   - Extremely distorted graffiti-style typography or circular badge text may experience lower confidence (<60%).
   - *Mitigation implemented:* Uncertainty handling catches low-confidence extractions and routes them to human reviewers (`status: "low_confidence"` -> warning) instead of making automated clearance decisions.
4. **Offline Scope Boundary:**
   - OCR runs strictly offline; it does not query online dictionaries or external LLMs for OCR correction.

---

## 10. Confirmation of User Changes and Audit Trails

- **Working Tree Integrity:** All pre-existing user files, schema modifications, frontend routes, and component updates were preserved. No Git resets, branch rollbacks, or destructive commands were executed.
- **Audit Logging:** Every governance execution evaluating poster images records structured audit events in `audit_events` with `event_type="GOVERNANCE_CHECK_RUN"`, capturing version ID, overall status, findings count, and image execution context.
- **Database Records:** Canonical product facts, approved claims, and 21 knowledge rules remain intact in the live database.

---
*End of Milestone 3 Report. Ready for user review before proceeding to approval workflow changes.*
