import os
from typing import Dict, Any, List, Optional
from PIL import Image

CHANNEL_DIMENSION_STANDARDS = {
    "Instagram Post": {"aspect_ratio": "1:1", "min_width": 1080, "min_height": 1080},
    "Instagram Story": {"aspect_ratio": "9:16", "min_width": 1080, "min_height": 1920},
    "Social Media": {"aspect_ratio": "1:1", "min_width": 800, "min_height": 800},
    "Website Banner": {"aspect_ratio": "16:9", "min_width": 1200, "min_height": 675},
    "Print Ad": {"color_mode": "CMYK", "min_dpi": 300},
}

class ImageGovernanceService:
    """
    Round 3 Improvement 3: Static-image governance and compliance checker.
    Validates brand asset specifications, color modes, clearances, and accessibility metadata.
    """

    def inspect_image(
        self,
        file_path: str,
        channel: str = "Social Media",
        alt_text: Optional[str] = None,
        is_logo: bool = False
    ) -> Dict[str, Any]:
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
                if not alt_text or len(alt_text.strip()) < 5:
                    findings.append("Accessibility Violation: Missing or inadequate alternative text (Alt-Text).")
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

                # 3. Minimum Resolution & Clearance
                min_w = expected_spec.get("min_width", 600)
                min_h = expected_spec.get("min_height", 600)
                if width < min_w or height < min_h:
                    findings.append(f"Resolution Deficiency: Image is {width}x{height}px, below the recommended {min_w}x{min_h}px for {channel}.")
                    recommendations.append(f"Upload high-resolution asset meeting at least {min_w}x{min_h}px.")

                # 4. Logo Clearspace Guideline
                if is_logo:
                    # Minimum clearance padding rule
                    findings.append("Brand Guideline Notice: Ensure a minimum 24px clearspace perimeter around the logo.")
                    recommendations.append("Do not place headlines or high-contrast graphics inside the logo isolation zone.")

                passed = len([f for f in findings if "Violation" in f or "Deficiency" in f]) == 0

                return {
                    "passed": passed,
                    "dimensions": f"{width}x{height}px",
                    "aspect_ratio": f"{round(width/max(height, 1), 2)}:1",
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

image_governance = ImageGovernanceService()
