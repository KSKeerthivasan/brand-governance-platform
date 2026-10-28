import os
import math
import numpy as np
import pytest
from PIL import Image, ImageDraw, ImageFont
import cv2

from app.services.image_governance import (
    image_governance,
    srgb_to_linear,
    calculate_relative_luminance,
    calculate_contrast_ratio,
    LocalizedContrastRegion
)
from app.services.ocr_service import OCRRegion, OCRResult
from app.models.content import GovernanceFinding


def _get_font(size: int = 28):
    try:
        return ImageFont.truetype("arial.ttf", size)
    except Exception:
        return ImageFont.load_default()


# =========================================================================
# 1. NUMERICAL & MATHEMATICAL FORMULA TESTS
# =========================================================================

def test_wcag_numerical_precision_and_srgb_linearization():
    """
    Verifies sRGB linearization and relative luminance against standard reference values:
    - Pure Black (0, 0, 0) -> L = 0.0
    - Pure White (255, 255, 255) -> L = 1.0
    - Contrast ratio Black vs White = 21.0 : 1
    - Pure Yellow (255, 255, 0) on White (255, 255, 255) ~ 1.07 : 1
    - Pure Red (255, 0, 0) on White (255, 255, 255) ~ 4.00 : 1
    - Linearization threshold boundary check at c <= 0.04045
    """
    # Boundary linearization test
    c_below = 0.04045
    c_above = 0.04046
    assert abs(srgb_to_linear(c_below) - (c_below / 12.92)) < 1e-6
    assert abs(srgb_to_linear(c_above) - (((c_above + 0.055) / 1.055) ** 2.4)) < 1e-6

    # Pure black & white
    lum_black = calculate_relative_luminance((0, 0, 0))
    lum_white = calculate_relative_luminance((255, 255, 255))
    assert lum_black == 0.0
    assert abs(lum_white - 1.0) < 1e-6

    # Black vs White contrast = 21.0
    cr_bw = calculate_contrast_ratio(lum_black, lum_white)
    assert abs(cr_bw - 21.0) < 1e-3

    # Pure Yellow on White
    lum_yellow = calculate_relative_luminance((255, 255, 0))
    cr_yellow_white = calculate_contrast_ratio(lum_yellow, lum_white)
    assert 1.07 <= cr_yellow_white <= 1.08  # Standard WCAG ratio is ~1.074:1

    # Pure Red on White
    lum_red = calculate_relative_luminance((255, 0, 0))
    cr_red_white = calculate_contrast_ratio(lum_red, lum_white)
    assert 3.99 <= cr_red_white <= 4.01  # Standard WCAG ratio is ~3.998:1


# =========================================================================
# 2. LOCALIZED CONTRAST IMAGE TESTS
# =========================================================================

def test_1_white_text_over_dark_uniform_background(tmp_path):
    """
    1. White text over dark uniform background (Freshsip Forest Green #1B4332).
       Must pass WCAG AA with CR >= 9.0:1.
    """
    img_path = str(tmp_path / "white_on_dark.png")
    bg_color = (27, 67, 50)  # Forest Green
    fg_color = (255, 255, 255)  # White

    img = Image.new("RGB", (600, 200), color=bg_color)
    draw = ImageDraw.Draw(img)
    font = _get_font(32)
    draw.text((40, 70), "FRESH VALENCIA ORANGE", fill=fg_color, font=font)
    img.save(img_path)

    cv_img = cv2.imread(img_path)
    # Define bounding polygon for the text
    reg = OCRRegion(
        text="FRESH VALENCIA ORANGE",
        confidence=0.98,
        bbox=[[35.0, 65.0], [520.0, 65.0], [520.0, 115.0], [35.0, 115.0]]
    )

    results = image_governance.estimate_localized_text_contrast(cv_img, [reg])
    assert len(results) == 1
    res = results[0]

    assert res.status == "pass"
    assert res.is_reliable
    assert res.contrast_ratio >= 9.0
    assert res.bg_rgb[0] < 40 and res.bg_rgb[1] > 50  # Matches dark green background
    assert res.fg_rgb[0] > 200 and res.fg_rgb[1] > 200  # Matches white text (accounting for font antialiasing)


def test_2_yellow_text_over_white_background(tmp_path):
    """
    2. Yellow text over white background.
       Severe accessibility failure: contrast ratio ~1.07:1, well below 3.0:1.
       Must be flagged as 'fail' (critical violation).
    """
    img_path = str(tmp_path / "yellow_on_white.png")
    bg_color = (255, 255, 255)
    fg_color = (255, 255, 0)  # Bright yellow

    img = Image.new("RGB", (600, 200), color=bg_color)
    draw = ImageDraw.Draw(img)
    font = _get_font(32)
    draw.text((40, 70), "SUMMER CITRUS REFRESH", fill=fg_color, font=font)
    img.save(img_path)

    cv_img = cv2.imread(img_path)
    reg = OCRRegion(
        text="SUMMER CITRUS REFRESH",
        confidence=0.95,
        bbox=[[35.0, 65.0], [530.0, 65.0], [530.0, 115.0], [35.0, 115.0]]
    )

    results = image_governance.estimate_localized_text_contrast(cv_img, [reg])
    assert len(results) == 1
    res = results[0]

    assert res.status == "fail"
    assert res.contrast_ratio < 2.0  # Extremely low contrast
    assert res.is_reliable


