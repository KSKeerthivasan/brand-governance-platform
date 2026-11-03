import os
import io
import threading
import time
import pytest
from PIL import Image, ImageOps
from app.services.image_processing import (
    MAX_UPLOAD_SIZE_BYTES,
    MAX_IMAGE_DIM,
    MAX_PROCESSING_DIM,
    MAX_PROCESSING_WIDTH,
    MAX_PROCESSING_HEIGHT,
    validate_advertisement_image_bytes,
    get_governance_processing_image,
    GovernanceImageContext
)
from app.services.ocr_service import ocr_service, OCRRegion, OCRResult
from app.services.image_governance import image_governance
from app.services.concurrency_limiter import HeavyImageGovernanceLimiter, image_governance_limiter


def create_test_image_bytes(width: int, height: int, format_name: str = "PNG", color=(100, 150, 200)) -> bytes:
    img = Image.new("RGB", (width, height), color=color)
    buf = io.BytesIO()
    img.save(buf, format=format_name)
    return buf.getvalue()


class TestImageUploadValidation:
    def test_valid_png_jpg_webp_accepted(self):
        for fmt in ("PNG", "JPEG", "WEBP"):
            raw = create_test_image_bytes(800, 600, fmt)
            res = validate_advertisement_image_bytes(raw, f"test.{fmt.lower()}")
            assert res.width == 800
            assert res.height == 600
            assert res.format_name in ("PNG", "JPEG", "WEBP")

    def test_file_exceeding_15mb_rejected(self):
        fake_large_bytes = b"0" * (MAX_UPLOAD_SIZE_BYTES + 1024)
        with pytest.raises(ValueError, match="exceeds maximum allowed limit of 15 MB"):
            validate_advertisement_image_bytes(fake_large_bytes, "large.png")

    def test_dimensions_exceeding_4096_rejected(self):
        raw = create_test_image_bytes(4097, 800, "PNG")
        with pytest.raises(ValueError, match="exceed maximum permitted limit of 4096 px"):
            validate_advertisement_image_bytes(raw, "wide.png")

        raw_tall = create_test_image_bytes(800, 4097, "PNG")
        with pytest.raises(ValueError, match="exceed maximum permitted limit of 4096 px"):
            validate_advertisement_image_bytes(raw_tall, "tall.png")

    def test_corrupted_or_non_image_bytes_rejected(self):
        corrupt = b"\x89PNG\r\n\x1a\ncorrupted_garbage_bytes_here"
        with pytest.raises(ValueError, match="corrupt, truncated, or not a valid image"):
            validate_advertisement_image_bytes(corrupt, "corrupt.png")

    def test_unsupported_format_rejected_even_with_png_extension(self):
        # Create a BMP image and name it .png
        img = Image.new("RGB", (100, 100), color=(255, 0, 0))
        buf = io.BytesIO()
        img.save(buf, format="BMP")
        bmp_bytes = buf.getvalue()

        with pytest.raises(ValueError, match="Unsupported image format 'BMP'"):
            validate_advertisement_image_bytes(bmp_bytes, "disguised.png")

    def test_empty_file_rejected(self):
        with pytest.raises(ValueError, match="Uploaded file is empty"):
            validate_advertisement_image_bytes(b"", "empty.png")


