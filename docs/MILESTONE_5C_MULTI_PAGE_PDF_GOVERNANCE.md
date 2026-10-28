# Milestone 5C Implementation Report: Multi-Page PDF Creative Governance

**Workspace:** `E:\CodeStar30`  
**Date:** 2026-10-28  
**Status:** Completed and Verified  
**Milestone Scope:** Multi-Page PDF Creative Governance, Local Rendering & Page Extraction (`pypdfium2`), Per-Page Finding Attribution (`page_number`), Within-Page Deduplication & Cross-Page Repetition Preservation, Content Studio Multi-Page Carousel & Findings Filter, Approval Queue Multi-Page Deck Review, and Deterministic Regression Testing.

---

## 1. Executive Summary

Milestone 5C extends the Brand Governance Platform to review and govern multi-page PDF marketing creatives (including advertising collateral, campaign pitch decks, partner slide carousels, and multi-page print/digital brochures) without altering or weakening the core governance engine. 

Prior to Milestone 5C, poster evaluation operated exclusively on single raster images (`image/png`, `image/jpeg`, `image/webp`). Milestone 5C establishes a local, zero-cloud, multi-page processing pipeline that:
1. Validates incoming PDF creatives against strict format signatures, encryption constraints, and resource limits.
2. Rasterizes pages locally with dynamic scaling bounded to prevent memory exhaustion.
3. Performs hybrid native-text and local OCR extraction per page with OCR confidence scoring and degradation warnings.
4. Evaluates brand governance rules at both the page level (attributing violations to exact 1-indexed `page_number`s) and document level (verifying mandatory disclosures across the multi-page creative).
5. Provides rich interactive preview and page navigation in both Content Studio and the Approval Queue, upholding the critical governance distinction: **"All $N$ pages analysed" $\neq$ "All $N$ pages compliant"**.

All functionality from Milestones 1 through 5B.2 is preserved with zero regressions across 172 backend tests and the full frontend test suite.

---

## 2. Architecture & Design Decisions

### 2.1 Initial Implementation Audit
Before writing code, an audit of existing models, services, uploads, governance, approvals, and frontend was conducted:
- **Models (`backend/app/models/content.py`):** `ContentVersion` possessed `poster_file_path`, `poster_file_type`, and `poster_checksum_sha256`. `GovernanceFinding` lacked a page indicator, associating all findings exclusively with `run_id`.
- **Uploads (`backend/app/api/v1/content.py`):** `upload_poster` allowed only `image/png`, `image/jpeg`, and `image/webp` with a 10MB limit and single-image validation.
- **OCR Service (`backend/app/services/ocr_service.py`):** `OCRService.extract_text_from_image` accepted only file paths on disk, not in-memory PIL images.
- **Image Governance (`backend/app/services/image_governance.py`):** Visual governance evaluated single image dimensions and aspect ratios without page context.
- **Governance Engine (`backend/app/services/governance_engine.py`):** Single-page evaluation path combined caption with one poster image OCR result.
- **Approval Workflow (`backend/app/services/approval_workflow.py`):** Submissions verified version checksums and latest governance run findings, but lacked awareness of multi-page PDF structures.
- **Frontend (`ContentStudio.tsx`, `ApprovalQueue.tsx`):** Creative previews assumed a single image URL rendered via `<img src=...>`, with no page navigation or page-level finding indicators.

### 2.2 Local Rendering & Extraction Engine
To uphold strict data sovereignty and offline operation requirements, document processing remains 100% local:
- **PDF Rendering Library:** `pypdfium2` (v5.14.0), wrapping Google's PDFium engine.
- **Native Text Extraction:** `pypdf` (v6.1.1).
- **OCR Engine:** `rapidocr_onnxruntime` (v1.4.4) with ONNX Runtime CPU inference.
- **Zero External Runtimes:** No external Poppler utilities, ImageMagick, Ghostscript, or cloud vision APIs are required. Everything executes within self-contained Python wheels and native libraries on Windows.

### 2.3 Rendering Resolution & Memory Bounding Policy
Pathological vector PDFs can trigger denial-of-service if rendered at unconstrained DPIs. `backend/app/services/pdf_service.py` implements a bounded rendering policy:
- **Baseline Target:** 150–200 DPI for standard page sizes.
- **Target Pixel Dimension:** `TARGET_RASTER_DIMENSION_PX = 1600`.
- **Dynamic Scale Formula:**
  $$\text{scale} = \min\left(\max\left(\frac{1600}{\max(\text{width\_pt}, \text{height\_pt})}, 1.0\right), 2.5\right)$$
