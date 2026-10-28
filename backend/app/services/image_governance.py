import os
import re
import math
from dataclasses import dataclass
from typing import Dict, Any, List, Optional, Tuple, Union
from PIL import Image
import numpy as np
import cv2
from sqlalchemy.orm import Session
from app.models.content import GovernanceFinding
from app.models.knowledge import KnowledgeRule, KnowledgeFact, BrandAsset
from app.services.ocr_service import OCRRegion, OCRResult

def srgb_to_linear(c_norm: float) -> float:
    """
    Applies standard IEC 61966-2-1 / WCAG 2.1 sRGB linearization.
    Normalizes each channel to [0, 1] then evaluates piecewise gamma expansion.
    """
    if c_norm <= 0.04045:
        return c_norm / 12.92
    return ((c_norm + 0.055) / 1.055) ** 2.4

def calculate_relative_luminance(rgb: Union[Tuple[int, int, int], List[int], np.ndarray]) -> float:
    """
    Calculates WCAG 2.1 relative luminance:
    L = 0.2126 * R_lin + 0.7152 * G_lin + 0.0722 * B_lin
    """
    r_lin = srgb_to_linear(float(rgb[0]) / 255.0)
    g_lin = srgb_to_linear(float(rgb[1]) / 255.0)
    b_lin = srgb_to_linear(float(rgb[2]) / 255.0)
    return 0.2126 * r_lin + 0.7152 * g_lin + 0.0722 * b_lin

def calculate_contrast_ratio(l1: float, l2: float) -> float:
    """
    Calculates WCAG 2.1 contrast ratio: (Llighter + 0.05) / (Ldarker + 0.05)
    """
    lighter = max(float(l1), float(l2))
    darker = min(float(l1), float(l2))
    return (lighter + 0.05) / (darker + 0.05)

@dataclass
class LocalizedContrastRegion:
    text: str
    bbox: List[List[float]]
    contrast_ratio: float
    fg_rgb: Tuple[int, int, int]
    bg_rgb: Tuple[int, int, int]
    fg_luminance: float
    bg_luminance: float
    threshold: float
    is_large_text: bool
    is_reliable: bool
    status: str  # "pass", "marginal", "fail", "inconclusive"
    method: str
    notes: str
    font_classification: str = "normal_text"
    stroke_width: float = 0.0

CHANNEL_DIMENSION_STANDARDS = {
    "Instagram Post": {"aspect_ratio": "1:1", "min_width": 1080, "min_height": 1080, "tolerance": 0.05},
    "Instagram Story": {"aspect_ratio": "9:16", "min_width": 1080, "min_height": 1920, "tolerance": 0.05},
    "Social Media": {"aspect_ratio": "1:1", "min_width": 800, "min_height": 800, "tolerance": 0.25},
    "Website Banner": {"aspect_ratio": "16:9", "min_width": 1200, "min_height": 675, "tolerance": 0.08},
    "Print Ad": {"color_mode": "CMYK", "min_dpi": 300},
}