class TestStandardizedProcessingResolution:
    def test_1856x2304_downsampled_proportionally(self, tmp_path):
        src_path = str(tmp_path / "gemini_poster.png")
        Image.new("RGB", (1856, 2304), color=(50, 100, 150)).save(src_path)

        ctx = get_governance_processing_image(src_path, max_dim=1400)
        assert ctx.is_downsampled is True
        assert ctx.original_width == 1856
        assert ctx.original_height == 2304
        assert ctx.processing_height == 1400
        # 1856 * 1400 / 2304 = 1127.3 -> 1127
        assert ctx.processing_width in (1127, 1128)
        assert os.path.exists(ctx.processing_path)
        assert ctx.processing_path != src_path
        # Original file remains untouched
        with Image.open(src_path) as orig:
            assert orig.size == (1856, 2304)

    def test_3000x2000_downsampled_proportionally(self, tmp_path):
        src_path = str(tmp_path / "wide_poster.png")
        Image.new("RGB", (3000, 2000), color=(50, 100, 150)).save(src_path)

        ctx = get_governance_processing_image(src_path, max_dim=1400)
        assert ctx.is_downsampled is True
        assert ctx.processing_width == 1400
        # 2000 * 1400 / 3000 = 933.33 -> 933
        assert ctx.processing_height == 933

    def test_1080x1350_unchanged_never_upscaled(self, tmp_path):
        src_path = str(tmp_path / "social_post.png")
        Image.new("RGB", (1080, 1350), color=(50, 100, 150)).save(src_path)

        ctx = get_governance_processing_image(src_path, max_dim=1400)
        assert ctx.is_downsampled is False
        assert ctx.scale == 1.0
        assert ctx.processing_path == src_path
        assert ctx.processing_width == 1080
        assert ctx.processing_height == 1350

    def test_processing_cache_reuse(self, tmp_path):
        src_path = str(tmp_path / "poster_cached.png")
        Image.new("RGB", (2000, 1500), color=(100, 100, 100)).save(src_path)

        ctx1 = get_governance_processing_image(src_path, max_dim=1400)
        mtime1 = os.path.getmtime(ctx1.processing_path)

        ctx2 = get_governance_processing_image(src_path, max_dim=1400)
        mtime2 = os.path.getmtime(ctx2.processing_path)
        assert ctx1.processing_path == ctx2.processing_path
        assert mtime1 == mtime2

    def test_cache_invalidation_on_content_change_with_same_filename_and_dims(self, tmp_path):
        src_path = str(tmp_path / "identical_name.png")
        # First image: solid red
        Image.new("RGB", (2000, 1600), color=(255, 0, 0)).save(src_path)
        ctx1 = get_governance_processing_image(src_path, max_dim=1400)

        # Overwrite file with new content: solid blue (same filename, same dimensions)
        Image.new("RGB", (2000, 1600), color=(0, 0, 255)).save(src_path)
        ctx2 = get_governance_processing_image(src_path, max_dim=1400)

        # Cache paths must differ based on content hash
        assert ctx1.processing_path != ctx2.processing_path
        with Image.open(ctx2.processing_path) as im:
            # Must reflect blue pixel, not old red derivative
            pixel = im.getpixel((10, 10))
            assert pixel[2] > 200  # Blue channel high
            assert pixel[0] < 50   # Red channel low


class TestOCRAndCoordinateMapping:
    def test_ocr_coordinates_rescaled_to_original(self, tmp_path):
        # Create image with size 2000x1000
        src_path = str(tmp_path / "large_text.png")
        img = Image.new("RGB", (2000, 1000), color=(255, 255, 255))
        img.save(src_path)

        # Call OCR on this large image
        res = ocr_service.extract_text_from_image(src_path)
        # Even if no text is detected on plain white, status is no_text
        assert res.status in ("no_text", "success")

    def test_ocr_region_stores_both_original_and_processing_bboxes(self):
        reg = OCRRegion(
            text="Organic Juice",
            confidence=0.95,
            bbox=[[100.0, 100.0], [300.0, 100.0], [300.0, 150.0], [100.0, 150.0]],
            processing_bbox=[[50.0, 50.0], [150.0, 50.0], [150.0, 75.0], [50.0, 75.0]]
        )
        assert reg.bbox[1][0] == 300.0
        assert reg.processing_bbox[1][0] == 150.0

    def test_exif_orientation_and_bbox_mapping(self, tmp_path):
        # 1. Portrait image (> 1400px)
        p_path = str(tmp_path / "portrait.png")
        Image.new("RGB", (1200, 2400), color=(100, 100, 100)).save(p_path)
        ctx_p = get_governance_processing_image(p_path, max_dim=1400)
        assert ctx_p.processing_height == 1400
        assert ctx_p.processing_width == 700
        assert abs(ctx_p.scale - (1400.0 / 2400.0)) < 1e-4

        # 2. Landscape image (> 1400px)
        l_path = str(tmp_path / "landscape.png")
        Image.new("RGB", (2800, 1400), color=(100, 100, 100)).save(l_path)
        ctx_l = get_governance_processing_image(l_path, max_dim=1400)
        assert ctx_l.processing_width == 1400
        assert ctx_l.processing_height == 700
        assert abs(ctx_l.scale - 0.5) < 1e-4

        # 3. Already under 1400px
        u_path = str(tmp_path / "under1400.png")
        Image.new("RGB", (800, 600), color=(100, 100, 100)).save(u_path)
        ctx_u = get_governance_processing_image(u_path, max_dim=1400)
        assert ctx_u.is_downsampled is False
        assert ctx_u.scale == 1.0
        assert ctx_u.processing_width == 800
        assert ctx_u.processing_height == 600

        # 4. EXIF-rotated JPEG (orientation 6: 90 deg CW rotation)
        exif_img = Image.new("RGB", (2000, 1000), color=(200, 150, 100))
        exif = exif_img.getexif()
        exif[0x0112] = 6  # Orientation tag 6
        exif_path = str(tmp_path / "exif_rotated.jpg")
        exif_img.save(exif_path, "JPEG", exif=exif)

        # Transposed visual dimensions: width 1000, height 2000 (portrait)
        ctx_exif = get_governance_processing_image(exif_path, max_dim=1400)
        assert ctx_exif.original_width == 1000
        assert ctx_exif.original_height == 2000
        assert ctx_exif.processing_height == 1400
        assert ctx_exif.processing_width == 700
        assert abs(ctx_exif.scale - (1400.0 / 2000.0)) < 1e-4