- Standard Letter/A4 pages (~612x792 pt) render at $\approx 2.0\times$ scale (~1224x1584 px), providing crystal-clear OCR legibility while capping memory consumption at $<10$ MB per rendered page buffer.

### 2.4 Supported PDF Constraints
Incoming creatives must satisfy deterministic safety boundaries:
- **Magic Bytes Validation:** File must start with `%PDF-` header.
- **Page Count Limits:** Maximum 30 pages allowed (`MAX_PDF_PAGES = 30`). Files exceeding this are rejected with HTTP 400.
- **File Size Limits:** Maximum 25 MB allowed (`MAX_PDF_FILE_SIZE = 25 * 1024 * 1024`). Files exceeding this are rejected with HTTP 400.
- **Encryption Security:** Password-protected or encrypted PDFs are rejected immediately with HTTP 400 (`"Encrypted or password-protected PDF creatives are not supported"`), preventing unhandled decryption exceptions.
- **Malformed / Zero-Byte Handling:** Empty or corrupt files fail closed with clean HTTP 400 validation responses.

### 2.5 Page Caching & On-Demand Preview
To prevent redundant rasterization during governance runs and UI browsing:
- Rendered page images are stored in a version-scoped disk cache: `uploads/pdf_cache/{version_id}/page_{page_num}.png`.
- The API endpoint `GET /api/v1/content/versions/{version_id}/poster?page=N&render=true` serves cached PNGs directly to frontend `<img>` elements with standard browser caching headers.
- Metadata endpoint `GET /api/v1/content/versions/{version_id}/pdf-pages` returns page dimensions, aspect ratios, and orientations (`portrait`, `landscape`, `square`).

### 2.6 Per-Page Finding Attribution & Alembic Migration
A database migration was created to record page numbers without altering existing table structures:
- **Migration:** `backend/alembic/versions/a1b2c3d4e5f6_add_page_number_to_governance_findings.py`
- **Field:** `governance_findings.page_number = Column(Integer, nullable=True)`
- **Index:** `ix_governance_findings_run_page` on `(governance_run_id, page_number)`
- **Attribution Convention:**
  - `page_number = N` (1-indexed): Finding detected on page $N$ of a multi-page PDF (e.g. prohibited terminology, visual contrast violation, SKU price mismatch on page 2).
  - `page_number = None`: Finding detected in caption text, legacy single-image raster artwork, or document-wide disclosures.

### 2.7 Deduplication vs Cross-Page Repetition Policy
A key architectural principle in multi-page governance is distinguishing duplicate extraction on the *same* page from repeated violations across *different* pages:
1. **Same-Page Deduplication:** PDFs often contain both selectable native text and rasterized text in embedded images. If native text extraction and OCR extraction identify the same prohibited claim (e.g. `"detox"`) on Page 1, the engine produces **one deduplicated finding** for Page 1, citing both extraction sources.
2. **Cross-Page Repetition Preservation:** If Page 1 contains `"India's #1 juice"` (unsubstantiated superlative) and Page 3 repeats `"India's #1 juice"`, these are **preserved as two distinct findings**: one attributed to Page 1 and one to Page 3. This ensures reviewers can pinpoint and correct every offending slide in a deck.

### 2.8 Document-Level vs Page-Level Governance
- **Page-Level Rules:** Terminology prohibitions (e.g. disease prevention, detox claims), approved product fact verification, unapproved claim detection, pricing mismatches, and visual/contrast compliance are evaluated per page and tagged with `page_number`.
- **Document-Level Disclosures:** Mandatory rules such as allergen disclosures (`CONTAINS CELERY` for Celery Punch) or sugar disclaimers (`No added sugar` for 100% juice claims) can appear on any page of the creative (e.g. on the final disclaimer slide). If the mandatory disclosure appears anywhere in the multi-page deck (or in the accompanying caption copy), the document passes the mandatory disclosure check.

### 2.9 Analysis vs Compliance Distinction
The frontend and governance results make a rigorous semantic distinction:
> **"All $N$ pages analysed" $\neq$ "All $N$ pages compliant"**

A PDF may be fully rendered, OCR-extracted, and evaluated across all pages without error, yet contain critical blockers on pages 1 and 3. The UI prominently displays an analysis vs compliance distinction banner in the findings panel:
- When all pages pass: `"All N pages analysed · All N pages compliant (0 findings)"` (Emerald)
- When violations exist: `"All N pages analysed · Violations detected across M page(s) (X critical blockers, Y warnings)"` (Amber/Rose)
- When OCR confidence is degraded: Clear warnings indicate which specific pages require manual human inspection.

