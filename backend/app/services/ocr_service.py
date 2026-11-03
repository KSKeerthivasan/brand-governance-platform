import os
import time
import re
from typing import List, Dict, Any, Optional, Tuple, Union
from dataclasses import dataclass, field
from PIL import Image
import numpy as np

def normalize_ocr_spacing(text: str) -> str:
    """
    Normalizes OCR tokens where downsampling or tight tracking causes inter-word spaces to be dropped.
    Splits CamelCase words, uppercase acronyms preceding Titlecase, digits/symbols adjoined to words,
    and punctuation boundaries without altering coordinates.
    """
    if not text:
        return ""
    # 1. Lowercase followed by Uppercase (CamelCase): e.g. MiracleDetox -> Miracle Detox
    s = re.sub(r'([a-z])([A-Z])', r'\1 \2', text)
    # 2. Uppercase acronym followed by Titlecase: e.g. USDACertified -> USDA Certified
    s = re.sub(r'([A-Z]+)([A-Z][a-z])', r'\1 \2', s)
    # 3. Digit or % followed by letter: e.g. 100%USDA -> 100% USDA
    s = re.sub(r'([0-9%])([A-Za-z])', r'\1 \2', s)
    # 4. Punctuation boundaries with &, @: e.g. Free&50% -> Free & 50%
    s = re.sub(r'([a-zA-Z0-9])([&@])', r'\1 \2', s)
    s = re.sub(r'([&@])([a-zA-Z0-9])', r'\1 \2', s)
    return re.sub(r'\s+', ' ', s).strip()

@dataclass
class OCRRegion:
    text: str
    confidence: float
    bbox: List[List[float]]  # [[x1, y1], [x2, y2], [x3, y3], [x4, y4]] in original image coordinates
    processing_bbox: Optional[List[List[float]]] = None  # coordinates in processing/downsampled image
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

from rapidocr_onnxruntime import RapidOCR