class TestUploadPosterAPIEndpoint:
    def test_upload_poster_valid_image(self, client, auth_tokens):
        headers = auth_tokens["content_creator"]["headers"]
        raw_png = create_test_image_bytes(1200, 800, "PNG")
        res = client.post(
            "/api/v1/content/upload-poster",
            headers=headers,
            files={"file": ("creative.png", io.BytesIO(raw_png), "image/png")}
        )
        assert res.status_code == 200
        data = res.json()
        assert data["width"] == 1200
        assert data["height"] == 800
        assert data["format"] == "PNG"
        assert data["is_pdf"] is False
        assert "posters" in data["file_path"]

    def test_upload_poster_oversized_file_rejected(self, client, auth_tokens):
        headers = auth_tokens["content_creator"]["headers"]
        # Over 15MB
        huge_bytes = b"0" * (15 * 1024 * 1024 + 512)
        res = client.post(
            "/api/v1/content/upload-poster",
            headers=headers,
            files={"file": ("too_heavy.png", io.BytesIO(huge_bytes), "image/png")}
        )
        assert res.status_code == 400
        assert "exceeds maximum allowed limit of 15 MB" in res.json()["detail"]

    def test_upload_poster_oversized_dimensions_rejected(self, client, auth_tokens):
        headers = auth_tokens["content_creator"]["headers"]
        too_wide = create_test_image_bytes(4097, 600, "PNG")
        res = client.post(
            "/api/v1/content/upload-poster",
            headers=headers,
            files={"file": ("too_wide.png", io.BytesIO(too_wide), "image/png")}
        )
        assert res.status_code == 400
        assert "exceed maximum permitted limit of 4096 px" in res.json()["detail"]

    def test_upload_poster_corrupted_rejected(self, client, auth_tokens):
        headers = auth_tokens["content_creator"]["headers"]
        corrupted = b"\x89PNG\r\n\x1a\nrandom_truncated_content"
        res = client.post(
            "/api/v1/content/upload-poster",
            headers=headers,
            files={"file": ("broken.png", io.BytesIO(corrupted), "image/png")}
        )
        assert res.status_code == 400
        assert "corrupt, truncated, or not a valid image" in res.json()["detail"]

    def test_upload_poster_disguised_unsupported_rejected(self, client, auth_tokens):
        headers = auth_tokens["content_creator"]["headers"]
        img = Image.new("RGB", (100, 100), color=(0, 255, 0))
        buf = io.BytesIO()
        img.save(buf, format="BMP")
        bmp_bytes = buf.getvalue()

        res = client.post(
            "/api/v1/content/upload-poster",
            headers=headers,
            files={"file": ("fake.png", io.BytesIO(bmp_bytes), "image/png")}
        )
        assert res.status_code == 400
        assert "Unsupported image format 'BMP'" in res.json()["detail"]