def test_3_dark_text_over_light_background(tmp_path):
    """
    3. Dark text over a light background.
       Charcoal (#1E1E1E) text over Cream (#FBF8F3) background.
       Must pass WCAG AA with CR >= 10:1.
    """
    img_path = str(tmp_path / "dark_on_light.png")
    bg_color = (251, 248, 243)  # Soft cream
    fg_color = (30, 30, 30)      # Charcoal

    img = Image.new("RGB", (600, 200), color=bg_color)
    draw = ImageDraw.Draw(img)
    font = _get_font(28)
    draw.text((40, 70), "100% Cold-Pressed Organic", fill=fg_color, font=font)
    img.save(img_path)

    cv_img = cv2.imread(img_path)
    reg = OCRRegion(
        text="100% Cold-Pressed Organic",
        confidence=0.97,
        bbox=[[35.0, 65.0], [480.0, 65.0], [480.0, 110.0], [35.0, 110.0]]
    )

    results = image_governance.estimate_localized_text_contrast(cv_img, [reg])
    assert len(results) == 1
    res = results[0]

    assert res.status == "pass"
    assert res.contrast_ratio >= 10.0


def test_4_light_text_over_unsuitable_local_background(tmp_path):
    """
    4. Light text on a dark poster that fails specifically because the LOCAL
       background behind the text is a bright highlight/glare spot.
       Demonstrates that localized background sampling detects local failures
       that whole-image averaging would miss.
    """
    img_path = str(tmp_path / "local_glare_failure.png")
    # Overall image is dark navy (15, 25, 45)
    img = Image.new("RGB", (800, 400), color=(15, 25, 45))
    draw = ImageDraw.Draw(img)

    # Draw a bright cream/white glare banner right behind the text
    draw.rectangle([40, 140, 600, 260], fill=(245, 245, 240))

    # Draw white text directly inside the bright glare banner
    font = _get_font(28)
    draw.text((60, 180), "Unreadable White on Glare", fill=(255, 255, 255), font=font)
    img.save(img_path)

    cv_img = cv2.imread(img_path)
    reg = OCRRegion(
        text="Unreadable White on Glare",
        confidence=0.94,
        bbox=[[50.0, 170.0], [450.0, 170.0], [450.0, 220.0], [50.0, 220.0]]
    )

    results = image_governance.estimate_localized_text_contrast(cv_img, [reg])
    assert len(results) == 1
    res = results[0]

    # Contrast ratio must fail because local halo is bright cream (245, 245, 240)
    assert res.contrast_ratio < 2.0
    assert res.status == "fail"


def test_5_multiple_text_regions_different_outcomes(tmp_path):
    """
    5. A poster with multiple text regions having different contrast outcomes:
       - Region A (Headline): Crisp white on dark green -> PASS (CR >= 9:1)
       - Region B (Subtitle): Low-contrast olive/dark-gray on dark green -> FAIL (CR < 3:1)
    """
    img_path = str(tmp_path / "multi_region_poster.png")
    bg_color = (20, 50, 35)  # Dark green
    img = Image.new("RGB", (800, 500), color=bg_color)
    draw = ImageDraw.Draw(img)

    font_large = _get_font(36)
    font_small = _get_font(20)

    # Line 1: High contrast headline (White)
    draw.text((50, 100), "HIGH CONTRAST HEADLINE", fill=(255, 255, 255), font=font_large)

    # Line 2: Low contrast subtitle (Dark muted olive #3A5038)
    draw.text((50, 250), "Low contrast unreadable fine print disclaimer", fill=(60, 80, 60), font=font_small)
    img.save(img_path)

    cv_img = cv2.imread(img_path)
    reg_headline = OCRRegion(
        text="HIGH CONTRAST HEADLINE",
        confidence=0.99,
        bbox=[[45.0, 90.0], [550.0, 90.0], [550.0, 150.0], [45.0, 150.0]]
    )
    reg_subtitle = OCRRegion(
        text="Low contrast unreadable fine print disclaimer",
        confidence=0.92,
        bbox=[[45.0, 240.0], [600.0, 240.0], [600.0, 280.0], [45.0, 280.0]]
    )

    results = image_governance.estimate_localized_text_contrast(cv_img, [reg_headline, reg_subtitle])
    assert len(results) == 2

    res_h = next(r for r in results if "HEADLINE" in r.text)
    res_s = next(r for r in results if "fine print" in r.text)

    assert res_h.status == "pass"
    assert res_h.contrast_ratio >= 8.0

    assert res_s.status == "fail"
    assert res_s.contrast_ratio < 3.0


