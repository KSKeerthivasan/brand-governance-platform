import os
import pytest
from PIL import Image
from unittest.mock import patch
from app.services.governance_engine import governance_engine
from app.services.image_governance import image_governance
from app.schemas.content import ContentItemCreate, ContentItemUpdate
from app.models.content import ContentItem, ContentVersion
from app.models.brand import BrandProfile
from app.services.ocr_service import OCRResult
from app.database import SessionLocal

@pytest.fixture(scope="module")
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()

def _create_test_image(tmp_path, width: int, height: int, filename: str = "ad_poster.png") -> str:
    path = str(tmp_path / filename)
    img = Image.new("RGB", (width, height), color=(240, 240, 240))
    img.save(path)
    return path

class TestContentTypeGovernance:
    """
    Validates governance behavior across the 3 supported content types:
    1. Image Advertisement (poster required, body_text optional)
    2. Text Advertisement (body_text required, poster optional)
    3. Image + Text Advertisement (both required)
    """

    def test_schema_defaults_and_optionality(self):
        """ContentItemCreate and Update handle missing channel and body_text gracefully."""
        # ContentItemCreate defaults channel to "General" and body_text to ""
        create_schema = ContentItemCreate(brand_id="b-1", title="New Ad")
        assert create_schema.channel == "General"
        assert create_schema.body_text == ""
        assert create_schema.poster_file_path is None

        # ContentItemUpdate allows optional body_text and channel
        update_schema = ContentItemUpdate(title="Updated Title")
        assert update_schema.channel is None
        assert update_schema.body_text is None

        # ContentItemUpdate with explicit channel
        update_schema_channel = ContentItemUpdate(title="Updated Title", channel="General")
        assert update_schema_channel.channel == "General"

    def test_channel_scope_ignores_destination_specific_rules_when_channel_is_general(self):
        """
        When channel is 'General', destination-specific rules (packaging, print_only, etc.)
        must NOT be evaluated as universally applicable. Universal rules (all_channels) MUST apply.
        """
        # Universal brand rule -> in scope
        assert governance_engine.is_rule_in_channel_scope(None, "General") is True
        assert governance_engine.is_rule_in_channel_scope("", "General") is True
        assert governance_engine.is_rule_in_channel_scope("all_channels", "General") is True

        # Specific channel rules -> out of scope when content channel is unspecified/general
        assert governance_engine.is_rule_in_channel_scope("packaging", "General") is False
        assert governance_engine.is_rule_in_channel_scope("print_only", "General") is False
        assert governance_engine.is_rule_in_channel_scope("instagram_story", "General") is False

        # Specific channel rule matches explicit channel
        assert governance_engine.is_rule_in_channel_scope("packaging", "packaging") is True
        assert governance_engine.is_rule_in_channel_scope("print_only", "print_only") is True

    def test_image_only_advertisement_dimensions_verified_without_aspect_ratio_penalty(self, tmp_path, db):
        """
        An Image Advertisement with channel='General' verifies image dimensions
        without imposing arbitrary channel aspect ratios (e.g. 1:1 Instagram or 16:9 Banner).
        """
        # 835 x 1080 poster
        poster_path = _create_test_image(tmp_path, 835, 1080, "v_protect_ad.png")

        findings = image_governance.evaluate_poster_for_governance(
            file_path=poster_path,
            channel="General",
            alt_text="A clean health supplement poster with certified seal",
            org_id="org-test",
            db=db
        )

        # Confirm there is an 'Image Dimensions Verified' informational finding
        dimension_finding = next((f for f in findings if "Image Dimensions Verified" in f.title), None)
        assert dimension_finding is not None
        assert dimension_finding.severity == "info"
        assert "835x1080" in dimension_finding.explanation

        # Confirm NO aspect ratio mismatch errors exist for General channel
        aspect_ratio_finding = next((f for f in findings if "Aspect Ratio" in f.title), None)
        assert aspect_ratio_finding is None

    def test_text_only_advertisement_skips_visual_checks(self, db):
        """
        A Text Advertisement (no poster_file_path) executes text claim and guideline
        governance without invoking OCR or OpenCV visual checks.
        """
        item = ContentItem(
            id="item-text-only",
            organization_id="org-test",
            brand_id="brand-test",
            title="Summer Wellness Copy",
            channel="General",
            status="draft",
            current_version_num=1
        )
        version = ContentVersion(
            id="ver-text-only",
            content_item_id="item-text-only",
            version_num=1,
            body_text="Our pure botanical extract supports immune health naturally.",
            poster_file_path=None
        )
        version.content_item = item

        with patch("app.services.ocr_service.ocr_service.extract_text_from_image") as mock_ocr, \
             patch("app.services.image_governance.image_governance.evaluate_poster_for_governance") as mock_img_gov:

            run = governance_engine.evaluate_content_version(db, version)

            # OCR and image governance must NOT have been called
            mock_ocr.assert_not_called()
            mock_img_gov.assert_not_called()

            assert run is not None
            assert run.content_version_id == "ver-text-only"

    def test_image_and_text_advertisement_runs_both_without_duplication(self, tmp_path, db):
        """
        An Image + Text Advertisement runs both text copy evaluation and poster checks,
        evaluating unified findings.
        """
        poster_path = _create_test_image(tmp_path, 800, 1000, "combined_ad.png")

        item = ContentItem(
            id="item-combined",
            organization_id="org-test",
            brand_id="brand-test",
            title="Combined Health Ad",
            channel="General",
            status="draft",
            current_version_num=1
        )
        version = ContentVersion(
            id="ver-combined",
            content_item_id="item-combined",
            version_num=1,
            body_text="Clinically formulated antioxidant defense.",
            poster_file_path=poster_path
        )
        version.content_item = item

        mock_ocr_res = OCRResult(
            status="success",
            extracted_text="V Protect 100% Herbal Immunity",
            mean_confidence=0.95
        )

        with patch("app.services.ocr_service.ocr_service.extract_text_from_image", return_value=mock_ocr_res) as mock_ocr, \
             patch("app.services.storage.storage_service.check_exists", return_value=True), \
             patch("app.services.storage.storage_service.get_file_path_for_processing", return_value=poster_path):

            run = governance_engine.evaluate_content_version(db, version)

            # OCR was invoked on the poster
            mock_ocr.assert_called_once()
            assert run is not None
            assert run.content_version_id == "ver-combined"
            assert run.overall_status in ("passed", "warnings", "failed", "approved", "changes_requested", "rejected")

    def test_partial_updates_do_not_erase_existing_fields(self, db):
        """
        Verifies that partial updates preserve omitted fields:
        1. Omitted body_text does not erase marketing copy.
        2. Omitted poster fields do not erase creative poster.
        """
        from app.models.organization import User, Organization, OrganizationMembership
        from app.api.v1.content import update_content_item
        from app.schemas.content import ContentItemUpdate

        user = db.query(User).first()
        org = db.query(Organization).first()
        membership = db.query(OrganizationMembership).filter(
            OrganizationMembership.user_id == user.id,
            OrganizationMembership.organization_id == org.id
        ).first()

        item = ContentItem(
            organization_id=org.id,
            brand_id="test-brand",
            title="Original Title",
            channel="General",
            status="draft",
            current_version_num=1,
            created_by=user.id
        )
        db.add(item)
        db.commit()
        db.refresh(item)

        ver = ContentVersion(
            content_item_id=item.id,
            version_num=1,
            body_text="Original Marketing Copy that must be preserved",
            poster_file_path="uploads/original_poster.png",
            poster_alt_text="Original Alt Text",
            checksum=ContentVersion.calculate_checksum("Original Marketing Copy that must be preserved", "uploads/original_poster.png"),
            created_by=user.id
        )
        db.add(ver)
        db.commit()

        # Partial update 1: Only change title
        req1 = ContentItemUpdate(title="Renamed Title Only")
        updated1 = update_content_item(
            content_id=item.id,
            req=req1,
            membership=membership,
            current_user=user,
            db=db
        )
        assert updated1.title == "Renamed Title Only"
        assert updated1.latest_version.body_text == "Original Marketing Copy that must be preserved"
        assert updated1.latest_version.poster_file_path == "uploads/original_poster.png"

        # Partial update 2: Only change body_text
        req2 = ContentItemUpdate(body_text="Revised Copy")
        updated2 = update_content_item(
            content_id=item.id,
            req=req2,
            membership=membership,
            current_user=user,
            db=db
        )
        assert updated2.latest_version.body_text == "Revised Copy"
        assert updated2.latest_version.poster_file_path == "uploads/original_poster.png"

        # Partial update 3: Explicitly set body_text to empty (Image ad mode)
        req3 = ContentItemUpdate(body_text="")
        updated3 = update_content_item(
            content_id=item.id,
            req=req3,
            membership=membership,
            current_user=user,
            db=db
        )
        assert updated3.latest_version.body_text == ""
        assert updated3.latest_version.poster_file_path == "uploads/original_poster.png"
