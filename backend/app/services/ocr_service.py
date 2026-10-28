import os
import time
from typing import List, Dict, Any, Optional, Tuple, Union
from dataclasses import dataclass, field
from PIL import Image
import numpy as np

@dataclass
class OCRRegion:
    text: str
    confidence: float
    bbox: List[List[float]]  # [[x1, y1], [x2, y2], [x3, y3], [x4, y4]]
    is_known_large_text: Optional[bool] = None
    is_known_normal_text: Optional[bool] = None
    typography_metadata: Optional[Dict[str, Any]] = None

@dataclass
class OCRResult:
    status: str  # "success", "no_text", "low_confidence", "failed", "unsupported_format"
    extracted_text: str = ""
    regions: List[OCRRegion] = field(default_factory=list)
    mean_confidence: float = 0.0
    error_message: Optional[str] = None
    latency_ms: float = 0.0

SUPPORTED_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff"}

class OCRService:
    """
    Local OCR Service using RapidOCR (ONNX Runtime).
    Runs completely offline on local CPU/GPU, preserving privacy and confidential assets.
    """
    def __init__(self, confidence_threshold: float = 0.60):
        self._engine = None
        self.confidence_threshold = confidence_threshold

    def _get_engine(self):
        """Lazy load RapidOCR engine on first usage to optimize application startup."""
        if self._engine is None:
            from rapidocr_onnxruntime import RapidOCR
            self._engine = RapidOCR()
        return self._engine

    def extract_text_from_image(self, file_path_or_image: Union[str, Image.Image]) -> OCRResult:
        """
        Extract visible text and bounding boxes from a local raster image file or PIL Image.
        Safely handles missing, corrupt, unsupported, or textless images.
        """
        t0 = time.time()

        if isinstance(file_path_or_image, Image.Image):
            try:
                rgb_img = file_path_or_image.convert("RGB")
                img_array = np.array(rgb_img)
                engine = self._get_engine()
                raw_result, elapse = engine(img_array)
            except Exception as e:
                return OCRResult(
                    status="failed",
                    error_message=f"OCR execution failure on in-memory image: {str(e)}",
                    latency_ms=(time.time() - t0) * 1000
                )
        else:
            file_path = file_path_or_image
            if not file_path or not os.path.exists(file_path):
                return OCRResult(
                    status="failed",
                    error_message=f"Image file not found: {file_path}",
                    latency_ms=(time.time() - t0) * 1000
                )

            _, ext = os.path.splitext(file_path)
            if ext.lower() not in SUPPORTED_IMAGE_EXTENSIONS:
                return OCRResult(
                    status="unsupported_format",
                    error_message=f"Unsupported image format '{ext}'. Supported: {sorted(list(SUPPORTED_IMAGE_EXTENSIONS))}",
                    latency_ms=(time.time() - t0) * 1000
                )

            # Validate that image can be opened by PIL (corrupt file check)
            try:
                with Image.open(file_path) as img:
                    img.verify()
            except Exception as e:
                return OCRResult(
                    status="failed",
                    error_message=f"Corrupt or unreadable image file: {str(e)}",
                    latency_ms=(time.time() - t0) * 1000
                )

            # Run OCR inference
            try:
                engine = self._get_engine()
                raw_result, elapse = engine(file_path)
            except Exception as e:
                return OCRResult(
                    status="failed",
                    error_message=f"OCR execution failure: {str(e)}",
                    latency_ms=(time.time() - t0) * 1000
                )

        latency_ms = (time.time() - t0) * 1000

        if not raw_result:
            return OCRResult(
                status="no_text",
                extracted_text="",
                regions=[],
                mean_confidence=0.0,
                latency_ms=latency_ms
            )

        regions: List[OCRRegion] = []
        text_lines: List[str] = []
        confidences: List[float] = []

        for item in raw_result:
            if len(item) >= 3:
                bbox, text, score = item[0], item[1], float(item[2])
                cleaned_text = str(text).strip()
                if cleaned_text:
                    regions.append(OCRRegion(
                        text=cleaned_text,
                        confidence=score,
                        bbox=bbox
                    ))
                    text_lines.append(cleaned_text)
                    confidences.append(score)

        if not regions:
            return OCRResult(
                status="no_text",
                extracted_text="",
                regions=[],
                mean_confidence=0.0,
                latency_ms=latency_ms
            )

        mean_conf = sum(confidences) / len(confidences) if confidences else 0.0
        status = "low_confidence" if mean_conf < self.confidence_threshold else "success"

        return OCRResult(
            status=status,
            extracted_text="\n".join(text_lines),
            regions=regions,
            mean_confidence=mean_conf,
            latency_ms=latency_ms
        )

ocr_service = OCRService()