class ImageGovernanceService:
    """
    Local image governance and compliance checker.
    Performs real deterministic visual analysis using Pillow, OpenCV, and NumPy:
    1. Image format, dimensions, and aspect ratio vs channel standards.
    2. Dominant-colour clustering (k-means) against approved brand colors.
    3. WCAG 2.1 relative luminance text/background contrast measurement.
    4. Multi-scale template matching against uploaded official brand logos.
    5. Screen-reader alternative text accessibility verification.
    6. Explicit declaration of unavailable/non-automated checks.
    """

    def inspect_image(
        self,
        file_path: str,
        channel: str = "Social Media",
        alt_text: Optional[str] = None,
        is_logo: bool = False
    ) -> Dict[str, Any]:
        """
        Backwards-compatible inspection method for standalone image checker.
        """
        if not os.path.exists(file_path):
            return {
                "passed": False,
                "findings": ["Image file not found on disk."],
                "recommendations": ["Ensure asset is correctly uploaded to storage."]
            }

        findings: List[str] = []
        recommendations: List[str] = []

        try:
            with Image.open(file_path) as img:
                width, height = img.size
                mode = img.mode
                format_name = img.format or "UNKNOWN"

                # 1. Accessibility Check: Alt Text
                if not alt_text or len(alt_text.strip()) < 10:
                    findings.append("Accessibility Violation: Missing or inadequate alternative text (Alt-Text < 10 chars).")
                    recommendations.append("Provide descriptive alt-text explaining visual content for screen-reader accessibility.")

                # 2. Color Mode Check
                expected_spec = CHANNEL_DIMENSION_STANDARDS.get(channel, {})
                if channel == "Print Ad":
                    if mode != "CMYK":
                        findings.append(f"Color Space Warning: Image uses '{mode}' color space instead of 'CMYK' required for print.")
                        recommendations.append("Convert asset to CMYK color profile before sending to press.")
                else:
                    if mode not in ["RGB", "RGBA"]:
                        findings.append(f"Web Optimization Warning: Color space '{mode}' may not render consistently across web browsers.")
                        recommendations.append("Export creative in sRGB color profile.")

                # 3. Minimum Resolution
                min_w = expected_spec.get("min_width", 800)
                min_h = expected_spec.get("min_height", 800)
                if width < min_w or height < min_h:
                    findings.append(f"Resolution Deficiency: Image is {width}x{height}px, below the recommended {min_w}x{min_h}px for {channel}.")
                    recommendations.append(f"Upload high-resolution asset meeting at least {min_w}x{min_h}px.")

                # 4. Aspect Ratio Check
                actual_ratio = width / max(height, 1)
                target_ratio_str = expected_spec.get("aspect_ratio")
                if target_ratio_str:
                    num, den = [float(x) for x in target_ratio_str.split(":")]
                    expected_ratio = num / den
                    tolerance = expected_spec.get("tolerance", 0.08)
                    if abs(actual_ratio - expected_ratio) > tolerance:
                        findings.append(f"Aspect Ratio Non-Compliance: Creative ratio is {round(actual_ratio, 2)}:1, expected {target_ratio_str} for {channel}.")
                        recommendations.append(f"Crop creative to match {target_ratio_str} standard for {channel}.")

                passed = len([f for f in findings if "Violation" in f or "Deficiency" in f]) == 0

                return {
                    "passed": passed,
                    "dimensions": f"{width}x{height}px",
                    "aspect_ratio": f"{round(actual_ratio, 2)}:1",
                    "color_mode": mode,
                    "format": format_name,
                    "findings": findings,
                    "recommendations": recommendations
                }

        except Exception as e:
            return {
                "passed": False,
                "findings": [f"Failed to inspect image: {e}"],
                "recommendations": ["Verify image file integrity."]
            }

    def evaluate_poster_for_governance(
        self,
        file_path: str,
        channel: str,
        alt_text: Optional[str],
        org_id: str,
        db: Session,
        brand_id: Optional[str] = None,
        ocr_result: Optional[OCRResult] = None,
        page_number: Optional[int] = None
    ) -> List[GovernanceFinding]:
        """
        Executes unified, deterministic visual checks on an advertisement poster.
        Returns a list of GovernanceFinding models with categorized results.
        Enforces organization and brand isolation using approved knowledge.
        """
        findings: List[GovernanceFinding] = []

        if not os.path.exists(file_path):
            findings.append(GovernanceFinding(
                category="asset",
                severity="critical",
                title="Poster File Missing on Disk",
                explanation=f"Attached creative file could not be located at '{file_path}'.",
                text_excerpt=file_path,
                source_citation="Storage Service",
                recommended_action="Re-upload the creative asset to attach a valid file.",
                status="verified_issue"
            ))
            return findings

        try:
            # -------------------------------------------------------------
            # CHECK 1: Format, Dimensions & Aspect Ratio
            # -------------------------------------------------------------
            with Image.open(file_path) as pil_img:
                width, height = pil_img.size
                mode = pil_img.mode
                format_name = pil_img.format or "UNKNOWN"
                actual_ratio = width / max(height, 1)

            spec = CHANNEL_DIMENSION_STANDARDS.get(channel, CHANNEL_DIMENSION_STANDARDS["Social Media"])
            min_w = spec.get("min_width", 800)
            min_h = spec.get("min_height", 800)
            target_ratio_str = spec.get("aspect_ratio")

            # Resolution evaluation
            if width < min_w or height < min_h:
                findings.append(GovernanceFinding(
                    category="dimensions",
                    severity="warning",
                    title=f"Resolution Deficiency for {channel}",
                    explanation=f"Creative resolution is {width}x{height}px, below the required minimum of {min_w}x{min_h}px for {channel}.",
                    text_excerpt=f"{width}x{height}px (Min: {min_w}x{min_h}px)",
                    source_citation=f"Channel Standards ({channel})",
                    recommended_action=f"Export asset at minimum {min_w}x{min_h}px to ensure crisp rendering on {channel}.",
                    status="verified_issue"
                ))
            else:
                findings.append(GovernanceFinding(
                    category="dimensions",
                    severity="info",
                    title=f"Resolution Verified for {channel}",
                    explanation=f"Creative resolution {width}x{height}px meets the channel specification of min {min_w}x{min_h}px.",
                    text_excerpt=f"{width}x{height}px ({format_name}, {mode})",
                    source_citation=f"Channel Standards ({channel})",
                    recommended_action="No change needed.",
                    status="passed_check"
                ))

            # Aspect ratio evaluation
            if target_ratio_str:
                num, den = [float(x) for x in target_ratio_str.split(":")]
                expected_ratio = num / den
                tolerance = spec.get("tolerance", 0.08)
                if abs(actual_ratio - expected_ratio) > tolerance:
                    findings.append(GovernanceFinding(
                        category="dimensions",
                        severity="warning",
                        title=f"Aspect Ratio Mismatch for {channel}",
                        explanation=f"Measured aspect ratio is {round(actual_ratio, 2)}:1, which deviates from standard {target_ratio_str} for {channel}.",
                        text_excerpt=f"Measured {round(actual_ratio, 2)}:1 vs Target {target_ratio_str}",
                        source_citation=f"Channel Standards ({channel})",
                        recommended_action=f"Crop creative to {target_ratio_str} ratio before public publishing.",
                        status="verified_issue"
                    ))
                else:
                    findings.append(GovernanceFinding(
                        category="dimensions",
                        severity="info",
                        title=f"Aspect Ratio Verified ({target_ratio_str})",
                        explanation=f"Creative aspect ratio {round(actual_ratio, 2)}:1 conforms to the expected {target_ratio_str} standard.",
                        text_excerpt=f"{round(actual_ratio, 2)}:1",
                        source_citation=f"Channel Standards ({channel})",
                        recommended_action="No change needed.",
                        status="passed_check"
                    ))

            # -------------------------------------------------------------
            # CHECK 2: Dominant-Colour Analysis against Approved Palette
            # -------------------------------------------------------------
            dominant_colors = self._extract_dominant_colors(file_path, k=5)
            approved_colors, color_rule = self._get_approved_brand_colors(db, org_id, brand_id)

            if not approved_colors:
                findings.append(GovernanceFinding(
                    category="colour",
                    severity="info",
                    title="Brand Color Palette: Reference Missing",
                    explanation="Unable to verify against the supplied guidelines; needs user review. No approved brand color palette rules found in approved knowledge.",
                    text_excerpt=f"Extracted dominant colors: {', '.join([c[0] for c in dominant_colors[:3]])}",
                    matched_rule_id=None,
                    source_citation="Knowledge Base (Colors Missing)",
                    recommended_action="Upload and approve brand color specifications in the Knowledge Library.",
                    status="unable_to_verify"
                ))
            else:
                # Check for brand palette matches
                matched_pairs = []
                for d_hex, d_pct, d_rgb in dominant_colors:
                    for a_name, a_hex, a_rgb in approved_colors:
                        dist = self._color_distance_rgb(d_rgb, a_rgb)
                        # Tolerance: Euclidean distance <= 75 in RGB space
                        if dist <= 75:
                            matched_pairs.append((a_name, a_hex, d_hex, d_pct))

                top_colors_str = ", ".join([f"{c[0]} ({c[1]}%)" for c in dominant_colors[:3]])
                if matched_pairs:
                    match_summary = ", ".join([f"{p[0]} ({p[1]} ~ {p[2]} at {p[3]}%)" for p in matched_pairs[:2]])
                    findings.append(GovernanceFinding(
                        category="colour",
                        severity="info",
                        title="Approved Brand Palette Alignment Verified",
                        explanation=f"Creative incorporates approved brand colors: {match_summary}.",
                        text_excerpt=f"Dominant colors: {top_colors_str}",
                        matched_rule_id=color_rule.id if color_rule else None,
                        source_citation=color_rule.source_citation if color_rule else "Approved Brand Guidelines",
                        recommended_action="No change needed.",
                        status="passed_check"
                    ))
                else:
                    approved_palette_str = ", ".join([f"{c[0]} ({c[1]})" for c in approved_colors])
                    findings.append(GovernanceFinding(
                        category="colour",
                        severity="warning",
                        title="Unapproved Dominant Palette Detected",
                        explanation=f"Extracted dominant colors ({top_colors_str}) do not match approved brand palette ({approved_palette_str}).",
                        text_excerpt=f"Dominant: {top_colors_str} | Approved: {approved_palette_str}",
                        matched_rule_id=color_rule.id if color_rule else None,
                        source_citation=color_rule.source_citation if color_rule else "Approved Brand Guidelines",
                        recommended_action="Adjust background or graphic accents to incorporate approved brand colors.",
                        status="verified_issue"
                    ))

            # -------------------------------------------------------------
            # CHECK 3: Localized WCAG 2.1 Text Region Contrast Measurement
            # -------------------------------------------------------------
            contrast_findings = self._evaluate_localized_text_contrast(
                file_path=file_path,
                ocr_result=ocr_result
            )
            findings.extend(contrast_findings)

            # -------------------------------------------------------------
            # CHECK 4: Logo Matching against Uploaded Brand Logo Asset
            # -------------------------------------------------------------
            logo_asset, logo_rule = self._find_approved_logo_asset(db, org_id, brand_id)
            from app.services.storage import storage_service
            if not logo_asset or not storage_service.check_exists(logo_asset.file_path):
                findings.append(GovernanceFinding(
                    category="logo",
                    severity="info",
                    title="Logo Verification: Reference Asset Missing",
                    explanation="Unable to verify against the supplied guidelines; needs user review. No approved official brand logo reference asset is uploaded in the Knowledge Library.",
                    text_excerpt="Missing official logo reference asset",
                    matched_rule_id=logo_rule.id if logo_rule else None,
                    source_citation=logo_rule.source_citation if logo_rule else "Approved Brand Guidelines",
                    recommended_action="Upload and approve the official brand logo in Knowledge Library to enable automated matching.",
                    status="unable_to_verify"
                ))
            else:
                logo_local_path = storage_service.get_file_path_for_processing(logo_asset.file_path)
                match_score, match_loc = self._match_logo_template(file_path, logo_local_path)
                if match_score >= 0.70:
                    findings.append(GovernanceFinding(
                        category="logo",
                        severity="info",
                        title="Official Brand Logo Placement Verified",
                        explanation=f"Official brand logo '{logo_asset.asset_name}' detected with {round(match_score * 100, 1)}% template correlation.",
                        text_excerpt=f"Detected at coordinates {match_loc} (Correlation: {round(match_score, 2)})",
                        matched_rule_id=logo_rule.id if logo_rule else None,
                        source_citation=logo_rule.source_citation if logo_rule else "Approved Brand Guidelines",
                        recommended_action="No change needed.",
                        status="passed_check"
                    ))
                elif match_score >= 0.45:
                    findings.append(GovernanceFinding(
                        category="logo",
                        severity="warning",
                        title="Ambiguous Logo Placement Detected",
                        explanation=f"Potential logo pattern detected (peak correlation {round(match_score, 2)}), but confidence is below the 0.70 verification threshold. Requires manual verification.",
                        text_excerpt=f"Peak correlation: {round(match_score, 2)} at {match_loc}",
                        matched_rule_id=logo_rule.id if logo_rule else None,
                        source_citation=logo_rule.source_citation if logo_rule else "Approved Brand Guidelines",
                        recommended_action="Verify that the official high-resolution logo is placed clearly and unwarped.",
                        status="unable_to_verify"
                    ))
                else:
                    findings.append(GovernanceFinding(
                        category="logo",
                        severity="warning",
                        title="Official Brand Logo Not Detected",
                        explanation=f"Official brand logo '{logo_asset.asset_name}' was not detected in this creative (peak correlation {round(match_score, 2)}).",
                        text_excerpt=f"Peak correlation: {round(match_score, 2)} (Required: >= 0.70)",
                        matched_rule_id=logo_rule.id if logo_rule else None,
                        source_citation=logo_rule.source_citation if logo_rule else "Approved Brand Guidelines",
                        recommended_action="Insert the approved official brand logo into the creative according to brand guidelines.",
                        status="verified_issue"
                    ))

            # -------------------------------------------------------------
            # CHECK 5: Accessibility & Alt-Text Metadata
            # -------------------------------------------------------------
            if not alt_text or len(alt_text.strip()) < 10:
                findings.append(GovernanceFinding(
                    category="accessibility",
                    severity="warning",
                    title="Accessibility Non-Compliance: Missing Alt-Text",
                    explanation="No descriptive alternative text provided for this creative. Brand guidelines mandate alt-text for screen-reader accessibility on public campaign assets.",
                    text_excerpt="Alt-Text: [EMPTY / INSUFFICIENT]",
                    source_citation="Brand Accessibility Guidelines",
                    recommended_action="Provide descriptive alt-text explaining the visual scene and text content.",
                    status="verified_issue"
                ))
            else:
                findings.append(GovernanceFinding(
                    category="accessibility",
                    severity="info",
                    title="Accessibility Alt-Text Provided",
                    explanation=f"Descriptive alternative text provided ({len(alt_text.strip())} chars) for screen-reader accessibility.",
                    text_excerpt=f"Alt-Text: \"{alt_text.strip()[:80]}{'...' if len(alt_text.strip()) > 80 else ''}\"",
                    source_citation="Brand Accessibility Guidelines",
                    recommended_action="No change needed.",
                    status="passed_check"
                ))

            # -------------------------------------------------------------
            # CHECK 6: Explicit Indication of Checks that Could Not Run
            # -------------------------------------------------------------
            findings.append(GovernanceFinding(
                category="layout",
                severity="info",
                title="Complex Layout & Object Classification: Not Automated",
                explanation="Automated object segmentation, visual clutter analysis, and proprietary font licensing are not automated for this channel. Manual reviewer sign-off required.",
                text_excerpt="Visual Layout Review: Manual Verification Required",
                source_citation="Governance Engine Policy",
                recommended_action="Approval Manager should visually inspect overall balance and font compliance during final review.",
                status="unable_to_verify"
            ))

        except Exception as e:
            findings.append(GovernanceFinding(
                category="asset",
                severity="warning",
                title="Visual Inspection Error",
                explanation=f"Encountered an exception while processing poster image: {e}",
                text_excerpt=str(e),
                source_citation="Image Governance Service",
                recommended_action="Ensure the image file is an uncorrupted PNG, JPG, or WEBP file.",
                status="unable_to_verify"
            ))

        if page_number is not None:
            for f in findings:
                f.page_number = page_number
                if not f.title.startswith(f"[Page {page_number}]"):
                    f.title = f"[Page {page_number}] {f.title}"
                if not f.explanation.startswith(f"[Page {page_number}]"):
                    f.explanation = f"[Page {page_number}] {f.explanation}"

        return findings

    # =========================================================================
    # HELPER METHODS
    # =========================================================================

    def _extract_dominant_colors(self, file_path: str, k: int = 5) -> List[Tuple[str, float, Tuple[int, int, int]]]:
        """
        Extracts dominant colors using k-means clustering on pixels.
        Returns list of (hex_code, percentage, (r, g, b)).
        """
        try:
            with Image.open(file_path) as pil_img:
                rgb_img = pil_img.convert("RGB")
                small_img = rgb_img.resize((150, 150))
                pixels = np.float32(np.array(small_img).reshape(-1, 3))

            criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 20, 0.2)
            _, labels, centers = cv2.kmeans(pixels, k, None, criteria, 10, cv2.KMEANS_RANDOM_CENTERS)
            counts = np.bincount(labels.flatten())
            total = len(labels)

            dominant = []
            for i in range(k):
                rgb = tuple(int(c) for c in centers[i])
                hex_col = "#{:02X}{:02X}{:02X}".format(*rgb)
                pct = round((counts[i] / total) * 100, 1)
                dominant.append((hex_col, pct, rgb))

            dominant.sort(key=lambda x: x[1], reverse=True)
            return dominant
        except Exception:
            return []

    def _get_approved_brand_colors(
        self, db: Session, org_id: str, brand_id: Optional[str] = None
    ) -> Tuple[List[Tuple[str, str, Tuple[int, int, int]]], Optional[KnowledgeRule]]:
        """
        Finds explicitly approved brand colors from approved rules and facts for the organization and brand.
        Returns list of (color_name, hex_code, (r, g, b)), plus supporting rule.
        Strictly multi-tenant: Returns an empty list if no approved colors exist (never falls back to hardcoded defaults).
        """
        rule_query = db.query(KnowledgeRule).filter(
            KnowledgeRule.organization_id == org_id,
            KnowledgeRule.status == "approved"
        )
        if brand_id:
            rule_query = rule_query.filter(
                (KnowledgeRule.brand_id == brand_id) | (KnowledgeRule.brand_id == None)
            )
        color_rules = rule_query.all()

        colors = []
        supporting_rule = None
        hex_regex = re.compile(r"#(?:[0-9a-fA-F]{3}){1,2}\b")

        for rule in color_rules:
            text_corpus = f"{rule.title} {rule.explanation} {rule.pattern} {rule.examples_good or ''}"
            matches = hex_regex.findall(text_corpus)
            if matches:
                supporting_rule = rule
                for h in set(matches):
                    norm_hex = h.upper()
                    if len(norm_hex) == 4:
                        norm_hex = f"#{norm_hex[1]*2}{norm_hex[2]*2}{norm_hex[3]*2}"
                    rgb = self._hex_to_rgb(norm_hex)
                    name = f"Approved Brand Color ({norm_hex})"
                    # Extract descriptive name if present in text
                    name_match = re.search(r"([A-Za-z\s]+)\s+" + re.escape(h), text_corpus)
                    if name_match and len(name_match.group(1).strip()) < 30:
                        clean_name = name_match.group(1).strip()
                        name = f"{clean_name} ({norm_hex})"
                    if not any(c[1] == norm_hex for c in colors):
                        colors.append((name, norm_hex, rgb))

        # Also search approved KnowledgeFact records for color specifications
        fact_query = db.query(KnowledgeFact).filter(
            KnowledgeFact.organization_id == org_id,
            KnowledgeFact.status == "approved"
        )
        if brand_id:
            fact_query = fact_query.filter(
                (KnowledgeFact.brand_id == brand_id) | (KnowledgeFact.brand_id == None)
            )
        for fact in fact_query.all():
            if any(k in f"{fact.fact_key} {fact.category}".lower() for k in ["color", "colour", "palette"]):
                matches = hex_regex.findall(f"{fact.fact_key} {fact.fact_value}")
                for h in set(matches):
                    norm_hex = h.upper()
                    if len(norm_hex) == 4:
                        norm_hex = f"#{norm_hex[1]*2}{norm_hex[2]*2}{norm_hex[3]*2}"
                    rgb = self._hex_to_rgb(norm_hex)
                    name = f"{fact.fact_key.title()} ({norm_hex})"
                    if not any(c[1] == norm_hex for c in colors):
                        colors.append((name, norm_hex, rgb))

        # Do NOT fallback to any hardcoded default colors. Return empty list if no approved colors exist.
        return colors, supporting_rule

    def _hex_to_rgb(self, hex_code: str) -> Tuple[int, int, int]:
        h = hex_code.lstrip("#")
        return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))

    def _color_distance_rgb(self, rgb1: Tuple[int, int, int], rgb2: Tuple[int, int, int]) -> float:
        return math.sqrt(sum((a - b) ** 2 for a, b in zip(rgb1, rgb2)))

    def estimate_localized_text_contrast(
        self,
        cv_img: np.ndarray,
        ocr_regions: List[OCRRegion]
    ) -> List[LocalizedContrastRegion]:
        """
        Estimates localized text and local background contrast for each OCR-detected text region.
        Uses sRGB linearization and WCAG 2.1 relative luminance standards:
        - Normalizes sRGB channels to [0, 1].
        - Applies piecewise gamma expansion (IEC 61966-2-1).
        - Computes L = 0.2126*R_lin + 0.7152*G_lin + 0.0722*B_lin.
        - Computes contrast ratio = (Llighter + 0.05) / (Ldarker + 0.05).
        - Evaluates against 4.5:1 (normal text) and 3.0:1 (large text >= 24px / 18pt).
        - Separates text strokes from background within the local polygon ROI and samples
          a localized background halo surrounding the text while excluding other text boxes.
        - Flags ambiguous or complex backgrounds as inconclusive rather than fabricating ratios.
        """
        if cv_img is None or not ocr_regions:
            return []

        img_h, img_w = cv_img.shape[:2]
        if img_h < 5 or img_w < 5:
            return []

        rgb_img = cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB)

        # Precompute polygon point arrays
        poly_pts_list: List[Optional[np.ndarray]] = []
        for reg in ocr_regions:
            try:
                pts = np.int32(reg.bbox)
                pts[:, 0] = np.clip(pts[:, 0], 0, img_w - 1)
                pts[:, 1] = np.clip(pts[:, 1], 0, img_h - 1)
                poly_pts_list.append(pts)
            except Exception:
                poly_pts_list.append(None)

        results: List[LocalizedContrastRegion] = []

        for idx, reg in enumerate(ocr_regions):
            pts = poly_pts_list[idx]
            if pts is None or len(pts) < 3:
                continue

            text_cleaned = reg.text.strip()
            if not text_cleaned:
                continue

            # Estimate font size and rotation using minAreaRect
            try:
                rect = cv2.minAreaRect(pts)
                dim1, dim2 = rect[1]
                if dim1 > 0 and dim2 > 0:
                    text_height = min(dim1, dim2)
                else:
                    text_height = max(1.0, float(np.max(pts[:, 1]) - np.min(pts[:, 1])))
            except Exception:
                text_height = max(1.0, float(np.max(pts[:, 1]) - np.min(pts[:, 1])))

            # WCAG 2.x AA threshold determination:
            # Large text: >= 18pt (typically 24px at 96 DPI) or 14pt bold
            is_large_text = bool(text_height >= 24.0)
            threshold = 3.0 if is_large_text else 4.5

            # 1. Create text polygon mask
            mask_text = np.zeros((img_h, img_w), dtype=np.uint8)
            cv2.fillPoly(mask_text, [pts], 255)

            # 2. Construct local background halo (annulus)
            d = max(5, min(25, int(text_height * 0.35)))
            kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * d + 1, 2 * d + 1))
            mask_dilated = cv2.dilate(mask_text, kernel)
            mask_bg_candidate = cv2.subtract(mask_dilated, mask_text)

            # Exclude other text regions from candidate background
            mask_other = np.zeros((img_h, img_w), dtype=np.uint8)
            for jdx, other_pts in enumerate(poly_pts_list):
                if jdx != idx and other_pts is not None:
                    cv2.fillPoly(mask_other, [other_pts], 255)

            other_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
            mask_other_dilated = cv2.dilate(mask_other, other_kernel)
            mask_bg = cv2.bitwise_and(mask_bg_candidate, cv2.bitwise_not(mask_other_dilated))

            bg_pixels = rgb_img[mask_bg == 255]
            if len(bg_pixels) < 15:
                # Fall back to candidate without other dilation if tightly clustered
                mask_bg = cv2.bitwise_and(mask_bg_candidate, cv2.bitwise_not(mask_other))
                bg_pixels = rgb_img[mask_bg == 255]

            text_pixels = rgb_img[mask_text == 255]

            # Guard against degenerated / boundary regions
            if len(bg_pixels) < 10 or len(text_pixels) < 10:
                results.append(LocalizedContrastRegion(
                    text=text_cleaned,
                    bbox=reg.bbox,
                    contrast_ratio=1.0,
                    fg_rgb=(128, 128, 128),
                    bg_rgb=(128, 128, 128),
                    fg_luminance=0.2,
                    bg_luminance=0.2,
                    threshold=threshold,
                    is_large_text=is_large_text,
                    is_reliable=False,
                    status="inconclusive",
                    method="Insufficient local pixels for statistical contrast estimation",
                    notes="Text region located on extreme boundary or obstructed by adjacent elements."
                ))
                continue

            # 3. Background color properties & variance
            bg_median_rgb = tuple(int(x) for x in np.median(bg_pixels, axis=0))
            bg_lum = calculate_relative_luminance(bg_median_rgb)

            bg_luminances = np.array([calculate_relative_luminance(p) for p in bg_pixels])
            std_bg = float(np.std(bg_luminances))
            min_bg_lum = float(np.percentile(bg_luminances, 10))
            max_bg_lum = float(np.percentile(bg_luminances, 90))

            # 4. Foreground / internal background separation within text ROI (Bimodal K-Means)
            criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 20, 0.2)
            _, labels, centers = cv2.kmeans(
                np.float32(text_pixels), 2, None, criteria, 10, cv2.KMEANS_RANDOM_CENTERS
            )
            c0, c1 = centers[0], centers[1]
            n0 = int(np.sum(labels == 0))
            n1 = int(np.sum(labels == 1))

            dist0 = float(np.linalg.norm(c0 - np.array(bg_median_rgb)))
            dist1 = float(np.linalg.norm(c1 - np.array(bg_median_rgb)))

            # The cluster farther from the background halo represents the foreground strokes
            if dist0 < dist1:
                fg_center, bg_center = c1, c0
                fg_count, bg_count = n1, n0
                fg_cluster_idx = 1
            else:
                fg_center, bg_center = c0, c1
                fg_count, bg_count = n0, n1
                fg_cluster_idx = 0

            fg_rgb = tuple(int(round(np.clip(x, 0, 255))) for x in fg_center)
            fg_lum = calculate_relative_luminance(fg_rgb)
            cr = calculate_contrast_ratio(fg_lum, bg_lum)

            # Measure stroke thickness using distance transform on foreground stroke mask
            stroke_submask = (labels.flatten() == fg_cluster_idx)
            fg_img_mask = np.zeros((img_h, img_w), dtype=np.uint8)
            fg_pts_coords = np.where(mask_text == 255)
            if len(fg_pts_coords[0]) == len(stroke_submask):
                fg_img_mask[fg_pts_coords[0][stroke_submask], fg_pts_coords[1][stroke_submask]] = 255
            dist_map = cv2.distanceTransform(fg_img_mask, cv2.DIST_L2, 3)
            stroke_width = round(2.0 * float(np.max(dist_map)), 1) if np.any(fg_img_mask) else 1.0

            # Typography Classification & Threshold Determination:
            # Policy (Milestone 5A.2):
            # 1. When trustworthy source typography metadata or documented mapping establishes qualifying large text
            #    (>= 18pt or >= 14pt bold), apply the 3.0:1 large-text threshold.
            # 2. When text is confirmed normal text via source metadata, apply the 4.5:1 threshold.
            # 3. When classification is based only on raster image pixel dimensions or estimated stroke width,
            #    label it as a heuristic / unverified estimate. Pixel height and stroke width do not prove WCAG large text.
            #    The conservative 4.5:1 threshold applies for automatic passing decisions.
            is_trustworthy_large = False
            is_trustworthy_normal = False
            meta = getattr(reg, "typography_metadata", None) or {}

            if getattr(reg, "is_known_large_text", None) is True or meta.get("is_large_text") is True:
                is_trustworthy_large = True
            elif meta.get("font_size_pt", 0) >= 18:
                is_trustworthy_large = True
            elif meta.get("font_size_pt", 0) >= 14 and meta.get("is_bold") is True:
                is_trustworthy_large = True
            elif getattr(reg, "is_known_normal_text", None) is True or meta.get("is_normal_text") is True:
                is_trustworthy_normal = True
            elif 0 < meta.get("font_size_pt", 0) < 14:
                is_trustworthy_normal = True

            if is_trustworthy_large:
                font_classification = "verified_large_text"
                threshold = 3.0
                is_large_text = True
                classification_desc = (
                    f"Verified large typography (source metadata confirmed, ~{int(round(text_height))}px raster height)"
                )
            elif is_trustworthy_normal:
                font_classification = "verified_normal_text"
                threshold = 4.5
                is_large_text = False
                classification_desc = (
                    f"Verified normal typography (source metadata confirmed, ~{int(round(text_height))}px raster height)"
                )
            else:
                # Raster-only estimation: heuristic evidence, not certified WCAG typography
                font_classification = "unverified_raster_estimate"
                is_large_text = False
                threshold = 4.5  # Conservative baseline applied for automatic passing decisions
                classification_desc = (
                    f"Unverified raster estimate (~{int(round(text_height))}px bbox height, "
                    f"stroke {stroke_width}px; heuristic only, not verified typography)"
                )

            # 5. Reliability, ambiguity, and failure checks
            cluster_dist = float(np.linalg.norm(c0 - c1))
            cluster_lum_diff = abs(calculate_relative_luminance(c0) - calculate_relative_luminance(c1))
            total_pixels = len(text_pixels)
            stroke_ratio = fg_count / total_pixels

            is_reliable = True
            status = "pass"
            method_desc = "Localized ROI bimodal clustering with surrounding halo sampling"
            notes = f"{classification_desc}. Stroke ratio: {stroke_ratio:.1%}."

            if cluster_dist < 18.0 and cluster_lum_diff < 0.04:
                is_reliable = False
                status = "inconclusive"
                notes = "Unable to reliably separate text strokes from background inside bounding polygon (insufficient internal color difference)."
            elif stroke_ratio < 0.04 or stroke_ratio > 0.92:
                is_reliable = False
                status = "inconclusive"
                notes = f"Foreground stroke pixel ratio ({stroke_ratio:.1%}) outside expected letterform range (4%-92%)."
            elif std_bg > 0.26:
                # High-variance complex / gradient background
                cr_min = min(calculate_contrast_ratio(fg_lum, min_bg_lum), calculate_contrast_ratio(fg_lum, max_bg_lum))
                cr_max = max(calculate_contrast_ratio(fg_lum, min_bg_lum), calculate_contrast_ratio(fg_lum, max_bg_lum))
                if cr_min < threshold <= cr_max:
                    is_reliable = False
                    status = "inconclusive"
                    notes = f"High background variance (luminance std: {std_bg:.2f}). Contrast varies between {cr_min:.2f}:1 and {cr_max:.2f}:1 across gradient."
                else:
                    notes += f" Complex background evaluated (std: {std_bg:.2f}, range {cr_min:.2f}:1 - {cr_max:.2f}:1)."
                    if cr >= threshold:
                        status = "pass"
                    elif is_trustworthy_normal:
                        status = "fail"
                    elif cr >= 3.0:
                        status = "marginal"
                    else:
                        status = "fail"
            else:
                if cr >= threshold:
                    status = "pass"
                elif is_trustworthy_normal:
                    # Verified normal text failing 4.5:1 is a direct failure
                    status = "fail"
                elif cr >= 3.0:
                    # Satisfies 3.0:1 but threshold is 4.5:1 because typography is unverified
                    status = "marginal"
                else:
                    status = "fail"

            results.append(LocalizedContrastRegion(
                text=text_cleaned,
                bbox=reg.bbox,
                contrast_ratio=round(float(cr), 2),
                fg_rgb=fg_rgb,
                bg_rgb=bg_median_rgb,
                fg_luminance=round(float(fg_lum), 4),
                bg_luminance=round(float(bg_lum), 4),
                threshold=threshold,
                is_large_text=is_large_text,
                is_reliable=is_reliable,
                status=status,
                method=method_desc,
                notes=notes,
                font_classification=font_classification,
                stroke_width=stroke_width
            ))

        return results

    def _evaluate_localized_text_contrast(
        self,
        file_path: str,
        ocr_result: Optional[OCRResult] = None
    ) -> List[GovernanceFinding]:
        """
        Evaluates localized text contrast for each OCR-detected text region and emits
        defensible WCAG findings grounded in localized pixel evidence.
        """
        findings: List[GovernanceFinding] = []
        try:
            cv_img = cv2.imread(file_path)
            if cv_img is None:
                findings.append(GovernanceFinding(
                    category="contrast",
                    severity="warning",
                    title="Text Contrast: Image Unreadable",
                    explanation=f"Unable to read image at '{file_path}' for contrast assessment.",
                    text_excerpt=file_path,
                    source_citation="WCAG 2.1 Contrast Standards",
                    recommended_action="Ensure the image file is valid and accessible on disk.",
                    status="unable_to_verify"
                ))
                return findings

            # If ocr_result not provided, run extraction
            if ocr_result is None:
                from app.services.ocr_service import ocr_service
                ocr_result = ocr_service.extract_text_from_image(file_path)

            if ocr_result.status == "no_text" or not ocr_result.regions:
                findings.append(GovernanceFinding(
                    category="contrast",
                    severity="info",
                    title="Text Contrast: No Embedded Text Detected",
                    explanation="No text regions were detected in this poster by local OCR. Visual text contrast check is not applicable for textless visuals.",
                    text_excerpt="No OCR Text Detected",
                    source_citation="WCAG 2.1 Section 1.4.3",
                    recommended_action="No change needed.",
                    status="passed_check"
                ))
                return findings

            # Estimate contrast per region
            region_results = self.estimate_localized_text_contrast(cv_img, ocr_result.regions)
            if not region_results:
                findings.append(GovernanceFinding(
                    category="contrast",
                    severity="info",
                    title="Text Contrast: No Eligible Text Regions",
                    explanation="Detected text boxes were too small or invalid for localized contrast measurement.",
                    text_excerpt="No measurable text boxes",
                    source_citation="WCAG 2.1 Section 1.4.3",
                    recommended_action="Ensure text is rendered with sufficient resolution.",
                    status="unable_to_verify"
                ))
                return findings

            failing_regions = [r for r in region_results if r.status == "fail"]
            marginal_regions = [r for r in region_results if r.status == "marginal"]
            inconclusive_regions = [r for r in region_results if r.status == "inconclusive"]
            passing_regions = [r for r in region_results if r.status == "pass"]

            # Add findings for failing regions
            for reg in failing_regions:
                bbox_str = str([[round(p[0], 1), round(p[1], 1)] for p in reg.bbox])
                is_crit = reg.contrast_ratio < 3.0
                class_label = reg.font_classification.replace("_", " ")
                findings.append(GovernanceFinding(
                    category="contrast",
                    severity="critical" if is_crit else "warning",
                    title=f"Insufficient Text Contrast ({reg.contrast_ratio:.2f}:1): '{reg.text[:30]}'",
                    explanation=(
                        f"Estimated contrast ratio is {reg.contrast_ratio:.2f}:1, failing WCAG 2.1 minimum requirement "
                        f"({reg.threshold:.1f}:1) for {class_label}. "
                        f"Estimated FG: {reg.fg_rgb} (L={reg.fg_luminance:.3f}), BG: {reg.bg_rgb} (L={reg.bg_luminance:.3f}). "
                        f"Method: {reg.notes}"
                    ),
                    text_excerpt=f"'{reg.text}' [bbox: {bbox_str}] — Contrast: {reg.contrast_ratio:.2f}:1 (Required: {reg.threshold:.1f}:1)",
                    source_citation="WCAG 2.1 Section 1.4.3 (Contrast Minimum)",
                    recommended_action="Darken background imagery or lighten foreground text to achieve at least 4.5:1 contrast (or 3:1 for verified large display headlines).",
                    status="verified_issue"
                ))

            # Add findings for marginal regions (unknown raster typography in 3:1 to 4.5:1 range)
            for reg in marginal_regions:
                bbox_str = str([[round(p[0], 1), round(p[1], 1)] for p in reg.bbox])
                class_label = reg.font_classification.replace("_", " ")
                findings.append(GovernanceFinding(
                    category="contrast",
                    severity="warning",
                    title=f"Text Contrast: Unverified Typography Scale Requires Manual Review ({reg.contrast_ratio:.2f}:1): '{reg.text[:30]}'",
                    explanation=(
                        f"Estimated contrast ratio is {reg.contrast_ratio:.2f}:1. This meets the 3.0:1 threshold for large-scale text, "
                        f"but falls below the conservative 4.5:1 threshold for normal text. "
                        f"Because font size and boldness are heuristic raster estimates rather than certified source typography ({reg.notes}), "
                        f"an automatic pass cannot be granted. Reviewer visual confirmation of rendered scale is required prior to approval."
                    ),
                    text_excerpt=f"'{reg.text}' [bbox: {bbox_str}] — Contrast: {reg.contrast_ratio:.2f}:1 (Conservative Target: 4.5:1, Large Standard: 3.0:1)",
                    source_citation="WCAG 2.1 Section 1.4.3",
                    recommended_action="Approval reviewer must inspect the published creative scale to ensure text renders as qualifying large/bold copy, or adjust colors to meet 4.5:1.",
                    status="unable_to_verify"
                ))

            # Add findings for inconclusive regions (unreliable separation, extreme boundary, low OCR confidence)
            for reg in inconclusive_regions:
                bbox_str = str([[round(p[0], 1), round(p[1], 1)] for p in reg.bbox])
                findings.append(GovernanceFinding(
                    category="contrast",
                    severity="warning",
                    title=f"Text Contrast: Visual Review Recommended — '{reg.text[:30]}'",
                    explanation=(
                        f"Automated contrast calculation is inconclusive: {reg.notes}. "
                        f"Nominal ratio: ~{reg.contrast_ratio:.2f}:1 (FG: {reg.fg_rgb}, BG: {reg.bg_rgb}). "
                        f"Manual visual inspection recommended to ensure readability."
                    ),
                    text_excerpt=f"'{reg.text}' [bbox: {bbox_str}] — Inconclusive: {reg.notes}",
                    source_citation="WCAG 2.1 Contrast Standards",
                    recommended_action="Visually verify that advertisement text is clearly legible against background imagery before approving.",
                    status="unable_to_verify"
                ))

            # If all regions passed, or to document passing regions:
            if passing_regions and not failing_regions and not marginal_regions and not inconclusive_regions:
                min_pass = min(passing_regions, key=lambda r: r.contrast_ratio)
                bbox_str = str([[round(p[0], 1), round(p[1], 1)] for p in min_pass.bbox])
                all_verified_large = all(r.font_classification == "verified_large_text" for r in passing_regions)
                if all_verified_large:
                    title_text = f"WCAG AA Contrast Verified (Large Typography Criterion) across {len(passing_regions)} Region{'s' if len(passing_regions) > 1 else ''}"
                    exp_text = (
                        f"All {len(passing_regions)} detected text regions satisfy the 3.0:1 WCAG AA large-text contrast standard based on verified source typography. "
                        f"Lowest measured contrast ratio is {min_pass.contrast_ratio:.2f}:1 for '{min_pass.text[:30]}' (FG: {min_pass.fg_rgb}, BG: {min_pass.bg_rgb})."
                    )
                else:
                    title_text = f"WCAG AA Contrast Verified (Conservative 4.5:1 Baseline) across {len(passing_regions)} Text Region{'s' if len(passing_regions) > 1 else ''}"
                    exp_text = (
                        f"All {len(passing_regions)} detected text regions meet the conservative 4.5:1 WCAG AA contrast threshold. "
                        f"Lowest measured contrast ratio is {min_pass.contrast_ratio:.2f}:1 (threshold: {min_pass.threshold:.1f}:1) for '{min_pass.text[:30]}'. "
                        f"Compliance is grounded in reliable localized measurements and does not rely on unverified large-scale or bold font assumptions."
                    )
                findings.append(GovernanceFinding(
                    category="contrast",
                    severity="info",
                    title=title_text,
                    explanation=exp_text,
                    text_excerpt=f"'{min_pass.text}' [bbox: {bbox_str}] — Contrast: {min_pass.contrast_ratio:.2f}:1 (Min {min_pass.threshold:.1f}:1)",
                    source_citation="WCAG 2.1 Contrast Standards",
                    recommended_action="No change needed.",
                    status="passed_check"
                ))
            elif passing_regions:
                min_pass = min(passing_regions, key=lambda r: r.contrast_ratio)
                findings.append(GovernanceFinding(
                    category="contrast",
                    severity="info",
                    title=f"WCAG AA Contrast Verified on {len(passing_regions)} Region{'s' if len(passing_regions) > 1 else ''}",
                    explanation=f"{len(passing_regions)} text regions satisfied WCAG AA standards (min ratio: {min_pass.contrast_ratio:.2f}:1 on '{min_pass.text[:30]}').",
                    text_excerpt=f"Passed regions: {len(passing_regions)} / {len(region_results)} total",
                    source_citation="WCAG 2.1 Contrast Standards",
                    recommended_action="No change needed for compliant regions.",
                    status="passed_check"
                ))

        except Exception as e:
            findings.append(GovernanceFinding(
                category="contrast",
                severity="info",
                title="Text Contrast: Evaluation Inconclusive",
                explanation=f"Error encountered while evaluating localized contrast: {str(e)}",
                text_excerpt=str(e),
                source_citation="Image Governance Service",
                recommended_action="Visually verify image legibility.",
                status="unable_to_verify"
            ))

        return findings

    def _measure_text_contrast(self, file_path: str) -> Tuple[float, bool]:
        """
        Backwards-compatible text contrast helper.
        Uses localized OCR text contrast if text is detected, or falls back to bimodal Otsu.
        Returns (contrast_ratio, is_reliable).
        """
        try:
            cv_img = cv2.imread(file_path)
            if cv_img is None:
                return 1.0, False

            from app.services.ocr_service import ocr_service
            ocr_result = ocr_service.extract_text_from_image(file_path)
            if ocr_result.regions:
                results = self.estimate_localized_text_contrast(cv_img, ocr_result.regions)
                if results:
                    min_res = min(results, key=lambda r: r.contrast_ratio)
                    return float(min_res.contrast_ratio), bool(min_res.is_reliable)

            gray = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)
            _, mask = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

            light_pixels = cv_img[mask == 255]
            dark_pixels = cv_img[mask == 0]

            if len(light_pixels) < 100 or len(dark_pixels) < 100:
                return 1.0, False

            mean_light = np.mean(light_pixels, axis=0)
            mean_dark = np.mean(dark_pixels, axis=0)

            l1 = self._relative_luminance(mean_light)
            l2 = self._relative_luminance(mean_dark)

            ratio = calculate_contrast_ratio(l1, l2)
            return float(ratio), True
        except Exception:
            return 1.0, False

    def _relative_luminance(self, bgr_color: np.ndarray) -> float:
        """
        Computes WCAG 2.1 relative luminance for a BGR color array using sRGB linearization.
        """
        rgb = (int(bgr_color[2]), int(bgr_color[1]), int(bgr_color[0]))
        return calculate_relative_luminance(rgb)

    def _find_approved_logo_asset(
        self, db: Session, org_id: str, brand_id: Optional[str] = None
    ) -> Tuple[Optional[BrandAsset], Optional[KnowledgeRule]]:
        """
        Finds an official APPROVED logo BrandAsset and any corresponding rule for the organization and brand.
        Only records with status='approved' are used.
        """
        asset_query = db.query(BrandAsset).filter(
            BrandAsset.organization_id == org_id,
            BrandAsset.status == "approved",
            BrandAsset.asset_type == "logo"
        )
        if brand_id:
            asset_query = asset_query.filter(
                (BrandAsset.brand_id == brand_id) | (BrandAsset.brand_id == None)
            )
        logo_asset = asset_query.first()

        # If no explicit asset_type == 'logo', search by approved asset name
        if not logo_asset:
            fallback_query = db.query(BrandAsset).filter(
                BrandAsset.organization_id == org_id,
                BrandAsset.status == "approved",
                BrandAsset.asset_name.ilike("%logo%")
            )
            if brand_id:
                fallback_query = fallback_query.filter(
                    (BrandAsset.brand_id == brand_id) | (BrandAsset.brand_id == None)
                )
            logo_asset = fallback_query.first()

        # Find dynamic approved rule for logo / brand asset usage
        rule_query = db.query(KnowledgeRule).filter(
            KnowledgeRule.organization_id == org_id,
            KnowledgeRule.status == "approved",
            (
                KnowledgeRule.rule_type.in_(["image_standard", "asset_policy"]) |
                KnowledgeRule.title.ilike("%logo%") |
                KnowledgeRule.pattern.ilike("%logo%")
            )
        )
        if brand_id:
            rule_query = rule_query.filter(
                (KnowledgeRule.brand_id == brand_id) | (KnowledgeRule.brand_id == None)
            )
        logo_rule = rule_query.first()

        return logo_asset, logo_rule

    def _match_logo_template(self, poster_path: str, logo_path: str) -> Tuple[float, Tuple[int, int]]:
        """
        Performs multi-scale OpenCV template matching to locate official logo in poster.
        Returns (max_correlation, (x, y)).
        """
        try:
            poster = cv2.imread(poster_path)
            logo = cv2.imread(logo_path)

            if poster is None or logo is None:
                return 0.0, (0, 0)

            gray_poster = cv2.cvtColor(poster, cv2.COLOR_BGR2GRAY)
            gray_logo = cv2.cvtColor(logo, cv2.COLOR_BGR2GRAY)

            p_h, p_w = gray_poster.shape[:2]
            l_h, l_w = gray_logo.shape[:2]

            best_val = 0.0
            best_loc = (0, 0)

            # Test scales from 0.2x to 1.0x
            scales = [0.2, 0.35, 0.5, 0.75, 1.0]
            for scale in scales:
                new_w = int(l_w * scale)
                new_h = int(l_h * scale)
                if new_w >= p_w or new_h >= p_h or new_w < 15 or new_h < 15:
                    continue

                scaled_template = cv2.resize(gray_logo, (new_w, new_h), interpolation=cv2.INTER_AREA)
                res = cv2.matchTemplate(gray_poster, scaled_template, cv2.TM_CCOEFF_NORMED)
                _, max_val, _, max_loc = cv2.minMaxLoc(res)

                if max_val > best_val:
                    best_val = max_val
                    best_loc = max_loc

            return float(best_val), best_loc
        except Exception:
            return 0.0, (0, 0)

image_governance = ImageGovernanceService()