def test_6_photographic_background_with_bright_and_dark_areas_outside_text(tmp_path):
    """
    6. A split photographic-style background (bright sky on left, dark forest on right).
       White text is positioned entirely within the dark forest section.
       Localized contrast must correctly evaluate against the dark section and pass,
       even though the left half of the image is bright white.
    """
    img_path = str(tmp_path / "split_photo.png")
    img = Image.new("RGB", (800, 400))
    draw = ImageDraw.Draw(img)

    # Left half: pure bright white
    draw.rectangle([0, 0, 400, 400], fill=(255, 255, 255))
    # Right half: deep dark navy
    draw.rectangle([400, 0, 800, 400], fill=(15, 20, 40))

    # Text placed on the dark right side
    font = _get_font(30)
    draw.text((450, 180), "PURE BOTANICALS", fill=(255, 255, 255), font=font)
    img.save(img_path)

    cv_img = cv2.imread(img_path)
    reg = OCRRegion(
        text="PURE BOTANICALS",
        confidence=0.98,
        bbox=[[440.0, 170.0], [750.0, 170.0], [750.0, 225.0], [440.0, 225.0]]
    )

    results = image_governance.estimate_localized_text_contrast(cv_img, [reg])
    assert len(results) == 1
    res = results[0]

    assert res.status == "pass"
    assert res.contrast_ratio >= 10.0
    # Confirms local background is navy, not the white from the left half
    assert res.bg_rgb[0] < 30 and res.bg_rgb[2] > 25


def test_7_gradient_background_where_local_contrast_varies(tmp_path):
    """
    7. Vertical gradient from black at top to white at bottom.
       White text at the top passes, while identical white text at the bottom fails.
    """
    img_path = str(tmp_path / "vertical_gradient.png")
    h, w = 600, 600
    grad = np.tile(np.linspace(0, 255, h, dtype=np.uint8)[:, None], (1, w))
    grad_rgb = np.stack([grad, grad, grad], axis=-1)

    img = Image.fromarray(grad_rgb)
    draw = ImageDraw.Draw(img)
    font = _get_font(28)

    # Text 1 near top (black background)
    draw.text((50, 60), "WHITE TEXT ON DARK TOP", fill=(255, 255, 255), font=font)
    # Text 2 near bottom (white background)
    draw.text((50, 500), "WHITE TEXT ON LIGHT BOTTOM", fill=(255, 255, 255), font=font)
    img.save(img_path)

    cv_img = cv2.imread(img_path)
    reg_top = OCRRegion(
        text="WHITE TEXT ON DARK TOP",
        confidence=0.95,
        bbox=[[45.0, 50.0], [500.0, 50.0], [500.0, 100.0], [45.0, 100.0]]
    )
    reg_bottom = OCRRegion(
        text="WHITE TEXT ON LIGHT BOTTOM",
        confidence=0.95,
        bbox=[[45.0, 490.0], [520.0, 490.0], [520.0, 540.0], [45.0, 540.0]]
    )

    results = image_governance.estimate_localized_text_contrast(cv_img, [reg_top, reg_bottom])
    assert len(results) == 2

    res_t = next(r for r in results if "TOP" in r.text)
    res_b = next(r for r in results if "BOTTOM" in r.text)

    assert res_t.status == "pass"
    assert res_t.contrast_ratio >= 6.0

    assert res_b.status == "fail"
    assert res_b.contrast_ratio < 2.0


def test_8_rotated_or_skewed_text_polygons(tmp_path):
    """
    8. Rotated or non-axis-aligned polygon.
       Verifies cv2.fillPoly and minAreaRect handle rotation without crashing
       and properly calculate contrast.
    """
    img_path = str(tmp_path / "rotated_text.png")
    bg_color = (25, 45, 65)  # Dark blue
    img = Image.new("RGB", (600, 400), color=bg_color)

    # Render text to an RGBA layer, rotate by 12 degrees, and composite
    txt_layer = Image.new("RGBA", (320, 60), (25, 45, 65, 0))
    d = ImageDraw.Draw(txt_layer)
    font = _get_font(28)
    d.text((10, 10), "ROTATED BADGE", fill=(250, 250, 250, 255), font=font)
    rotated = txt_layer.rotate(12, expand=True, resample=Image.Resampling.BICUBIC)

    img.paste(rotated, (100, 120), rotated)
    img.save(img_path)

    cv_img = cv2.imread(img_path)
    reg = OCRRegion(
        text="ROTATED BADGE",
        confidence=0.95,
        bbox=[[105.0, 125.0], [405.0, 185.0], [390.0, 245.0], [90.0, 185.0]]
    )

    results = image_governance.estimate_localized_text_contrast(cv_img, [reg])
    assert len(results) == 1
    res = results[0]

    assert res.contrast_ratio >= 6.0
    assert res.is_reliable
    assert res.status == "pass"


def test_9_text_close_to_image_boundary(tmp_path):
    """
    9. Text directly on image boundary [0, 0] to [200, 40].
       Verifies boundary clipping avoids IndexError during dilation.
    """
    img_path = str(tmp_path / "boundary_text.png")
    img = Image.new("RGB", (400, 300), color=(20, 20, 20))
    draw = ImageDraw.Draw(img)
    font = _get_font(20)
    draw.text((5, 5), "EDGE WATERMARK", fill=(240, 240, 240), font=font)
    img.save(img_path)

    cv_img = cv2.imread(img_path)
    reg = OCRRegion(
        text="EDGE WATERMARK",
        confidence=0.92,
        bbox=[[0.0, 0.0], [220.0, 0.0], [220.0, 35.0], [0.0, 35.0]]
    )

    # Must execute safely without index error
    results = image_governance.estimate_localized_text_contrast(cv_img, [reg])
    assert len(results) == 1
    assert results[0].contrast_ratio >= 5.0