### 2.10 Version Integrity and Approval Workflow
- When a new or revised PDF is uploaded via `PUT /api/v1/content/{id}`, a new `ContentVersion` is minted with an updated SHA-256 checksum (`poster_checksum_sha256`).
- The new version starts with zero governance runs (`404` on latest run). Stale governance runs from prior versions cannot leak or satisfy approval submission gates.
- Approval submission requires a fresh governance run on the current version. Any unresolved critical blockers immediately reject the submission (HTTP 400). Unresolved warnings require documented reviewer justifications.

---

## 3. Dependencies and Licensing

| Dependency | Version | License | Usage & Purpose |
| :--- | :--- | :--- | :--- |
| `pypdfium2` | `^5.14.0` | Apache-2.0 / BSD-3-Clause | Local rasterization of vector and raster PDF pages via bundled Google PDFium binary. |
| `pypdf` | `^6.1.1` | BSD-3-Clause | Native vector text extraction, page metadata inspection, encryption detection. |
| `rapidocr_onnxruntime` | `1.4.4` | Apache-2.0 | Local OCR text and bounding-box detection via ONNX Runtime CPU inference. |
| `Pillow` | `^11.0.0` | MIT-CMU | In-memory image manipulation, cropping, format conversion, and saving. |
| `SQLAlchemy` | `^2.0.0` | MIT | ORM models, pagination, query filtering, and Alembic migrations. |

All dependencies are commercial-friendly open-source software executing 100% offline with zero network connectivity or external licensing requirements.

---

## 4. Database Schema & Migration

