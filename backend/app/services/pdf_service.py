import os
import io
import time
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from PIL import Image
import pypdf
import pypdfium2

MAX_PDF_FILE_SIZE_BYTES = 25 * 1024 * 1024  # 25 MB
MAX_PDF_PAGE_COUNT = 30  # Bounded execution limit
MIN_PAGE_DIMENSION_POINTS = 10.0
MAX_PAGE_DIMENSION_POINTS = 10000.0
TARGET_RASTER_DIMENSION_PX = 1600.0
MIN_RENDER_SCALE = 1.0
MAX_RENDER_SCALE = 3.0


class PDFValidationError(Exception):
    """Raised when a PDF fails format, signature, encryption, or constraint validation."""
    pass


class PDFRenderError(Exception):
    """Raised when a PDF page cannot be rendered to a raster image."""
    pass


@dataclass
class PDFPageInfo:
    page_number: int  # 1-indexed
    width_pt: float
    height_pt: float
    width_px: int
    height_px: int
    orientation: str  # "portrait", "landscape", "square"
    aspect_ratio: str
    cached_raster_path: Optional[str] = None


@dataclass
class PDFMetadata:
    is_valid: bool
    page_count: int
    file_size_bytes: int
    pages: List[PDFPageInfo] = field(default_factory=list)
    error_message: Optional[str] = None