def test_10_poster_with_no_ocr_detected_text(tmp_path):
    """
    10. A poster with zero OCR-detected text.
        evaluate_poster_for_governance must emit a clean 'passed_check' finding
        indicating text contrast check is not applicable.
    """
    img_path = str(tmp_path / "no_text_photo.png")
    img = Image.new("RGB", (1080, 1080), color=(30, 80, 60))
    img.save(img_path)

    ocr_empty = OCRResult(status="no_text", extracted_text="", regions=[])
    findings = image_governance._evaluate_localized_text_contrast(
        file_path=img_path,
        ocr_result=ocr_empty
    )

    assert len(findings) == 1
    f = findings[0]
    assert f.category == "contrast"
    assert f.status == "passed_check"
    assert "No Embedded Text Detected" in f.title


def test_11_low_confidence_ocr_results(tmp_path):
    """
    11. Low-confidence OCR extraction.
        Findings must evaluate available regions and document uncertainty.
    """
    img_path = str(tmp_path / "low_conf_poster.png")
    img = Image.new("RGB", (600, 300), color=(30, 30, 30))
    draw = ImageDraw.Draw(img)
    font = _get_font(24)
    draw.text((50, 100), "Uncertain Blurred Text", fill=(200, 200, 200), font=font)
    img.save(img_path)

    ocr_low_conf = OCRResult(
        status="low_confidence",
        extracted_text="Uncertain Blurred Text",
        mean_confidence=0.45,
        regions=[OCRRegion(
            text="Uncertain Blurred Text",
            confidence=0.45,
            bbox=[[40.0, 90.0], [350.0, 90.0], [350.0, 140.0], [40.0, 140.0]]
        )]
    )

    findings = image_governance._evaluate_localized_text_contrast(
        file_path=img_path,
        ocr_result=ocr_low_conf
    )

    assert len(findings) >= 1
    contrast_findings = [f for f in findings if f.category == "contrast"]
    assert len(contrast_findings) >= 1


def test_12_inconclusive_when_text_and_background_cannot_be_separated(tmp_path):
    """
    12. An image where foreground and background colors cannot be reliably separated
        (e.g., solid gray block where text and background have identical color).
        Must return 'inconclusive' (unable_to_verify) rather than a fabricated pass.
    """
    img_path = str(tmp_path / "camouflaged.png")
    # Both background and polygon are identical gray (128, 128, 128)
    img = Image.new("RGB", (400, 200), color=(128, 128, 128))
    img.save(img_path)

    cv_img = cv2.imread(img_path)
    reg = OCRRegion(
        text="Invisible Text",
        confidence=0.80,
        bbox=[[50.0, 50.0], [300.0, 50.0], [300.0, 100.0], [50.0, 100.0]]
    )

    results = image_governance.estimate_localized_text_contrast(cv_img, [reg])
    assert len(results) == 1
    res = results[0]

    assert res.status == "inconclusive"
    assert not res.is_reliable
    assert "Unable to reliably separate text strokes" in res.notes


# =========================================================================
# 3. END-TO-END GOVERNANCE INTEGRATION TEST
# =========================================================================

def test_14_end_to_end_governance_integration_with_localized_contrast(client, auth_tokens):
    """
    14. Verifies that running unified governance on a draft with an attached poster
        produces detailed localized contrast findings with bounding box provenance
        and correct WCAG statuses.
    """
    headers = auth_tokens["content_creator"]["headers"]
    res_b = client.get("/api/v1/brands", headers=headers)
    assert res_b.status_code == 200
    brand_id = res_b.json()[0]["id"]

    test_poster = "./storage_data/19a8a675-7b45-4834-8836-de1996c2a919/knowledge/campaign_citrus_ginger_pending.png"
    assert os.path.exists(test_poster), f"Poster asset required: {test_poster}"

    res_draft = client.post("/api/v1/content", headers=headers, json={
        "brand_id": brand_id,
        "title": "Localized Contrast Integration Campaign",
        "channel": "Instagram Post",
        "body_text": "Taste the revitalizing goodness of 100% cold-pressed Valencia oranges with no added sugar.",
        "poster_file_path": test_poster,
        "poster_alt_text": "Bottle of Freshsip Sparkling Citrus on natural wooden table"
    })
    assert res_draft.status_code == 200
    v_id = res_draft.json()["latest_version"]["id"]

    res_gov = client.post("/api/v1/governance/run", headers=headers, json={
        "content_version_id": v_id
    })
    assert res_gov.status_code == 200
    data = res_gov.json()

    contrast_findings = [f for f in data["findings"] if f["category"] == "contrast"]
    assert len(contrast_findings) >= 1

    # Verify that finding contains localized details
    cf = contrast_findings[0]
    assert cf["status"] in ("passed_check", "verified_issue", "unable_to_verify")
    assert "WCAG" in cf["source_citation"] or "WCAG" in cf["title"]
    assert "Contrast" in cf["title"]


# =========================================================================
# 4. MILESTONE 5A.1 THRESHOLD & SEVERITY MAPPING TESTS
# =========================================================================