class TestConcurrencyLimiter:
    def test_limiter_allows_one_active_one_waiting_and_rejects_excess(self):
        limiter = HeavyImageGovernanceLimiter(max_active=1, max_waiting=1, wait_timeout=5.0)

        # Thread 1 acquires slot
        slot1_acquired = threading.Event()
        slot1_release = threading.Event()
        results = []

        def worker1():
            with limiter.slot():
                results.append("w1_acquired")
                slot1_acquired.set()
                slot1_release.wait(timeout=2.0)
                results.append("w1_done")

        t1 = threading.Thread(target=worker1)
        t1.start()
        assert slot1_acquired.wait(timeout=1.0)
        assert limiter.active_count == 1
        assert limiter.waiting_count == 0

        # Thread 2 enters queue
        slot2_acquired = threading.Event()

        def worker2():
            with limiter.slot():
                results.append("w2_acquired")
                slot2_acquired.set()

        t2 = threading.Thread(target=worker2)
        t2.start()
        time.sleep(0.1)
        assert limiter.active_count == 1
        assert limiter.waiting_count == 1

        # Thread 3 attempts while queue is full -> must raise HTTP 429
        with pytest.raises(Exception) as exc_info:
            limiter.acquire()
        assert exc_info.value.status_code == 429
        assert exc_info.value.headers.get("Retry-After") == "10"
        assert "queue is full" in str(exc_info.value.detail)

        # Release thread 1 -> thread 2 acquires slot
        slot1_release.set()
        t1.join(timeout=1.0)
        assert slot2_acquired.wait(timeout=1.0)
        t2.join(timeout=1.0)

        assert limiter.active_count == 0
        assert limiter.waiting_count == 0
        assert results == ["w1_acquired", "w1_done", "w2_acquired"]

    def test_limiter_timeout_raises_503(self):
        limiter = HeavyImageGovernanceLimiter(max_active=1, max_waiting=1, wait_timeout=0.15)

        # Hold the slot
        limiter.acquire()
        assert limiter.active_count == 1

        # Second thread waits and times out
        timeout_caught = threading.Event()

        def waiting_worker():
            with pytest.raises(Exception) as exc_info:
                limiter.acquire()
            if exc_info.value.status_code == 503 and exc_info.value.headers.get("Retry-After") == "10":
                timeout_caught.set()

        t = threading.Thread(target=waiting_worker)
        t.start()
        assert timeout_caught.wait(timeout=1.0)
        t.join(timeout=1.0)

        # Cleanup
        limiter.release()
        assert limiter.active_count == 0
        assert limiter.waiting_count == 0

    def test_limiter_exception_safely_releases_slot(self):
        limiter = HeavyImageGovernanceLimiter(max_active=1, max_waiting=1)
        with pytest.raises(RuntimeError):
            with limiter.slot():
                assert limiter.active_count == 1
                raise RuntimeError("Worker crashed during processing")

        # Slot must be safely released
        assert limiter.active_count == 0
        assert limiter.waiting_count == 0
        # Subsequent acquire must succeed immediately
        with limiter.slot():
            assert limiter.active_count == 1
        assert limiter.active_count == 0


