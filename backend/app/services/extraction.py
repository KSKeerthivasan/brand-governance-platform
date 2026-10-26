import os
import re
from typing import List, Dict, Any, Tuple
from pypdf import PdfReader
from PIL import Image

def extract_pdf_text_and_candidates(file_path: str, filename: str) -> Tuple[str, List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Extracts text from a PDF document and parses candidate rules and product facts.
    ALL extracted rules and facts start in status='pending_review'.
    Preserves exact page references and citations.
    """
    if not os.path.exists(file_path):
        return "", [], []

    full_text = []
    page_texts = []
    try:
        reader = PdfReader(file_path)
        for page_num, page in enumerate(reader.pages, start=1):
            text = page.extract_text() or ""
            page_texts.append((page_num, text))
            full_text.append(f"--- Page {page_num} ---\n{text}")
    except Exception as e:
        return f"Error reading PDF: {e}", [], []

    combined_text = "\n\n".join(full_text)
    candidate_rules: List[Dict[str, Any]] = []
    candidate_facts: List[Dict[str, Any]] = []

    # Parse candidate brand rules from extracted pages
    for page_num, text in page_texts:
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        for line in lines:
            # Look for prohibited / disallowed patterns
            prohibited_match = re.search(
                r"(?:do not use|prohibited|never use|avoid|disallowed|banned)\s*[:\-]?\s*['\"]?([^'\"\.\,\;]+)['\"]?",
                line,
                re.IGNORECASE
            )
            if prohibited_match:
                word = prohibited_match.group(1).strip()
                if len(word) > 2 and len(word) < 60:
                    candidate_rules.append({
                        "rule_type": "prohibited_word",
                        "title": f"Prohibited: '{word}'",
                        "pattern": word,
                        "explanation": f"Source document prohibits the usage of '{word}'. Found on page {page_num}.",
                        "severity": "critical",
                        "source_citation": f"{filename}, Page {page_num}",
                        "status": "pending_review",
                    })

            # Look for required / mandatory terminology patterns
            required_match = re.search(
                r"(?:must include|required wording|mandatory phrase|always include)\s*[:\-]?\s*['\"]?([^'\"\.\,\;]+)['\"]?",
                line,
                re.IGNORECASE
            )
            if required_match:
                phrase = required_match.group(1).strip()
                if len(phrase) > 2 and len(phrase) < 80:
                    candidate_rules.append({
                        "rule_type": "required_term",
                        "title": f"Mandatory Term: '{phrase}'",
                        "pattern": phrase,
                        "explanation": f"Brand guidelines mandate inclusion of '{phrase}'. Found on page {page_num}.",
                        "severity": "warning",
                        "source_citation": f"{filename}, Page {page_num}",
                        "status": "pending_review",
                    })

            # Look for product facts / nutrition / claims
            # e.g., "Calories: 15 kcal", "Sugar: 0g", "Organic Certified: USDA Organic"
            fact_match = re.search(
                r"^([A-Za-z\s]{3,30})\s*[:\-=]\s*([A-Za-z0-9\s\,\.\%\+\-]+)$",
                line
            )
            if fact_match:
                key = fact_match.group(1).strip()
                val = fact_match.group(2).strip()
                if len(val) > 0 and len(val) < 100:
                    # Categorize fact
                    lower_key = key.lower()
                    if any(term in lower_key for term in ["sugar", "calorie", "caffeine", "sodium", "fat", "protein", "vitamin"]):
                        cat = "nutrition"
                    elif any(term in lower_key for term in ["organic", "gmo", "certified", "kosher", "vegan", "fair trade"]):
                        cat = "certification"
                    elif any(term in lower_key for term in ["ingredient", "extract", "flavor"]):
                        cat = "ingredient"
                    elif any(term in lower_key for term in ["claim", "health", "boost", "energy"]):
                        cat = "claim"
                    else:
                        cat = "specification"

                    candidate_facts.append({
                        "product_name": "Freshsip",
                        "category": cat,
                        "fact_key": key,
                        "fact_value": val,
                        "supporting_evidence": line,
                        "source_citation": f"{filename}, Page {page_num}",
                        "status": "pending_review",
                    })

    summary = f"Parsed {len(page_texts)} pages. Extracted {len(candidate_rules)} candidate rules and {len(candidate_facts)} candidate facts."
    return summary, candidate_rules, candidate_facts


def extract_image_metadata(file_path: str, filename: str) -> Dict[str, Any]:
    """
    Extracts image dimensions, color mode, aspect ratio, and checks compliance.
    """
    if not os.path.exists(file_path):
        return {}

    try:
        with Image.open(file_path) as img:
            width, height = img.size
            mode = img.mode
            format_name = img.format or "UNKNOWN"
            aspect_ratio = f"{width}:{height}" if height > 0 else "N/A"
            
            # Simple aspect ratio normalization
            gcd_val = _gcd(width, height) if height > 0 else 1
            if gcd_val > 10:
                normalized_ratio = f"{width // gcd_val}:{height // gcd_val}"
            else:
                ratio_float = round(width / max(height, 1), 2)
                normalized_ratio = f"{ratio_float}:1"

            return {
                "asset_name": filename,
                "asset_type": "logo" if "logo" in filename.lower() else ("product_image" if "product" in filename.lower() else "campaign_creative"),
                "file_path": file_path,
                "mime_type": f"image/{format_name.lower()}",
                "width": width,
                "height": height,
                "aspect_ratio": normalized_ratio,
                "color_mode": mode,
                "min_clearance_px": 24 if "logo" in filename.lower() else 16,
                "alt_text_required": True,
                "status": "pending_review",
            }
    except Exception as e:
        return {
            "asset_name": filename,
            "asset_type": "campaign_creative",
            "file_path": file_path,
            "mime_type": "image/unknown",
            "status": "pending_review",
            "error": str(e)
        }

def _gcd(a: int, b: int) -> int:
    while b:
        a, b = b, a % b
    return a