def test_threshold_normal_text_below_3_to_1_fails_critical(tmp_path):
    """
    Normal text (< 24px height) with contrast ratio < 3.0:1.
    Must fail with severity='critical' and status='verified_issue'.
    """
    img_path = str(tmp_path / "normal_below_3.png")
    # Black background (0, 0, 0), dark gray text (75, 75, 75) -> CR ~ 2.2:1
    img = Image.new("RGB", (400, 150), color=(0, 0, 0))
    d = ImageDraw.Draw(img)
    font = _get_font(16)  # Small normal text (height < 24px)
    d.text((30, 50), "Fine Print Terms", fill=(75, 75, 75), font=font)
    img.save(img_path)

    cv_img = cv2.imread(img_path)
    reg = OCRRegion(
        text="Fine Print Terms",
        confidence=0.95,
        bbox=[[25.0, 45.0], [250.0, 45.0], [250.0, 70.0], [25.0, 70.0]]  # Height = 25px max, small text
    )

    findings = image_governance._evaluate_localized_text_contrast(
        file_path=img_path,
        ocr_result=OCRResult(status="success", extracted_text="Fine Print Terms", regions=[reg])
    )
    assert len(findings) == 1
    f = findings[0]
    assert f.status == "verified_issue"
    assert f.severity == "critical"
    assert "Insufficient Text Contrast" in f.title


def test_threshold_normal_text_between_3_and_4_5_fails_warning(tmp_path):
    """
    Normal text (< 24px height) with contrast ratio between 3.0:1 and 4.5:1.
    Fails the 4.5:1 normal text threshold; must produce severity='warning'.
    """
    img_path = str(tmp_path / "normal_between_3_and_45.png")
    # Black background (0, 0, 0), medium gray text (115, 115, 115) -> CR ~ 3.4:1
    img = Image.new("RGB", (400, 150), color=(0, 0, 0))
    d = ImageDraw.Draw(img)
    font = _get_font(18)  # Normal text
    d.text((30, 50), "Nutritional Values", fill=(115, 115, 115), font=font)
    img.save(img_path)

    cv_img = cv2.imread(img_path)
    reg = OCRRegion(
        text="Nutritional Values",
        confidence=0.96,
        bbox=[[25.0, 45.0], [260.0, 45.0], [260.0, 68.0], [25.0, 68.0]],  # Height = 23px
        is_known_normal_text=True
    )

    findings = image_governance._evaluate_localized_text_contrast(
        file_path=img_path,
        ocr_result=OCRResult(status="success", extracted_text="Nutritional Values", regions=[reg])
    )
    assert len(findings) == 1
    f = findings[0]
    assert f.status == "verified_issue"
    assert f.severity == "warning"
    assert "4.5:1" in f.text_excerpt or "4.5:1" in f.explanation


def test_threshold_normal_text_above_4_5_passes(tmp_path):
    """
    Normal text (< 24px height) with contrast ratio >= 4.5:1.
    Must pass with severity='info' and status='passed_check'.
    """
    img_path = str(tmp_path / "normal_above_45.png")
    # Navy background (10, 20, 50), white text (255, 255, 255) -> CR ~ 14:1
    img = Image.new("RGB", (400, 150), color=(10, 20, 50))
    d = ImageDraw.Draw(img)
    font = _get_font(18)
    d.text((30, 50), "Approved Body Copy", fill=(255, 255, 255), font=font)
    img.save(img_path)

    cv_img = cv2.imread(img_path)
    reg = OCRRegion(
        text="Approved Body Copy",
        confidence=0.98,
        bbox=[[25.0, 45.0], [260.0, 45.0], [260.0, 68.0], [25.0, 68.0]],
        is_known_normal_text=True
    )

    findings = image_governance._evaluate_localized_text_contrast(
        file_path=img_path,
        ocr_result=OCRResult(status="success", extracted_text="Approved Body Copy", regions=[reg])
    )
    assert len(findings) == 1
    f = findings[0]
    assert f.status == "passed_check"
    assert f.severity == "info"
    assert "Verified" in f.title


def test_threshold_large_text_below_3_to_1_fails_critical(tmp_path):
    """
    Verified large headline text (height >= 36px) with contrast ratio < 3.0:1.
    Fails even the lenient 3.0:1 threshold; must produce severity='critical'.
    """
    img_path = str(tmp_path / "large_below_3.png")
    # Dark brown (45, 20, 10), muted dark rust (130, 55, 30) -> CR ~ 2.4:1
    img = Image.new("RGB", (600, 200), color=(45, 20, 10))
    d = ImageDraw.Draw(img)
    font = _get_font(42)  # Large headline (height > 40px)
    d.text((30, 50), "MAJOR HEADLINE", fill=(130, 55, 30), font=font)
    img.save(img_path)

    cv_img = cv2.imread(img_path)
    reg = OCRRegion(
        text="MAJOR HEADLINE",
        confidence=0.97,
        bbox=[[25.0, 40.0], [450.0, 40.0], [450.0, 105.0], [25.0, 105.0]],  # Height = 65px
        is_known_large_text=True
    )

    findings = image_governance._evaluate_localized_text_contrast(
        file_path=img_path,
        ocr_result=OCRResult(status="success", extracted_text="MAJOR HEADLINE", regions=[reg])
    )
    assert len(findings) == 1
    f = findings[0]
    assert f.status == "verified_issue"
    assert f.severity == "critical"
    assert "Insufficient Text Contrast" in f.title or "Insufficient Large Text" in f.title