class PDFService:
    """
    Local multi-page PDF processing and rasterization service.
    Uses pypdfium2 (Apache 2.0 / BSD 3-Clause) for deterministic, local rendering
    and pypdf (BSD 3-Clause) for structure validation. Zero external API calls.
    """

    def validate_pdf_file(self, file_path: str) -> PDFMetadata:
        """
        Validates PDF signature, encryption, corruptions, page limits, and pathological dimensions.
        """
        if not file_path or not os.path.exists(file_path):
            raise PDFValidationError(f"PDF file not found on disk: {file_path}")

        file_size = os.path.getsize(file_path)
        if file_size == 0:
            raise PDFValidationError("PDF file is empty (0 bytes).")

        if file_size > MAX_PDF_FILE_SIZE_BYTES:
            raise PDFValidationError(
                f"PDF file size ({file_size / (1024*1024):.1f}MB) exceeds 25MB limit."
            )

        # 1. Validate File Signature (%PDF-)
        try:
            with open(file_path, "rb") as f:
                header = f.read(1024)
                if b"%PDF-" not in header:
                    raise PDFValidationError(
                        "Invalid PDF file signature. The file header does not begin with '%PDF-'."
                    )
        except PDFValidationError:
            raise
        except Exception as e:
            raise PDFValidationError(f"Could not read PDF header: {str(e)}")

        # 2. Check Encryption and Structural Parsing via pypdf
        try:
            reader = pypdf.PdfReader(file_path)
            if reader.is_encrypted:
                raise PDFValidationError(
                    "PDF is encrypted or password-protected. Encrypted documents cannot be governed automatically."
                )
            pypdf_page_count = len(reader.pages)
        except PDFValidationError:
            raise
        except Exception as e:
            raise PDFValidationError(f"Malformed or unreadable PDF: {str(e)}")

        # 3. Check Page Count Limits
        if pypdf_page_count == 0:
            raise PDFValidationError("PDF document is empty (0 pages).")

        if pypdf_page_count > MAX_PDF_PAGE_COUNT:
            raise PDFValidationError(
                f"PDF page count ({pypdf_page_count}) exceeds the maximum supported limit of {MAX_PDF_PAGE_COUNT} pages."
            )

        # 4. Validate Dimensions and Renderability via pypdfium2
        pages_info: List[PDFPageInfo] = []
        try:
            doc = pypdfium2.PdfDocument(file_path)
            doc_page_count = len(doc)
            if doc_page_count != pypdf_page_count:
                # Potential corrupted stream or dual object table
                pass

            for idx in range(doc_page_count):
                page_num = idx + 1
                page = doc[idx]
                w_pt, h_pt = page.get_size()

                if w_pt < MIN_PAGE_DIMENSION_POINTS or h_pt < MIN_PAGE_DIMENSION_POINTS:
                    raise PDFValidationError(
                        f"Page {page_num} has degenerate dimensions ({w_pt:.1f}x{h_pt:.1f} pt)."
                    )
                if w_pt > MAX_PAGE_DIMENSION_POINTS or h_pt > MAX_PAGE_DIMENSION_POINTS:
                    raise PDFValidationError(
                        f"Page {page_num} has pathological dimensions ({w_pt:.1f}x{h_pt:.1f} pt) exceeding safety limit ({MAX_PAGE_DIMENSION_POINTS} pt)."
                    )

                # Determine orientation
                if abs(w_pt - h_pt) < 1.0:
                    orientation = "square"
                elif w_pt > h_pt:
                    orientation = "landscape"
                else:
                    orientation = "portrait"

                # Calculate aspect ratio string (e.g. 1:1, 16:9, or 4:3)
                ratio_val = w_pt / h_pt if h_pt > 0 else 1.0
                if abs(ratio_val - 1.0) < 0.05:
                    ratio_str = "1:1"
                elif abs(ratio_val - (16.0 / 9.0)) < 0.08:
                    ratio_str = "16:9"
                elif abs(ratio_val - (9.0 / 16.0)) < 0.08:
                    ratio_str = "9:16"
                elif abs(ratio_val - (4.0 / 3.0)) < 0.08:
                    ratio_str = "4:3"
                else:
                    ratio_str = f"{ratio_val:.2f}:1"

                # Estimate default raster dimensions
                scale = self._compute_render_scale(w_pt, h_pt)
                render_w = int(round(w_pt * scale))
                render_h = int(round(h_pt * scale))

                pages_info.append(PDFPageInfo(
                    page_number=page_num,
                    width_pt=round(w_pt, 2),
                    height_pt=round(h_pt, 2),
                    width_px=render_w,
                    height_px=render_h,
                    orientation=orientation,
                    aspect_ratio=ratio_str
                ))

            doc.close()
        except PDFValidationError:
            raise
        except Exception as e:
            raise PDFValidationError(f"PDF rendering engine failed to parse document: {str(e)}")

        return PDFMetadata(
            is_valid=True,
            page_count=len(pages_info),
            file_size_bytes=file_size,
            pages=pages_info
        )

    def _compute_render_scale(self, width_pt: float, height_pt: float) -> float:
        """
        Computes a bounded rendering scale to ensure clear OCR resolution (at least ~150-200 DPI)
        while capping maximum raster dimensions to avoid excessive memory usage.
        """
        max_pt = max(width_pt, height_pt)
        if max_pt <= 0:
            return MIN_RENDER_SCALE
        # Aim for TARGET_RASTER_DIMENSION_PX on longest side
        ideal_scale = TARGET_RASTER_DIMENSION_PX / max_pt
        # Clamp between 1.0 (72 DPI) and 3.0 (216 DPI)
        return max(MIN_RENDER_SCALE, min(MAX_RENDER_SCALE, ideal_scale))

    def render_page_to_pil(self, file_path: str, page_number: int) -> Image.Image:
        """
        Renders a single 1-indexed page of a PDF file to a Pillow RGB Image.
        """
        if not os.path.exists(file_path):
            raise PDFRenderError(f"File not found: {file_path}")

        try:
            doc = pypdfium2.PdfDocument(file_path)
            total_pages = len(doc)
            if page_number < 1 or page_number > total_pages:
                doc.close()
                raise PDFRenderError(
                    f"Requested page {page_number} is out of bounds (document has {total_pages} pages)."
                )

            page = doc[page_number - 1]
            w_pt, h_pt = page.get_size()
            scale = self._compute_render_scale(w_pt, h_pt)

            bitmap = page.render(scale=scale)
            pil_image = bitmap.to_pil().convert("RGB")
            doc.close()
            return pil_image
        except PDFRenderError:
            raise
        except Exception as e:
            raise PDFRenderError(f"Failed to render page {page_number}: {str(e)}")

    def extract_native_text(self, file_path: str, page_number: int) -> str:
        """
        Extracts native embedded text stream from the PDF page using pypdfium2 TextPage.
        """
        if not os.path.exists(file_path):
            return ""

        try:
            doc = pypdfium2.PdfDocument(file_path)
            if page_number < 1 or page_number > len(doc):
                doc.close()
                return ""
            page = doc[page_number - 1]
            textpage = page.get_textpage()
            extracted = textpage.get_text_range()
            doc.close()
            return extracted.strip() if extracted else ""
        except Exception:
            return ""

    def get_or_render_page_cache(
        self,
        file_path: str,
        page_number: int,
        cache_base_dir: str
    ) -> str:
        """
        Renders the requested page and saves it as a PNG file in cache_base_dir.
        If already cached and newer than source PDF, returns the existing file path.
        """
        os.makedirs(cache_base_dir, exist_ok=True)
        cached_file = os.path.join(cache_base_dir, f"page_{page_number}.png")

        pdf_mtime = os.path.getmtime(file_path) if os.path.exists(file_path) else 0
        if os.path.exists(cached_file) and os.path.getmtime(cached_file) >= pdf_mtime:
            return cached_file

        img = self.render_page_to_pil(file_path, page_number)
        img.save(cached_file, "PNG", optimize=True)
        return cached_file


pdf_service = PDFService()