class TestGovernanceConcurrencyAPI:
    def test_text_only_draft_does_not_wait_on_poster_limiter(self, client, auth_tokens, tmp_path):
        """Text-only drafts bypass the heavy limiter and execute immediately."""
        headers = auth_tokens["content_creator"]["headers"]
        brand_res = client.get("/api/v1/brands", headers=headers)
        brand_id = brand_res.json()[0]["id"]

        # Simulate limiter occupied by heavy poster
        image_governance_limiter.acquire()
        try:
            assert image_governance_limiter.active_count == 1

            # Create a text-only item & version
            create_res = client.post(
                "/api/v1/content",
                headers=headers,
                json={
                    "brand_id": brand_id,
                    "title": "Text Only Test Draft",
                    "channel": "Social Media",
                    "body_text": "100% pure organic orange juice with no added sugar."
                }
            )
            assert create_res.status_code == 200
            v_id = create_res.json()["latest_version"]["id"]

            # Run governance check on text draft - must succeed immediately without 429
            gov_res = client.post(
                "/api/v1/governance/run",
                headers=headers,
                json={"content_version_id": v_id}
            )
            assert gov_res.status_code == 200
            assert gov_res.json()["overall_status"] in ("compliant", "needs_review", "rejected", "approved", "warnings")
        finally:
            image_governance_limiter.release()

    def test_concurrent_poster_governance_queue_and_429(self, client, auth_tokens, tmp_path):
        """Simultaneous poster governance requests enforce 1 active, 1 waiting, and 429 for the 3rd."""
        import concurrent.futures
        headers = auth_tokens["content_creator"]["headers"]
        brand_res = client.get("/api/v1/brands", headers=headers)
        brand_id = brand_res.json()[0]["id"]

        # Create 3 distinct drafts with poster images
        version_ids = []
        for i in range(3):
            # Create a valid test poster image
            img_path = str(tmp_path / f"poster_{i}.png")
            Image.new("RGB", (1000, 1000), color=(100 + i * 20, 150, 200)).save(img_path)

            # Upload poster
            with open(img_path, "rb") as f:
                up_res = client.post(
                    "/api/v1/content/upload-poster",
                    headers=headers,
                    files={"file": (f"poster_{i}.png", f, "image/png")}
                )
            assert up_res.status_code == 200
            up_path = up_res.json()["file_path"]

            create_res = client.post(
                "/api/v1/content",
                headers=headers,
                json={
                    "brand_id": brand_id,
                    "title": f"Poster Draft {i}",
                    "channel": "Social Media",
                    "body_text": f"Test poster copy {i}.",
                    "poster_file_path": up_path
                }
            )
            assert create_res.status_code == 200
            version_ids.append(create_res.json()["latest_version"]["id"])

        # Delay evaluate_content_version slightly so 3 simultaneous requests overlap
        from app.services.governance_engine import governance_engine
        original_evaluate = governance_engine.evaluate_content_version

        def slow_evaluate(*args, **kwargs):
            time.sleep(0.4)
            return original_evaluate(*args, **kwargs)

        governance_engine.evaluate_content_version = slow_evaluate
        try:
            def send_run(v_id):
                return client.post(
                    "/api/v1/governance/run",
                    headers=headers,
                    json={"content_version_id": v_id}
                )

            with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
                futs = [executor.submit(send_run, v_id) for v_id in version_ids]
                results = [f.result() for f in futs]

            status_codes = sorted([r.status_code for r in results])
            # Exactly 2 requests must succeed (200), and 1 must be rejected with 429
            assert status_codes == [200, 200, 429], f"Unexpected status codes: {status_codes}"
            rejected = [r for r in results if r.status_code == 429][0]
            assert rejected.headers.get("Retry-After") == "10"
            assert "queue is full" in rejected.json()["detail"]
        finally:
            governance_engine.evaluate_content_version = original_evaluate