def test_threshold_large_text_between_3_and_4_5_passes_large_criterion(tmp_path):
    """
    Verified large headline text (with confirmed source metadata) with contrast ratio between 3.0:1 and 4.5:1.
    Under WCAG AA, qualifying large text requires only 3.0:1, so this MUST PASS
    with status='passed_check' while noting the 3.0:1 large-text standard in explanation.
    """
    img_path = str(tmp_path / "large_between_3_and_45.png")
    # Black background (0, 0, 0), medium gray text (115, 115, 115) -> CR ~ 3.4:1
    img = Image.new("RGB", (600, 200), color=(0, 0, 0))
    d = ImageDraw.Draw(img)
    font = _get_font(44)  # Prominent large display text (height > 40px)
    d.text((30, 50), "VERIFIED DISPLAY HEADLINE", fill=(115, 115, 115), font=font)
    img.save(img_path)

    cv_img = cv2.imread(img_path)
    reg = OCRRegion(
        text="VERIFIED DISPLAY HEADLINE",
        confidence=0.99,
        bbox=[[25.0, 40.0], [550.0, 40.0], [550.0, 110.0], [25.0, 110.0]],  # Height = 70px
        is_known_large_text=True
    )

    results = image_governance.estimate_localized_text_contrast(cv_img, [reg])
    assert len(results) == 1
    res = results[0]

    assert res.is_large_text
    assert res.font_classification == "verified_large_text"
    assert res.threshold == 3.0
    assert 3.0 <= res.contrast_ratio < 4.5
    assert res.status == "pass"

    findings = image_governance._evaluate_localized_text_contrast(
        file_path=img_path,
        ocr_result=OCRResult(status="success", extracted_text="VERIFIED DISPLAY HEADLINE", regions=[reg])
    )
    assert len(findings) == 1
    f = findings[0]
    assert f.status == "passed_check"
    assert f.severity == "info"
    assert "3.0:1" in f.explanation or "3.0:1" in f.text_excerpt


def test_threshold_large_text_above_4_5_passes(tmp_path):
    """
    Verified large text with contrast ratio >= 4.5:1.
    Must pass with status='passed_check'.
    """
    img_path = str(tmp_path / "large_above_45.png")
    # Deep Forest Green (27, 67, 50), pure white (255, 255, 255) -> CR ~ 11.2:1
    img = Image.new("RGB", (600, 200), color=(27, 67, 50))
    d = ImageDraw.Draw(img)
    font = _get_font(44)
    d.text((30, 50), "SUMMER CITRUS", fill=(255, 255, 255), font=font)
    img.save(img_path)

    cv_img = cv2.imread(img_path)
    reg = OCRRegion(
        text="SUMMER CITRUS",
        confidence=0.99,
        bbox=[[25.0, 40.0], [450.0, 40.0], [450.0, 110.0], [25.0, 110.0]],
        is_known_large_text=True
    )

    results = image_governance.estimate_localized_text_contrast(cv_img, [reg])
    assert len(results) == 1
    res = results[0]
    assert res.is_large_text
    assert res.contrast_ratio >= 9.0
    assert res.status == "pass"


# =========================================================================
# 5. MILESTONE 5A.2 RASTER TYPOGRAPHY & MANUAL-REVIEW INTEGRITY TESTS
# =========================================================================

def test_unknown_raster_typography_between_3_and_4_5_requires_manual_review(tmp_path):
    """
    Milestone 5A.2 Requirement:
    Unknown raster typography between 3:1 and 4.5:1 does NOT receive an automatic pass.
    Even when pixel bounding box is tall (e.g. 70px), raster pixel dimensions alone
    do not establish WCAG-qualified large text.
    Must emit a 'warning' severity finding with status='unable_to_verify' requiring manual review.
    """
    img_path = str(tmp_path / "unknown_raster_3_to_45.png")
    # Black background (0, 0, 0), medium gray text (115, 115, 115) -> CR ~ 3.4:1
    img = Image.new("RGB", (600, 200), color=(0, 0, 0))
    d = ImageDraw.Draw(img)
    font = _get_font(44)  # Tall raster text (height ~ 70px)
    d.text((30, 50), "UNVERIFIED POSTER COPY", fill=(115, 115, 115), font=font)
    img.save(img_path)

    cv_img = cv2.imread(img_path)
    # NO is_known_large_text or source typography metadata provided!
    reg = OCRRegion(
        text="UNVERIFIED POSTER COPY",
        confidence=0.98,
        bbox=[[25.0, 40.0], [550.0, 40.0], [550.0, 110.0], [25.0, 110.0]]
    )

    results = image_governance.estimate_localized_text_contrast(cv_img, [reg])
    assert len(results) == 1
    res = results[0]

    # Must be classified as an unverified raster estimate with conservative 4.5:1 threshold
    assert res.font_classification == "unverified_raster_estimate"
    assert res.threshold == 4.5
    assert not res.is_large_text
    assert 3.0 <= res.contrast_ratio < 4.5
    assert res.status == "marginal"  # Not 'pass'!

    findings = image_governance._evaluate_localized_text_contrast(
        file_path=img_path,
        ocr_result=OCRResult(status="success", extracted_text="UNVERIFIED POSTER COPY", regions=[reg])
    )
    assert len(findings) == 1
    f = findings[0]
    assert f.status == "unable_to_verify"
    assert f.severity == "warning"
    assert "Unverified Typography Scale" in f.title
    assert "manual review" in f.title.lower() or "manual review" in f.explanation.lower()
    assert "heuristic" in f.explanation.lower()