class LeanRapidOCR(RapidOCR):
    """
    Lean RapidOCR engine that skips initializing the TextClassifier ONNX session.
    Eliminates ~25 MB of ONNX model allocations and avoids loading cls_infer into memory,
    since angle classification is not used in advertisement poster governance (use_cls=False).
    """
    def __init__(self, **kwargs):
        from rapidocr_onnxruntime.main import (
            TextDetector, TextRecognizer, DEFAULT_CFG_PATH, read_yaml,
            update_model_path, UpdateParameters, CalRecBoxes, LoadImage
        )
        config = update_model_path(read_yaml(DEFAULT_CFG_PATH))
        if kwargs:
            config = UpdateParameters()(config, **kwargs)
        # Configure text recognizer to batch size 1 to minimize transient tensor allocations
        config["Rec"]["rec_batch_num"] = 1
        global_config = config["Global"]
        self.print_verbose = global_config["print_verbose"]
        self.text_score = global_config["text_score"]
        self.min_height = global_config["min_height"]
        self.width_height_ratio = global_config["width_height_ratio"]
        self.use_det = global_config["use_det"]
        self.text_det = TextDetector(config["Det"])
        self.use_cls = False
        self.text_cls = None
        self.use_rec = global_config["use_rec"]
        self.text_rec = TextRecognizer(config["Rec"])
        self.load_img = LoadImage()
        self.max_side_len = global_config["max_side_len"]
        self.min_side_len = global_config["min_side_len"]
        self.cal_rec_boxes = CalRecBoxes()


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
            try:
                import cv2
                cv2.setNumThreads(1)
            except Exception:
                pass
            # Restrict thread execution to 1 to eliminate thread pool overhead and multi-arena memory inflation on Linux containers
            self._engine = LeanRapidOCR(intra_op_num_threads=1, inter_op_num_threads=1)
        return self._engine

    def extract_text_from_image(
        self,
        file_path_or_image: Union[str, Image.Image],
        *args,
        **kwargs
    ) -> OCRResult:
        """
        Extract visible text and bounding boxes from a local raster image file or PIL Image.
        Standardizes inference resolution to fit within max 835 px width and 1080 px height.
        Safely handles missing, corrupt, unsupported, or textless images.
        """
        t0 = time.time()
        from app.services.image_processing import MAX_PROCESSING_WIDTH, MAX_PROCESSING_HEIGHT
        original_scale = kwargs.get("original_scale")
        if original_scale is None and args:
            original_scale = args[0]
        scale = original_scale if original_scale is not None else 1.0

        if isinstance(file_path_or_image, Image.Image):
            pil_img = file_path_or_image
            w, h = pil_img.size
            if (w > MAX_PROCESSING_WIDTH or h > MAX_PROCESSING_HEIGHT) and original_scale is None:
                scale = min(float(MAX_PROCESSING_WIDTH) / float(w), float(MAX_PROCESSING_HEIGHT) / float(h))
                new_w, new_h = max(1, int(round(w * scale))), max(1, int(round(h * scale)))
                resized_pil = pil_img.resize((new_w, new_h), Image.Resampling.LANCZOS)
            else:
                resized_pil = pil_img

            try:
                import cv2
                # RapidOCR expects BGR format when passing a numpy array
                bgr_array = cv2.cvtColor(np.array(resized_pil.convert("RGB")), cv2.COLOR_RGB2BGR)
                engine = self._get_engine()
                raw_result, elapse = engine(bgr_array, use_cls=False)
            except Exception as e:
                return OCRResult(
                    status="failed",
                    error_message=f"OCR execution failure on in-memory image: {str(e)}",
                    latency_ms=(time.time() - t0) * 1000
                )
            finally:
                if 'bgr_array' in locals():
                    del bgr_array
                import gc
                gc.collect()
                try:
                    import ctypes
                    libc = ctypes.CDLL("libc.so.6")
                    libc.malloc_trim(0)
                except Exception:
                    pass
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

            # Validate image and inspect dimensions
            try:
                with Image.open(file_path) as img:
                    w, h = img.size
                    img.verify()
            except Exception as e:
                return OCRResult(
                    status="failed",
                    error_message=f"Corrupt or unreadable image file: {str(e)}",
                    latency_ms=(time.time() - t0) * 1000
                )

            cv_img = None
            resized = None
            try:
                engine = self._get_engine()
                if (w > MAX_PROCESSING_WIDTH or h > MAX_PROCESSING_HEIGHT) and original_scale is None:
                    import cv2
                    scale = min(float(MAX_PROCESSING_WIDTH) / float(w), float(MAX_PROCESSING_HEIGHT) / float(h))
                    cv_img = cv2.imread(file_path)
                    new_w, new_h = max(1, int(round(w * scale))), max(1, int(round(h * scale)))
                    resized = cv2.resize(cv_img, (new_w, new_h), interpolation=cv2.INTER_AREA)
                    raw_result, elapse = engine(resized, use_cls=False)
                else:
                    raw_result, elapse = engine(file_path, use_cls=False)
            except Exception as e:
                return OCRResult(
                    status="failed",
                    error_message=f"OCR execution failure: {str(e)}",
                    latency_ms=(time.time() - t0) * 1000
                )
            finally:
                if cv_img is not None:
                    del cv_img
                if resized is not None:
                    del resized
                import gc
                gc.collect()
                try:
                    import ctypes
                    libc = ctypes.CDLL("libc.so.6")
                    libc.malloc_trim(0)
                except Exception:
                    pass

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
                raw_bbox, text, score = item[0], item[1], float(item[2])
                cleaned_text = str(text).strip()
                if cleaned_text:
                    normalized_text = normalize_ocr_spacing(cleaned_text)
                    if scale != 1.0:
                        scaled_bbox = [[float(c[0]) / scale, float(c[1]) / scale] for c in raw_bbox]
                    else:
                        scaled_bbox = raw_bbox
                    regions.append(OCRRegion(
                        text=normalized_text,
                        confidence=score,
                        bbox=scaled_bbox,
                        processing_bbox=raw_bbox
                    ))
                    text_lines.append(normalized_text)
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
