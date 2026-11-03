import os
import pytest
from PIL import Image
from app.services.image_governance import image_governance, CHANNEL_DIMENSION_STANDARDS
from app.database import SessionLocal

@pytest.fixture(scope="module")
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()

def _create_test_image(tmp_path, width: int, height: int, filename: str = "aspect_test.png") -> str:
    path = str(tmp_path / filename)
    img = Image.new("RGB", (width, height), color=(255, 255, 255))
    img.save(path)
    return path

def test_aspect_ratio_077_passes_social_media_with_clear_range(tmp_path, db):
    """
    Verifies that an image with 0.77:1 aspect ratio on Social Media channel:
    1. Passes because Social Media allows standard 1:1 with ±0.25 tolerance (0.75:1 to 1.25:1).
    2. The finding explanation and text_excerpt explicitly state the permitted range,
       eliminating any contradiction.
    """
    # 770 x 1000 => 0.77:1 ratio
    img_path = _create_test_image(tmp_path, 800, 1039, "social_media_077.png")
    # 800 / 1039 ~ 0.77

    findings = image_governance.evaluate_poster_for_governance(
        file_path=img_path,
        db=db,
        org_id="test-org",
        brand_id="test-brand",
        channel="Social Media",
        alt_text="Descriptive alt text for poster graphic."
    )

    ar_findings = [f for f in findings if f.category == "dimensions" and "Aspect Ratio" in f.title]
    assert len(ar_findings) == 1
    f = ar_findings[0]
    assert f.status == "passed_check"
    assert f.severity == "info"
    assert "0.77:1" in f.explanation
    assert "0.75:1 to 1.25:1" in f.explanation
    assert "Social Media" in f.explanation
    assert "±25%" in f.explanation
    assert "Permitted: 0.75:1–1.25:1" in f.text_excerpt

def test_aspect_ratio_deviating_outside_range_fails_with_clear_range(tmp_path, db):
    """
    Verifies that an image outside the allowed range (e.g. 0.70:1 on Social Media)
    fails and clearly states the allowed range.
    """
    # 800 x 1143 => ~0.70:1 ratio (outside 0.75 - 1.25)
    img_path = _create_test_image(tmp_path, 800, 1143, "social_media_070.png")

    findings = image_governance.evaluate_poster_for_governance(
        file_path=img_path,
        db=db,
        org_id="test-org",
        brand_id="test-brand",
        channel="Social Media",
        alt_text="Descriptive alt text for poster graphic."
    )

    ar_findings = [f for f in findings if f.category == "dimensions" and "Aspect Ratio" in f.title]
    assert len(ar_findings) == 1
    f = ar_findings[0]
    assert f.status == "verified_issue"
    assert f.severity == "warning"
    assert "Aspect Ratio Mismatch" in f.title
    assert "0.7:1" in f.explanation or "0.70:1" in f.explanation
    assert "0.75:1 to 1.25:1" in f.explanation

def test_aspect_ratio_strict_instagram_post_fails_077(tmp_path, db):
    """
    Verifies that on Instagram Post (tolerance ±0.05, allowed 0.95:1 to 1.05:1),
    an 0.77:1 image correctly triggers a mismatch.
    """
    img_path = _create_test_image(tmp_path, 1080, 1403, "insta_077.png")
    # 1080 / 1403 ~ 0.77

    findings = image_governance.evaluate_poster_for_governance(
        file_path=img_path,
        db=db,
        org_id="test-org",
        brand_id="test-brand",
        channel="Instagram Post",
        alt_text="Descriptive alt text for poster graphic."
    )

    ar_findings = [f for f in findings if f.category == "dimensions" and "Aspect Ratio" in f.title]
    assert len(ar_findings) == 1
    f = ar_findings[0]
    assert f.status == "verified_issue"
    assert f.severity == "warning"
    assert "0.95:1 to 1.05:1" in f.explanation