def test_unknown_raster_typography_above_4_5_passes_conservative_threshold(tmp_path):
    """
    Milestone 5A.2 Requirement:
    Unknown raster typography with contrast ratio >= 4.5:1 passes the conservative threshold
    cleanly without needing to certify whether it is large text or bold.
    """
    img_path = str(tmp_path / "unknown_raster_high_cr.png")
    # Black background (0, 0, 0), pure white text (255, 255, 255) -> CR ~ 21:1
    img = Image.new("RGB", (600, 200), color=(0, 0, 0))
    d = ImageDraw.Draw(img)
    font = _get_font(36)
    d.text((30, 50), "CLEAR HIGH CONTRAST", fill=(255, 255, 255), font=font)
    img.save(img_path)

    cv_img = cv2.imread(img_path)
    reg = OCRRegion(
        text="CLEAR HIGH CONTRAST",
        confidence=0.99,
        bbox=[[25.0, 40.0], [500.0, 40.0], [500.0, 100.0], [25.0, 100.0]]
    )

    results = image_governance.estimate_localized_text_contrast(cv_img, [reg])
    assert len(results) == 1
    res = results[0]
    assert res.threshold == 4.5  # Conservative baseline applied
    assert res.status == "pass"

    findings = image_governance._evaluate_localized_text_contrast(
        file_path=img_path,
        ocr_result=OCRResult(status="success", extracted_text="CLEAR HIGH CONTRAST", regions=[reg])
    )
    assert len(findings) == 1
    f = findings[0]
    assert f.status == "passed_check"
    assert f.severity == "info"
    assert "Conservative 4.5:1 Baseline" in f.title


def test_inconclusive_separation_emits_warning_not_silent_pass(tmp_path):
    """
    Milestone 5A.2 Requirement:
    An inconclusive accessibility result (e.g. inability to separate text from background)
    must emit a 'warning' severity finding with status='unable_to_verify' so it cannot
    silently bypass the approval workflow without reviewer review.
    """
    img_path = str(tmp_path / "camouflaged_box.png")
    # Solid gray canvas (128, 128, 128)
    img = Image.new("RGB", (400, 200), color=(128, 128, 128))
    img.save(img_path)

    reg = OCRRegion(
        text="Invisible Text",
        confidence=0.85,
        bbox=[[50.0, 50.0], [300.0, 50.0], [300.0, 100.0], [50.0, 100.0]]
    )

    findings = image_governance._evaluate_localized_text_contrast(
        file_path=img_path,
        ocr_result=OCRResult(status="success", extracted_text="Invisible Text", regions=[reg])
    )
    assert len(findings) == 1
    f = findings[0]
    assert f.severity == "warning"  # Crucial: Warning, not Info!
    assert f.status == "unable_to_verify"
    assert "Visual Review Recommended" in f.title


def test_raster_only_pixel_measurements_labeled_as_heuristic_estimates(tmp_path):
    """
    Milestone 5A.2 Requirement:
    Raster-only pixel measurements must be explicitly labeled as heuristic estimates,
    never falsely claiming certified WCAG conformance.
    """
    img_path = str(tmp_path / "heuristic_label_test.png")
    img = Image.new("RGB", (400, 150), color=(20, 20, 20))
    d = ImageDraw.Draw(img)
    font = _get_font(28)
    d.text((20, 40), "Brand Tagline", fill=(180, 180, 180), font=font)
    img.save(img_path)

    cv_img = cv2.imread(img_path)
    reg = OCRRegion(
        text="Brand Tagline",
        confidence=0.95,
        bbox=[[15.0, 35.0], [250.0, 35.0], [250.0, 80.0], [15.0, 80.0]]
    )

    results = image_governance.estimate_localized_text_contrast(cv_img, [reg])
    assert len(results) == 1
    res = results[0]
    assert res.font_classification == "unverified_raster_estimate"
    assert "heuristic only" in res.notes.lower()
    assert "not verified typography" in res.notes.lower()