### Migration Script
**Path:** [backend/alembic/versions/a1b2c3d4e5f6_add_page_number_to_governance_findings.py](file:///e:/CodeStar30/backend/alembic/versions/a1b2c3d4e5f6_add_page_number_to_governance_findings.py)

```python
"""add_page_number_to_governance_findings

Revision ID: a1b2c3d4e5f6
Revises:
Create Date: 2026-10-28 19:35:00
"""
from alembic import op
import sqlalchemy as sa

revision = 'a1b2c3d4e5f6'
down_revision = None
branch_labels = None
depends_on = None

def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [col['name'] for col in inspector.get_columns('governance_findings')]
    if 'page_number' not in columns:
        op.add_column('governance_findings', sa.Column('page_number', sa.Integer(), nullable=True))
    indexes = [idx['name'] for idx in inspector.get_indexes('governance_findings')]
    if 'ix_governance_findings_run_page' not in indexes:
        op.create_index('ix_governance_findings_run_page', 'governance_findings', ['governance_run_id', 'page_number'])

def downgrade() -> None:
    op.drop_index('ix_governance_findings_run_page', table_name='governance_findings')
    op.drop_column('governance_findings', 'page_number')
```

### Models & Schemas Updated
- [backend/app/models/content.py](file:///e:/CodeStar30/backend/app/models/content.py): Added `page_number = Column(Integer, nullable=True)` to `GovernanceFinding`.
- [backend/app/schemas/governance.py](file:///e:/CodeStar30/backend/app/schemas/governance.py): Added `page_number: Optional[int] = None` to `GovernanceFindingOut`.
- [backend/app/schemas/content.py](file:///e:/CodeStar30/backend/app/schemas/content.py): Added `is_pdf: bool = False` and `page_count: Optional[int] = None` to `ContentVersionOut`.
- [backend/app/schemas/approval.py](file:///e:/CodeStar30/backend/app/schemas/approval.py): Added `is_pdf: bool = False` and `page_count: Optional[int] = None` to `ApprovalSubmissionOut`.

---

## 5. API and Service Implementation

### 5.1 PDF Service
**Path:** [backend/app/services/pdf_service.py](file:///e:/CodeStar30/backend/app/services/pdf_service.py)
Key functions:
- `validate_pdf_file(file_path)`: Asserts file exists, checks `%PDF-` signature, inspects encryption via `pypdf.PdfReader`, enforces `MAX_PDF_PAGES` and `MAX_PDF_FILE_SIZE`, returning page count.
- `render_pdf_page_to_image(file_path, page_number)`: Renders 1-indexed page using `pypdfium2` with bounded scaling, returning a PIL RGB Image.
- `get_or_render_page_cache(file_path, version_id, page_number)`: Manages disk cache for rendered PNGs.
- `extract_native_text(file_path, page_number)`: Extracts selectable vector text from page using `pypdf`.
- `get_pdf_metadata(file_path)`: Inspects all pages and returns structured dimensions, aspect ratios, and orientations.

### 5.2 Content & Poster Endpoints
**Path:** [backend/app/api/v1/content.py](file:///e:/CodeStar30/backend/app/api/v1/content.py)
- `POST /api/v1/content/{id}/versions/{version_id}/upload-poster`:
  - Accepts `application/pdf` in addition to raster images.
  - Validates PDF format, pages, and size via `PDFService`.
  - Calculates and stores SHA-256 checksum and file type (`application/pdf`).
  - Pre-renders and caches initial page PNGs.
  - Returns `is_pdf: True`, `page_count: N`, and page metadata.
- `GET /api/v1/content/versions/{version_id}/poster`:
  - For PDF creatives, takes query parameters `?page=N&render=true` to serve rendered PNG images for `<img src=...>` tag display.
  - Serves raw PDF file when `render=false` or omitted without page specification.
- `GET /api/v1/content/versions/{version_id}/pdf-pages`:
  - Returns structured array of page objects: `[{page_number, width_pt, height_pt, aspect_ratio, orientation}]`.

### 5.3 Governance Engine Integration
**Path:** [backend/app/services/governance_engine.py](file:///e:/CodeStar30/backend/app/services/governance_engine.py)
- Detects `is_pdf = content_version.poster_file_type == "application/pdf"`.
- If PDF, executes `_execute_pdf_governance_run`:
  - Iterates through each page $1 \dots N$.
  - Extracts native vector text and performs local OCR on the rendered page image.
  - Evaluates OCR confidence; generates non-blocking `missing_evidence` warning if confidence $< 0.60$.
  - Evaluates prohibited terminology, approved claims, and SKU facts per page, associating each violation with `page_number=page_idx`.
  - Deduplicates identical findings produced by native text and OCR on the same page.
  - Evaluates visual contrast and geometry per page, attributing findings to `page_number=page_idx`.
  - Evaluates document-wide disclosures across all pages and caption text.

---

## 6. Frontend Content Studio & Approval Queue

### 6.1 Content Studio (`frontend/src/pages/ContentStudio.tsx`)
1. **Upload Acceptance:** Creative asset file input accepts `.pdf,image/png,image/jpeg,image/webp`.
2. **Multi-Page Deck Header:** Shows `Multi-Page Creative Deck (N Pages)` with format badge.
3. **Interactive Page Navigation:**
   - Page selector chips (`Pg 1`, `Pg 2`, ...) allow instantaneous switching.
   - Per-page status dot indicators: Red for pages with critical blockers, amber for warnings, emerald for compliant pages.
4. **Current Page Preview:** Renders `<img src="/api/v1/content/versions/{id}/poster?page={selectedPage}&render=true">` with `p. {selectedPage}/{pageCount}` overlay badge and orientation metadata.
5. **Analysis vs Compliance Distinction Banner:** Prominently states whether all pages were analysed and lists compliant vs violating page counts.
6. **Per-Page Findings Filter:** Tab bar (`All Pages (M)`, `Pg 1 (X)`, `Pg 2 (Y)`, `Caption (Z)`) filters findings drawer in one click.
7. **Interactive Finding Links:** Clicking the `Page {f.page_number}` badge on any finding card automatically synchronizes the preview carousel and filter tab to that page.

### 6.2 Approval Queue (`frontend/src/pages/ApprovalQueue.tsx`)
1. **Submission Metadata:** Highlights PDF submissions with `PDF Creative (N Pages)`.
2. **Reviewer Deck Navigation:** Reviewers can inspect every individual slide/page using carousel chips with per-page status dots before rendering their decision.
3. **Blockers & Warnings Inspector:** Critical blockers and warnings display clickable `Page {f.page_number}` badges that jump the creative preview directly to the offending page.
4. **Strict Approval Gate:** Any submission with critical blockers cannot be approved; warnings require typed reviewer justification.

---

## 7. Verification and Testing Results

### 7.1 Regression Test Suite (`backend/tests/test_milestone5c_pdf_governance.py`)
13 deterministic regression tests validate every requirement of Milestone 5C:

```powershell
pytest tests/test_milestone5c_pdf_governance.py -v
```

| Test Name | Verification Focus | Result |
| :--- | :--- | :--- |
| `test_1_valid_single_and_multi_page_pdf` | Upload and governance evaluation of valid single and multi-page PDFs | **PASSED** |
| `test_2_different_page_sizes_and_orientations` | Correct extraction and rendering across portrait, landscape, and square pages | **PASSED** |
| `test_3_page_to_finding_associations` | Accurate attribution of findings to specific 1-indexed `page_number`s | **PASSED** |
| `test_4_ocr_confidence_and_unreadable_pages` | Low-confidence warning generation and unreadable page handling | **PASSED** |
| `test_5_malformed_empty_encrypted_pdfs` | Clean rejection (HTTP 400) of empty, corrupt, and encrypted PDFs | **PASSED** |
| `test_6_page_count_and_file_size_limits` | Enforcement of 30-page and 25MB limits | **PASSED** |
| `test_7_duplicate_extraction_paths_deduplicated_on_same_page` | Same-page native + OCR deduplication | **PASSED** |
| `test_8_findings_repeating_across_different_pages` | Preservation of repeating violations across different pages | **PASSED** |
| `test_9_pdf_checksum_changes_and_stale_governance` | SHA-256 recalculation on revision and prevention of stale governance leakage | **PASSED** |
| `test_10_critical_blockers_and_warning_justification_in_pdf_approval` | Hard block on approval submit for critical blockers; warning justification enforcement | **PASSED** |
| `test_11_tenant_isolation_and_permissions` | Strict tenant data isolation and role-based permissions on PDF assets | **PASSED** |
| `test_12_existing_png_jpeg_webp_and_text_workflows` | Zero regressions on existing raster images and text-only governance | **PASSED** |
| `test_13_pdf_pages_metadata_endpoint` | Structured metadata endpoint (`GET /pdf-pages`) accuracy | **PASSED** |

**Outcome:** `13 passed in 10.32s`

### 7.2 Full Backend Regression Suite
To ensure complete backwards compatibility across Milestones 1–5B.2:

```powershell
pytest -q
```
**Outcome:** `172 passed in 108.62s` (100% pass rate across entire repository).

### 7.3 Frontend Build & Unit Test Verification
```powershell
npm test -- --run
```
**Outcome:** 3 test files, 9 unit tests passed.

```powershell
npm run build
```
**Outcome:** TypeScript type-check and Vite build completed with return code `0` (`dist/` built cleanly without errors).

### 7.4 End-to-End Browser Verification
An autonomous browser verification subagent performed a full end-to-end user session:
1. Logged into the platform as `creator@freshsip.com`.
2. Navigated to Content Studio.
3. Created a new draft and uploaded a multi-page PDF campaign deck (`multi_page_creative.pdf`).
4. Verified that the page navigation chips (`Pg 1`, `Pg 2`) and preview carousel rendered properly with orientation badges.
5. Ran governance check and verified that the Analysis vs Compliance distinction banner rendered properly.
6. Tested per-page filter tabs (`Pg 1`, `Pg 2`) and verified that finding cards displayed clickable `Page 1` and `Page 2` badges.
7. Submitted the draft to the Approval Queue.
8. Switched to `reviewer@freshsip.com` in the Approval Queue, verified multi-page deck inspection, status dots, and finding page jumps.
9. Recorded video artifact saved to:
   [pdf_governance_e2e_1793193477029.webp](file:///C:/Users/Keerthivasan%20K%20S/.gemini/antigravity-ide/brain/bdc72709-48b3-451c-8856-74f130e8093d/pdf_governance_e2e_1793193477029.webp)

---

## 8. Known Limitations & Out-of-Scope Boundaries

In adherence to the milestone specification, the following boundaries remain strictly out of scope:
- **No AI Rewriting or Autonomous Content Modifications:** The engine flags violations and reports excerpts; it does not rewrite or alter creative content.
- **Unsupported Document Formats:** Native Microsoft PowerPoint (`.pptx`), Word (`.docx`), or raw HTML files are rejected. Such formats must be exported to standard PDF prior to upload.
- **Unsupported Media:** Video files (`.mp4`, `.mov`) and animated GIFs remain unsupported under Milestone 5C.
- **Document Modifications:** The platform does not alter, annotate, or re-encode uploaded PDF binaries.
- **Password-Protected Files:** Encrypted or password-protected PDFs are rejected fail-closed to prevent security vulnerabilities and unhandled worker failures.
- **Maximum Page Threshold:** Files with $>30$ pages are rejected to guarantee predictable response times and local resource safety.

---

## 9. Conclusion

Milestone 5C establishes a production-grade, local multi-page PDF governance engine. Creatives with multiple pages, mixed orientations, and complex layouts are rendered, extracted, and evaluated with precision. Page-level findings, duplicate handling, interactive previews, and strict approval integrity ensure marketing teams and brand reviewers can govern decks and collateral with total confidence.
