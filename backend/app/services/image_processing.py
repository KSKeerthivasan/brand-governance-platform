import os
import io
import gc
import hashlib
import logging
from dataclasses import dataclass
from typing import Optional, Tuple, List, Union
from PIL import Image, ImageOps

logger = logging.getLogger(__name__)

# System limits for advertisement image processing
MAX_UPLOAD_SIZE_BYTES = 15 * 1024 * 1024  # 15 MB
MAX_IMAGE_DIM = 4096  # 4096 px maximum dimension
MAX_PROCESSING_DIM = 1400  # 1400 px longest edge for governance operations
ALLOWED_IMAGE_FORMATS = {"PNG", "JPEG", "WEBP"}
ALLOWED_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}


@dataclass
class ImageValidationResult:
    width: int
    height: int
    format_name: str
    color_mode: str
    size_bytes: int


@dataclass
class GovernanceImageContext:
    original_path: str
    processing_path: str
    original_width: int
    original_height: int
    processing_width: int
    processing_height: int
    scale: float  # processing_dim / original_dim (1.0 if not downsampled)
    is_downsampled: bool


def validate_advertisement_image_bytes(file_bytes: bytes, filename: str) -> ImageValidationResult:
    """
    Validates advertisement creative image bytes against strict safety criteria:
    - Maximum upload file size: 15 MB.
    - True image format validation: must be PNG, JPEG, or WEBP (content-based, not just extension).
    - Image integrity: rejects corrupt, truncated, or unreadable files.
    - EXIF orientation: correctly accounts for EXIF orientation when measuring dimensions.
    - Maximum dimensions: rejects files exceeding 4096 px on either axis.
    """
    if not file_bytes:
        raise ValueError("Uploaded file is empty.")

    if len(file_bytes) > MAX_UPLOAD_SIZE_BYTES:
        size_mb = len(file_bytes) / (1024 * 1024)
        raise ValueError(f"File size ({size_mb:.1f} MB) exceeds maximum allowed limit of 15 MB.")

    # 1. Verify basic file integrity and format
    try:
        with Image.open(io.BytesIO(file_bytes)) as test_img:
            format_name = (test_img.format or "").upper()
            test_img.verify()
    except Exception:
        raise ValueError("The uploaded file is corrupt, truncated, or not a valid image.")

    if format_name not in ALLOWED_IMAGE_FORMATS:
        raise ValueError(f"Unsupported image format '{format_name}'. Supported formats: PNG, JPG, WEBP.")

    # 2. Decode image with EXIF transposition to measure true visual dimensions
    try:
        with Image.open(io.BytesIO(file_bytes)) as img:
            transposed = ImageOps.exif_transpose(img)
            w, h = transposed.size
            mode = transposed.mode
    except Exception:
        raise ValueError("The uploaded image could not be decoded or processed.")

    # 3. Check maximum dimension limit (4096 px)
    if w > MAX_IMAGE_DIM or h > MAX_IMAGE_DIM:
        raise ValueError(
            f"Image dimensions ({w}x{h} px) exceed maximum permitted limit of {MAX_IMAGE_DIM} px on either axis."
        )

    return ImageValidationResult(
        width=w,
        height=h,
        format_name=format_name,
        color_mode=mode,
        size_bytes=len(file_bytes)
    )


def compute_image_content_hash(file_path: str) -> str:
    """
    Computes a cryptographic SHA-256 digest prefix of the original image content
    to guarantee strict processing-cache invalidation.
    """
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()[:16]


def get_governance_processing_image(
    original_local_path: str,
    max_dim: int = MAX_PROCESSING_DIM
) -> GovernanceImageContext:
    """
    Returns an optimized processing copy for governance operations (OCR, contrast, logo matching).
    - Preserves original image completely untouched in private storage.
    - Standardizes longest edge to at most max_dim (1400 px).
    - Never upscales smaller images.
    - Preserves aspect ratio.
    - Uses high-quality LANCZOS downsampling.
    - Accounts for EXIF orientation.
    - Caches the processing copy alongside the local original keyed by content hash for instant reuse across runs.
    """
    if not os.path.exists(original_local_path):
        raise FileNotFoundError(f"Original image file not found on disk: {original_local_path}")

    # Inspect original dimensions with EXIF orientation
    try:
        with Image.open(original_local_path) as orig_img:
            transposed = ImageOps.exif_transpose(orig_img)
            orig_w, orig_h = transposed.size
    except Exception as e:
        # Corrupt, truncated, or unsupported format: return context pointing to original path
        # so downstream validators and OCR can emit specific domain findings safely
        return GovernanceImageContext(
            original_path=original_local_path,
            processing_path=original_local_path,
            original_width=0,
            original_height=0,
            processing_width=0,
            processing_height=0,
            scale=1.0,
            is_downsampled=False
        )

    longest_edge = max(orig_w, orig_h)
    if longest_edge <= max_dim:
        return GovernanceImageContext(
            original_path=original_local_path,
            processing_path=original_local_path,
            original_width=orig_w,
            original_height=orig_h,
            processing_width=orig_w,
            processing_height=orig_h,
            scale=1.0,
            is_downsampled=False
        )

    # Calculate proportional downscaled dimensions
    scale = float(max_dim) / float(longest_edge)
    proc_w = max(1, int(round(orig_w * scale)))
    proc_h = max(1, int(round(orig_h * scale)))

    # Compute content hash for reliable cache invalidation
    try:
        content_hash = compute_image_content_hash(original_local_path)
    except Exception:
        content_hash = "nohash"

    # Deterministic cache path in a .proc_cache subfolder keyed by content hash
    file_dir = os.path.dirname(original_local_path)
    base_name = os.path.basename(original_local_path)
    proc_cache_dir = os.path.join(file_dir, ".proc_cache")
    proc_file_name = f"proc_{max_dim}_{proc_w}x{proc_h}_{content_hash}_{base_name}.png"
    proc_path = os.path.join(proc_cache_dir, proc_file_name)

    # Check if previously generated processing derivative exists
    if os.path.exists(proc_path) and os.path.getsize(proc_path) > 0:
        return GovernanceImageContext(
            original_path=original_local_path,
            processing_path=proc_path,
            original_width=orig_w,
            original_height=orig_h,
            processing_width=proc_w,
            processing_height=proc_h,
            scale=scale,
            is_downsampled=True
        )

    # Generate the standardized processing copy
    try:
        os.makedirs(proc_cache_dir, exist_ok=True)
        with Image.open(original_local_path) as orig_img:
            transposed = ImageOps.exif_transpose(orig_img)
            resized = transposed.resize((proc_w, proc_h), Image.Resampling.LANCZOS)
            tmp_proc = f"{proc_path}.tmp_{os.getpid()}"
            resized.save(tmp_proc, format="PNG", optimize=True)
            os.replace(tmp_proc, proc_path)
            del resized, transposed
            gc.collect()
    except Exception as e:
        logger.warning(
            f"Failed to create cached processing copy at {proc_path}: {e}. Falling back to original path."
        )
        return GovernanceImageContext(
            original_path=original_local_path,
            processing_path=original_local_path,
            original_width=orig_w,
            original_height=orig_h,
            processing_width=orig_w,
            processing_height=orig_h,
            scale=1.0,
            is_downsampled=False
        )

    return GovernanceImageContext(
        original_path=original_local_path,
        processing_path=proc_path,
        original_width=orig_w,
        original_height=orig_h,
        processing_width=proc_w,
        processing_height=proc_h,
        scale=scale,
        is_downsampled=True
    )