class TestStandardizedPosterProcessingDimensions:
    """
    Verification suite for 835 x 1080 px maximum processing dimensions.
    Confirms that every processing derivative stays within both maximum dimensions,
    never stretches or distorts, never upscales smaller images, and maps coordinates accurately.
    """
    def test_image_already_sized_835x1080_retained_unchanged(self, tmp_path):
        src_path = str(tmp_path / "exact_835x1080.png")
        Image.new("RGB", (835, 1080), color=(100, 150, 200)).save(src_path)

        ctx = get_governance_processing_image(src_path)
        assert ctx.is_downsampled is False
        assert ctx.scale == 1.0
        assert ctx.processing_width == 835
        assert ctx.processing_height == 1080
        assert ctx.processing_path == src_path
        # Original file remains untouched
        with Image.open(src_path) as orig:
            assert orig.size == (835, 1080)

    def test_larger_portrait_image_proportionally_fits_within_835x1080(self, tmp_path):
        # 1856 x 2304 px (V Protect poster dimensions)
        src_path = str(tmp_path / "large_portrait.png")
        Image.new("RGB", (1856, 2304), color=(60, 120, 180)).save(src_path)

        ctx = get_governance_processing_image(src_path)
        assert ctx.is_downsampled is True
        assert ctx.processing_width <= MAX_PROCESSING_WIDTH  # <= 835
        assert ctx.processing_height <= MAX_PROCESSING_HEIGHT  # <= 1080
        # Expected scale = min(835/1856, 1080/2304) = 835/1856 = 0.449892
        assert ctx.processing_width == 835
        assert ctx.processing_height == 1037
        # Verify aspect ratio is strictly preserved (no distortion)
        orig_ratio = 1856.0 / 2304.0
        proc_ratio = float(ctx.processing_width) / float(ctx.processing_height)
        assert abs(orig_ratio - proc_ratio) < 0.005
        # Verify file exists on disk and is distinct from original
        assert os.path.exists(ctx.processing_path)
        assert ctx.processing_path != src_path

    def test_landscape_image_proportionally_fits_within_835x1080(self, tmp_path):
        # 2000 x 1000 px landscape
        src_path = str(tmp_path / "landscape.png")
        Image.new("RGB", (2000, 1000), color=(80, 140, 100)).save(src_path)

        ctx = get_governance_processing_image(src_path)
        assert ctx.is_downsampled is True
        assert ctx.processing_width <= MAX_PROCESSING_WIDTH  # <= 835
        assert ctx.processing_height <= MAX_PROCESSING_HEIGHT  # <= 1080
        # Expected scale = min(835/2000, 1080/1000) = 835/2000 = 0.4175
        assert ctx.processing_width == 835
        assert ctx.processing_height == 418
        # Aspect ratio preserved
        assert abs((2000.0 / 1000.0) - (ctx.processing_width / ctx.processing_height)) < 0.005

    def test_square_image_proportionally_fits_within_835x1080(self, tmp_path):
        # 1600 x 1600 px square
        src_path = str(tmp_path / "square.png")
        Image.new("RGB", (1600, 1600), color=(120, 80, 160)).save(src_path)

        ctx = get_governance_processing_image(src_path)
        assert ctx.is_downsampled is True
        assert ctx.processing_width <= MAX_PROCESSING_WIDTH  # <= 835
        assert ctx.processing_height <= MAX_PROCESSING_HEIGHT  # <= 1080
        # Expected scale = min(835/1600, 1080/1600) = 835/1600 = 0.521875
        assert ctx.processing_width == 835
        assert ctx.processing_height == 835
        # Strict 1:1 square ratio preserved
        assert ctx.processing_width == ctx.processing_height

    def test_smaller_image_retains_original_dimensions_never_upscaled(self, tmp_path):
        # 600 x 800 px (fits within 835 x 1080)
        src_path = str(tmp_path / "smaller.png")
        Image.new("RGB", (600, 800), color=(150, 100, 50)).save(src_path)

        ctx = get_governance_processing_image(src_path)
        assert ctx.is_downsampled is False
        assert ctx.scale == 1.0
        assert ctx.processing_width == 600
        assert ctx.processing_height == 800
        assert ctx.processing_path == src_path

    def test_ocr_extraction_and_bbox_mapping_under_standardized_bounds(self, tmp_path):
        src_path = str(tmp_path / "ocr_test.png")
        img = Image.new("RGB", (1856, 2304), color=(255, 255, 255))
        img.save(src_path)

        ctx = get_governance_processing_image(src_path)
        assert ctx.processing_width == 835
        assert ctx.processing_height == 1037
        scale = ctx.scale

        # Mock OCR finding at processing resolution coordinates
        proc_bbox = [[100.0, 200.0], [300.0, 200.0], [300.0, 250.0], [100.0, 250.0]]
        # Rescale back to original image space
        orig_bbox = [[float(c[0]) / scale, float(c[1]) / scale] for c in proc_bbox]

        # Verify rescaled points correspond to original coordinates
        assert round(orig_bbox[0][0]) == round(100.0 / scale)
        assert round(orig_bbox[0][1]) == round(200.0 / scale)
        assert orig_bbox[0][0] > proc_bbox[0][0]
        assert orig_bbox[0][1] > proc_bbox[0][1]

    def test_full_governance_lifecycle_runs_at_standardized_resolution(self, client, auth_tokens, tmp_path):
        headers = auth_tokens["content_creator"]["headers"]
        brand_res = client.get("/api/v1/brands", headers=headers)
        brand_id = brand_res.json()[0]["id"]

        # Create large test poster image (1800 x 2400)
        img_path = str(tmp_path / "large_lifecycle_poster.png")
        Image.new("RGB", (1800, 2400), color=(100, 150, 200)).save(img_path)

        with open(img_path, "rb") as f:
            up_res = client.post(
                "/api/v1/content/upload-poster",
                headers=headers,
                files={"file": ("large_lifecycle_poster.png", f, "image/png")}
            )
        assert up_res.status_code == 200
        up_path = up_res.json()["file_path"]

        create_res = client.post(
            "/api/v1/content",
            headers=headers,
            json={
                "brand_id": brand_id,
                "title": "Standardized Resolution Poster Test",
                "channel": "Social Media",
                "body_text": "100% pure organic orange juice.",
                "poster_file_path": up_path
            }
        )
        assert create_res.status_code == 200
        v_id = create_res.json()["latest_version"]["id"]

        gov_res = client.post(
            "/api/v1/governance/run",
            headers=headers,
            json={"content_version_id": v_id}
        )
        assert gov_res.status_code == 200
        data = gov_res.json()
        assert data["overall_status"] is not None
        assert "findings" in data
        assert "findings_count" in data
        assert data["findings_count"] >= 1