def test_resolution_variation_does_not_forge_large_text_qualification(tmp_path):
    """
    Milestone 5A.2 Requirement:
    Scaling a raster canvas (e.g. 1x vs 4x resolution) increases raw pixel height,
    but does NOT forge WCAG large-text qualification without source metadata.
    Both low-res and high-res versions of unverified typography at ~3.4:1 contrast
    must consistently apply the conservative 4.5:1 threshold and require manual review.
    """
    # 1. Low resolution canvas (300x100), font size 18
    low_res_path = str(tmp_path / "low_res_banner.png")
    img_low = Image.new("RGB", (300, 100), color=(0, 0, 0))
    d_low = ImageDraw.Draw(img_low)
    font_low = _get_font(18)
    d_low.text((20, 30), "SUMMER SALE", fill=(115, 115, 115), font=font_low)
    img_low.save(low_res_path)

    # 2. High resolution canvas (1200x400), font size 72 (4x pixel height!)
    high_res_path = str(tmp_path / "high_res_banner.png")
    img_high = Image.new("RGB", (1200, 400), color=(0, 0, 0))
    d_high = ImageDraw.Draw(img_high)
    font_high = _get_font(72)
    d_high.text((80, 120), "SUMMER SALE", fill=(115, 115, 115), font=font_high)
    img_high.save(high_res_path)

    cv_low = cv2.imread(low_res_path)
    reg_low = OCRRegion(
        text="SUMMER SALE",
        confidence=0.98,
        bbox=[[15.0, 25.0], [250.0, 25.0], [250.0, 55.0], [15.0, 55.0]]  # Height = 30px
    )

    cv_high = cv2.imread(high_res_path)
    reg_high = OCRRegion(
        text="SUMMER SALE",
        confidence=0.98,
        bbox=[[60.0, 100.0], [1000.0, 100.0], [1000.0, 220.0], [60.0, 220.0]]  # Height = 120px
    )

    res_low = image_governance.estimate_localized_text_contrast(cv_low, [reg_low])[0]
    res_high = image_governance.estimate_localized_text_contrast(cv_high, [reg_high])[0]

    # Both have contrast ratio ~3.4:1
    assert 3.0 <= res_low.contrast_ratio < 4.5
    assert 3.0 <= res_high.contrast_ratio < 4.5

    # Crucial assertion: despite 120px height on high-res canvas, neither is certified
    # as WCAG large text without source metadata! Both consistently require manual review.
    assert res_low.font_classification == "unverified_raster_estimate"
    assert res_high.font_classification == "unverified_raster_estimate"
    assert res_low.threshold == 4.5
    assert res_high.threshold == 4.5
    assert res_low.status == "marginal"
    assert res_high.status == "marginal"


def test_unresolved_accessibility_in_approval_workflow_requires_justification(client, auth_tokens, tmp_path):
    """
    Milestone 5A.2 Requirement:
    Verify that unresolved accessibility findings (such as unverified typography between 3:1 and 4.5:1)
    remain visible and correctly enforced in the approval workflow:
    1. Content with active warnings can be submitted.
    2. Governance status is 'warnings'.
    3. Reviewer CANNOT approve without a recorded justification comment (HTTP 400).
    4. Reviewer CAN approve when a substantive justification comment is provided.
    """
    creator_headers = auth_tokens["content_creator"]["headers"]
    reviewer_headers = auth_tokens["approval_manager"]["headers"]

    # 1. Create test image with unverified raster typography at ~3.4:1 contrast
    poster_path = str(tmp_path / "marginal_approval_test.png")
    img = Image.new("RGB", (600, 300), color=(0, 0, 0))
    d = ImageDraw.Draw(img)
    font = _get_font(36)
    d.text((40, 80), "DISCOUNT OFFER", fill=(115, 115, 115), font=font)
    img.save(poster_path)

    # 2. Get brand ID
    res_b = client.get("/api/v1/brands", headers=creator_headers)
    assert res_b.status_code == 200
    brand_id = res_b.json()[0]["id"]

    # 3. Create content draft
    res_draft = client.post("/api/v1/content", headers=creator_headers, json={
        "brand_id": brand_id,
        "title": "Campaign with Marginal Accessibility",
        "channel": "Social Media",
        "body_text": "Enjoy our exclusive refreshing citrus drink today.",
        "poster_file_path": poster_path,
        "poster_alt_text": "Promotional poster displaying discount offer"
    })
    assert res_draft.status_code == 200
    item_id = res_draft.json()["id"]
    version_id = res_draft.json()["latest_version"]["id"]

    # 4. Run governance
    res_gov = client.post("/api/v1/governance/run", headers=creator_headers, json={
        "content_version_id": version_id
    })
    assert res_gov.status_code == 200
    gov_data = res_gov.json()

    # Governance status MUST be 'warnings' because of the unverified typography contrast warning!
    assert gov_data["overall_status"] == "warnings"
    contrast_warnings = [
        f for f in gov_data["findings"]
        if f["category"] == "contrast" and f["severity"] == "warning"
    ]
    assert len(contrast_warnings) >= 1

    # 5. Creator submits for approval
    res_sub = client.post("/api/v1/approvals/submit", headers=creator_headers, json={
        "content_item_id": item_id,
        "content_version_id": version_id,
        "submission_notes": "Submitted with marginal contrast; requesting reviewer sign-off."
    })
    assert res_sub.status_code == 200
    sub_id = res_sub.json()["id"]

    # 6. Reviewer attempts to approve WITHOUT justification comment -> MUST FAIL (HTTP 400)
    res_appr_fail = client.post(f"/api/v1/approvals/submissions/{sub_id}/decide", headers=reviewer_headers, json={
        "decision": "approved",
        "comments": ""
    })
    assert res_appr_fail.status_code == 400
    assert "warning" in res_appr_fail.json()["detail"].lower()
    assert "justification" in res_appr_fail.json()["detail"].lower()

    # 7. Reviewer approves WITH valid justification comment -> MUST SUCCEED (HTTP 200)
    res_appr_ok = client.post(f"/api/v1/approvals/submissions/{sub_id}/decide", headers=reviewer_headers, json={
        "decision": "approved",
        "comments": "Visually verified on high-brightness test display: text is legible and clear."
    })
    assert res_appr_ok.status_code == 200
    assert res_appr_ok.json()["decision"] == "approved"
    assert res_appr_ok.json()["decision_label"] == "Approved — Ready to Publish"


