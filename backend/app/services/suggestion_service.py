import re
import difflib
from datetime import datetime
from typing import List, Optional, Tuple, Dict, Any
from sqlalchemy.orm import Session

from app.models.content import ContentItem, ContentVersion, GovernanceRun, GovernanceFinding, CorrectionSuggestion
from app.models.knowledge import KnowledgeRule, KnowledgeFact
from app.models.organization import User

# Canonical product metadata mapping
CANONICAL_PRODUCT_METADATA: Dict[str, Dict[str, Any]] = {
    "FS-PROD-001": {
        "name": "Valencia Orange Cold-Pressed Juice",
        "mrp": 120,
        "processing": "Cold-Pressed, High-Pressure Processed (HPP)",
        "sugar_type": "fruit",
        "pack_size": "250 mL",
        "approved_claim_code": "FS-CLAIM-001",
        "approved_claim": "Made from 100% cold-pressed Valencia orange juice with no added sugar and no added preservatives (contains 8.4 g naturally occurring fruit sugars per 100 mL)."
    },
    "FS-PROD-002": {
        "name": "Pink Guava Pomegranate Nectar",
        "mrp": 110,
        "processing": "Flash Pasteurized",
        "sugar_type": "fruit",
        "pack_size": "250 mL",
        "approved_claim_code": "FS-CLAIM-002",
        "approved_claim": "Crafted from 60% pink guava puree and 40% pomegranate juice, flash pasteurized with no added sugar or preservatives (54 kcal per 100 mL)."
    },
    "FS-PROD-003": {
        "name": "Garden Tomato Celery Press",
        "mrp": 95,
        "processing": "Cold-Pressed, High-Pressure Processed (HPP)",
        "sugar_type": "vegetable",
        "pack_size": "250 mL",
        "has_celery_allergen": True,
        "approved_claim_code": "FS-CLAIM-003",
        "approved_claim": "Savory cold-pressed vegetable blend made with 82% tomato juice and 14% celery juice, containing 22 kcal per 100 mL. Contains Celery."
    },
    "FS-PROD-004": {
        "name": "Spiced Carrot Beetroot Press",
        "mrp": 105,
        "processing": "Flash Pasteurized",
        "sugar_type": "vegetable",
        "pack_size": "250 mL",
        "approved_claim_code": None,
        "approved_claim": None
    },
    "FS-PROD-005": {
        "name": "Green Orchard Cucumber Spinach Blend",
        "mrp": 130,
        "processing": "Cold-Pressed, High-Pressure Processed (HPP)",
        "sugar_type": "fruit and vegetable",
        "pack_size": "250 mL",
        "approved_claim_code": "FS-CLAIM-006",
        "approved_claim": "A cold-pressed fruit-and-vegetable blend of 55% green apple juice, 28% cucumber juice, 15% spinach juice, and 2% lemon juice, providing 34 kcal per 100 mL with no added sugar."
    },
    "FS-PROD-006": {
        "name": "Citrus Carrot Ginger Blend",
        "mrp": 115,
        "processing": "Cold-Pressed, High-Pressure Processed (HPP)",
        "sugar_type": "fruit and vegetable",
        "pack_size": "250 mL",
        "approved_claim_code": "FS-CLAIM-008",
        "approved_claim": "Combines 50% Valencia orange juice, 45% carrot juice, 3.5% ginger juice, and 1.5% lemon juice in a 250 mL glass bottle at MRP ₹115."
    }
}


class SuggestionService:
    """
    Context-preserving correction suggestion engine.
    Produces evidence-grounded, explainable suggestions for governance findings.
    Preserves creator original text, strictly respects product scoping,
    and enforces differences between editable text and non-editable artwork.
    """

    def generate_diff_preview(self, original: str, proposed: str) -> str:
        """Create a clean, human-readable diff representation."""
        if not original or not proposed:
            return ""
        return f"- {original}\n+ {proposed}"

    def detect_sku_from_text(self, text: str, title: str) -> Optional[str]:
        """Identify which SKU is referenced in the copy or title."""
        combined = f"{title} {text}".lower()
        if any(k in combined for k in ["fs-prod-001", "valencia orange"]):
            return "FS-PROD-001"
        if any(k in combined for k in ["fs-prod-002", "pink guava", "pomegranate nectar"]):
            return "FS-PROD-002"
        if any(k in combined for k in ["fs-prod-003", "garden tomato", "tomato celery"]):
            return "FS-PROD-003"
        if any(k in combined for k in ["fs-prod-004", "spiced carrot", "carrot beetroot"]):
            return "FS-PROD-004"
        if any(k in combined for k in ["fs-prod-005", "green orchard", "cucumber spinach"]):
            return "FS-PROD-005"
        if any(k in combined for k in ["fs-prod-006", "citrus carrot", "carrot ginger"]):
            return "FS-PROD-006"
        return None

    def generate_suggestions_for_run(self, db: Session, run: GovernanceRun) -> List[CorrectionSuggestion]:
        """
        Evaluate all unresolved findings in a governance run and generate
        evidence-grounded correction suggestions.
        """
        version = db.query(ContentVersion).filter(ContentVersion.id == run.content_version_id).first()
        if not version:
            return []

        item = db.query(ContentItem).filter(ContentItem.id == version.content_item_id).first()
        if not item:
            return []

        detected_sku = self.detect_sku_from_text(version.body_text or "", item.title or "")
        suggestions: List[CorrectionSuggestion] = []

        findings = db.query(GovernanceFinding).filter(
            GovernanceFinding.governance_run_id == run.id,
            GovernanceFinding.status != "passed_check"
        ).all()

        for finding in findings:
            # Check if suggestion already exists for this finding
            existing = db.query(CorrectionSuggestion).filter(CorrectionSuggestion.finding_id == finding.id).first()
            if existing:
                suggestions.append(existing)
                continue

            suggestion = self._generate_suggestion_for_finding(
                db=db,
                finding=finding,
                version=version,
                item=item,
                detected_sku=detected_sku
            )
            if suggestion:
                db.add(suggestion)
                suggestions.append(suggestion)

        db.commit()
        return suggestions

    def _generate_suggestion_for_finding(
        self,
        db: Session,
        finding: GovernanceFinding,
        version: ContentVersion,
        item: ContentItem,
        detected_sku: Optional[str]
    ) -> Optional[CorrectionSuggestion]:
        """Route finding to appropriate category generator."""
        # 1. Determine target type
        if finding.page_number is not None:
            target_type = "pdf_page"
        elif "Poster" in (finding.title or "") or "Poster" in (finding.text_excerpt or ""):
            target_type = "poster_image"
        elif finding.category in ("image_guideline_issue", "contrast", "dimensions", "colour", "logo", "accessibility", "layout"):
            target_type = "poster_image"
        else:
            target_type = "body_text"

        rule = db.query(KnowledgeRule).filter(KnowledgeRule.id == finding.matched_rule_id).first() if finding.matched_rule_id else None
        fact = db.query(KnowledgeFact).filter(KnowledgeFact.id == finding.matched_fact_id).first() if finding.matched_fact_id else None
        rule_code = rule.rule_code if rule else None
        if not rule_code:
            # Extract FR-RULE-XXX from title if present
            m_code = re.search(r"FR-RULE-\d+", finding.title or "")
            if m_code:
                rule_code = m_code.group(0)

        # -------------------------------------------------------------
        # Category A: Terminology and Prohibited Wording
        # -------------------------------------------------------------
        if rule_code == "FR-RULE-005" or "sugar-free" in (finding.title or "").lower() or "zero sugar" in (finding.title or "").lower():
            return self._build_sugar_terminology_suggestion(finding, version, item, target_type, rule, detected_sku)

        if rule_code == "FR-RULE-004" or "miracle" in (finding.title or "").lower() or "magic" in (finding.title or "").lower():
            return self._build_miracle_terminology_suggestion(finding, version, item, target_type, rule)

        if rule_code == "FR-RULE-006" or "raw" in (finding.title or "").lower() or "unprocessed" in (finding.title or "").lower():
            return self._build_processing_terminology_suggestion(finding, version, item, target_type, rule, detected_sku)

        if rule_code == "FR-RULE-001" or "naming" in (finding.title or "").lower() or "pvt. ltd." in (finding.text_excerpt or "").lower():
            return self._build_naming_suggestion(finding, version, item, target_type, rule)

        if rule_code == "FR-RULE-010" or "organic" in (finding.title or "").lower() or "natural" in (finding.title or "").lower() or "chemical-free" in (finding.title or "").lower():
            return self._build_natural_organic_suggestion(finding, version, item, target_type, rule, detected_sku)

        if rule_code == "FR-RULE-011" or "superlative" in (finding.title or "").lower() or "india's #" in (finding.text_excerpt or "").lower():
            return self._build_superlative_suggestion(finding, version, item, target_type, rule)

        # -------------------------------------------------------------
        # Category B: Promotional Claims & Product Facts
        # -------------------------------------------------------------
        if rule_code == "FR-RULE-015" or finding.category == "product_fact_mismatch" or "mrp" in (finding.title or "").lower() or "price" in (finding.title or "").lower():
            return self._build_price_or_fact_suggestion(finding, version, item, target_type, rule, fact, detected_sku)

        if rule_code == "FR-RULE-016" or "discount" in (finding.title or "").lower() or "flash sale" in (finding.title or "").lower():
            return self._build_discount_suggestion(finding, version, item, target_type, rule)

        if rule_code in ("FR-RULE-007", "FR-RULE-008", "FR-RULE-018") or finding.category in ("unsupported_claim", "claim_status_issue"):
            return self._build_claim_suggestion(finding, version, item, target_type, rule, fact, detected_sku)

        # -------------------------------------------------------------
        # Category C: Mandatory Disclosures
        # -------------------------------------------------------------
        if rule_code == "FR-RULE-014" or finding.category == "mandatory_wording_missing":
            return self._build_disclosure_suggestion(finding, version, item, target_type, rule, detected_sku)

        # -------------------------------------------------------------
        # Category D: Tone and Voice
        # -------------------------------------------------------------
        if rule_code == "FR-RULE-002" or "fear-based" in (finding.title or "").lower() or "tone" in (finding.title or "").lower():
            return self._build_tone_suggestion(finding, version, item, target_type, rule)

        # -------------------------------------------------------------
        # Category E: Visual, Contrast, and Accessibility
        # -------------------------------------------------------------
        if finding.category in ("image_guideline_issue", "contrast", "dimensions", "colour", "logo", "accessibility", "layout") or target_type in ("poster_image", "pdf_page"):
            return self._build_visual_suggestion(finding, version, item, target_type, rule, detected_sku)

        # Fallback manual guidance
        return CorrectionSuggestion(
            finding_id=finding.id,
            content_item_id=item.id,
            content_version_id=version.id,
            source_checksum=version.checksum,
            target_type=target_type,
            page_number=finding.page_number,
            rule_id=finding.matched_rule_id,
            rule_code=rule_code,
            fact_id=finding.matched_fact_id,
            original_text=finding.text_excerpt or (version.body_text[:100] if version.body_text else "Content"),
            proposed_text=None,
            diff_preview=None,
            explanation=f"Manual review required: {finding.explanation}",
            evidence_source=finding.source_citation,
            correction_type="manual_guidance",
            confidence="manual_review",
            can_auto_apply=False,
            status="pending"
        )

    # -----------------------------------------------------------------
    # SPECIFIC CATEGORY BUILDERS
    # -----------------------------------------------------------------

    def _build_sugar_terminology_suggestion(
        self,
        finding: GovernanceFinding,
        version: ContentVersion,
        item: ContentItem,
        target_type: str,
        rule: Optional[KnowledgeRule],
        sku: Optional[str]
    ) -> CorrectionSuggestion:
        meta = CANONICAL_PRODUCT_METADATA.get(sku or "", {})
        sugar_type = meta.get("sugar_type", "fruit")
        approved_phrase = f"no added sugar (contains naturally occurring {sugar_type} sugars)"

        original_excerpt = finding.text_excerpt or "sugar-free"
        cleaned_orig = re.sub(r"^\[Page \d+\]\s*", "", original_excerpt).strip("'\" ")

        if target_type == "body_text":
            body = version.body_text or ""
            # Find and replace deterministically
            pattern = re.compile(r"\b(?:100%\s+)?(?:sugar[ -]free|zero\s+sugar)\b", re.IGNORECASE)
            m = pattern.search(body)
            if m:
                matched_str = m.group(0)
                proposed_passage = body[:m.start()] + approved_phrase + body[m.end():]
                diff = self.generate_diff_preview(matched_str, approved_phrase)
                return CorrectionSuggestion(
                    finding_id=finding.id,
                    content_item_id=item.id,
                    content_version_id=version.id,
                    source_checksum=version.checksum,
                    target_type="body_text",
                    page_number=None,
                    rule_id=rule.id if rule else None,
                    rule_code="FR-RULE-005",
                    original_text=matched_str,
                    proposed_text=approved_phrase,
                    diff_preview=diff,
                    explanation="Replaces prohibited 'sugar-free'/'zero sugar' phrase with approved 'no added sugar' terminology acknowledging naturally occurring sugars (FR-RULE-005).",
                    evidence_source="freshsip_brand_guidelines.pdf, Section C: Terminology Rules",
                    correction_type="deterministic_replacement",
                    confidence="high",
                    can_auto_apply=True,
                    status="pending"
                )

        # If in artwork/PDF
        page_str = f"on Page {finding.page_number} " if finding.page_number else "in creative artwork "
        return CorrectionSuggestion(
            finding_id=finding.id,
            content_item_id=item.id,
            content_version_id=version.id,
            source_checksum=version.checksum,
            target_type=target_type,
            page_number=finding.page_number,
            rule_id=rule.id if rule else None,
            rule_code="FR-RULE-005",
            original_text=cleaned_orig,
            proposed_text=f"Replace '{cleaned_orig}' with 'No added sugar' in artwork layout.",
            diff_preview=f"- {cleaned_orig}\n+ No added sugar (per specification)",
            explanation=f"Prohibited sugar terminology detected {page_str}. Flattened creative artwork cannot be modified directly via text replacement. Update copy in design file and re-upload.",
            evidence_source="freshsip_brand_guidelines.pdf, Section C: Terminology Rules",
            correction_type="manual_guidance",
            confidence="high",
            can_auto_apply=False,
            status="pending"
        )

    def _build_miracle_terminology_suggestion(
        self,
        finding: GovernanceFinding,
        version: ContentVersion,
        item: ContentItem,
        target_type: str,
        rule: Optional[KnowledgeRule]
    ) -> CorrectionSuggestion:
        original_excerpt = finding.text_excerpt or "miracle juice"
        cleaned_orig = re.sub(r"^\[Page \d+\]\s*", "", original_excerpt).strip("'\" ")
        replacement = "vibrant cold-pressed blend"

        if target_type == "body_text":
            body = version.body_text or ""
            pattern = re.compile(r"\b(?:miracle\s+juice|magic\s+elixir|magic\s+potion|superfood\s+cure-all|liquid\s+medicine)\b", re.IGNORECASE)
            m = pattern.search(body)
            if m:
                matched_str = m.group(0)
                diff = self.generate_diff_preview(matched_str, replacement)
                return CorrectionSuggestion(
                    finding_id=finding.id,
                    content_item_id=item.id,
                    content_version_id=version.id,
                    source_checksum=version.checksum,
                    target_type="body_text",
                    page_number=None,
                    rule_id=rule.id if rule else None,
                    rule_code="FR-RULE-004",
                    original_text=matched_str,
                    proposed_text=replacement,
                    diff_preview=diff,
                    explanation="Removes sensationalist terminology attributing supernatural properties, replacing with factual beverage phrasing (FR-RULE-004).",
                    evidence_source="freshsip_brand_guidelines.pdf, Section C: Terminology Rules",
                    correction_type="deterministic_replacement",
                    confidence="high",
                    can_auto_apply=True,
                    status="pending"
                )

        return CorrectionSuggestion(
            finding_id=finding.id,
            content_item_id=item.id,
            content_version_id=version.id,
            source_checksum=version.checksum,
            target_type=target_type,
            page_number=finding.page_number,
            rule_id=rule.id if rule else None,
            rule_code="FR-RULE-004",
            original_text=cleaned_orig,
            proposed_text="Remove miraculous/medicinal adjectives in creative layout.",
            diff_preview=f"- {cleaned_orig}\n+ Refreshing blend",
            explanation="Avoid describing beverages with sensationalist adjectives like miracle or magic. Update artwork in authoring tool.",
            evidence_source="freshsip_brand_guidelines.pdf, Section C: Terminology Rules",
            correction_type="manual_guidance",
            confidence="high",
            can_auto_apply=False,
            status="pending"
        )

    def _build_processing_terminology_suggestion(
        self,
        finding: GovernanceFinding,
        version: ContentVersion,
        item: ContentItem,
        target_type: str,
        rule: Optional[KnowledgeRule],
        sku: Optional[str]
    ) -> CorrectionSuggestion:
        meta = CANONICAL_PRODUCT_METADATA.get(sku or "", {})
        approved_processing = meta.get("processing", "High-Pressure Processed (HPP)")

        original_excerpt = finding.text_excerpt or "100% raw"
        cleaned_orig = re.sub(r"^\[Page \d+\]\s*", "", original_excerpt).strip("'\" ")

        if target_type == "body_text":
            body = version.body_text or ""
            pattern = re.compile(r"\b(?:100%\s+raw|completely\s+unprocessed|unprocessed|straight\s+from\s+the\s+farm\s+without\s+processing)\b", re.IGNORECASE)
            m = pattern.search(body)
            if m:
                matched_str = m.group(0)
                diff = self.generate_diff_preview(matched_str, approved_processing)
                return CorrectionSuggestion(
                    finding_id=finding.id,
                    content_item_id=item.id,
                    content_version_id=version.id,
                    source_checksum=version.checksum,
                    target_type="body_text",
                    page_number=None,
                    rule_id=rule.id if rule else None,
                    rule_code="FR-RULE-006",
                    original_text=matched_str,
                    proposed_text=approved_processing,
                    diff_preview=diff,
                    explanation=f"Replaces inaccurate raw/unprocessed terminology with approved processing method '{approved_processing}' (FR-RULE-006).",
                    evidence_source="freshsip_brand_guidelines.pdf, Section C: Terminology Rules",
                    correction_type="deterministic_replacement",
                    confidence="high",
                    can_auto_apply=True,
                    status="pending"
                )

        return CorrectionSuggestion(
            finding_id=finding.id,
            content_item_id=item.id,
            content_version_id=version.id,
            source_checksum=version.checksum,
            target_type=target_type,
            page_number=finding.page_number,
            rule_id=rule.id if rule else None,
            rule_code="FR-RULE-006",
            original_text=cleaned_orig,
            proposed_text=f"Replace '{cleaned_orig}' with '{approved_processing}' in artwork layout.",
            diff_preview=f"- {cleaned_orig}\n+ {approved_processing}",
            explanation=f"All packaged Freshsip beverages undergo processing ({approved_processing}). Revise design file and re-upload.",
            evidence_source="freshsip_brand_guidelines.pdf, Section C: Terminology Rules",
            correction_type="manual_guidance",
            confidence="high",
            can_auto_apply=False,
            status="pending"
        )

    def _build_naming_suggestion(
        self,
        finding: GovernanceFinding,
        version: ContentVersion,
        item: ContentItem,
        target_type: str,
        rule: Optional[KnowledgeRule]
    ) -> CorrectionSuggestion:
        original_excerpt = finding.text_excerpt or "Freshsip Organic Pvt. Ltd."
        cleaned_orig = re.sub(r"^\[Page \d+\]\s*", "", original_excerpt).strip("'\" ")
        replacement = "Freshsip Beverages"

        if target_type == "body_text":
            body = version.body_text or ""
            pattern = re.compile(r"\bFreshsip(?:\s+Organic)?(?:\s+Pvt\.?\s*Ltd\.?)\b", re.IGNORECASE)
            m = pattern.search(body)
            if m:
                matched_str = m.group(0)
                diff = self.generate_diff_preview(matched_str, replacement)
                return CorrectionSuggestion(
                    finding_id=finding.id,
                    content_item_id=item.id,
                    content_version_id=version.id,
                    source_checksum=version.checksum,
                    target_type="body_text",
                    page_number=None,
                    rule_id=rule.id if rule else None,
                    rule_code="FR-RULE-001",
                    original_text=matched_str,
                    proposed_text=replacement,
                    diff_preview=diff,
                    explanation="Aligns brand name with approved corporate identity 'Freshsip Beverages' without fabricated corporate registration suffixes (FR-RULE-001).",
                    evidence_source="freshsip_brand_guidelines.pdf, Section A: Brand Identity",
                    correction_type="deterministic_replacement",
                    confidence="high",
                    can_auto_apply=True,
                    status="pending"
                )

        return CorrectionSuggestion(
            finding_id=finding.id,
            content_item_id=item.id,
            content_version_id=version.id,
            source_checksum=version.checksum,
            target_type=target_type,
            page_number=finding.page_number,
            rule_id=rule.id if rule else None,
            rule_code="FR-RULE-001",
            original_text=cleaned_orig,
            proposed_text="Replace corporate suffix with 'Freshsip Beverages'.",
            diff_preview=f"- {cleaned_orig}\n+ Freshsip Beverages",
            explanation="Use canonical brand naming in creative artwork. Revise layout in authoring software.",
            evidence_source="freshsip_brand_guidelines.pdf, Section A: Brand Identity",
            correction_type="manual_guidance",
            confidence="high",
            can_auto_apply=False,
            status="pending"
        )

    def _build_natural_organic_suggestion(
        self,
        finding: GovernanceFinding,
        version: ContentVersion,
        item: ContentItem,
        target_type: str,
        rule: Optional[KnowledgeRule],
        sku: Optional[str]
    ) -> CorrectionSuggestion:
        replacement = "no added preservatives (per internal synthetic specification)"
        original_excerpt = finding.text_excerpt or "100% natural"
        cleaned_orig = re.sub(r"^\[Page \d+\]\s*", "", original_excerpt).strip("'\" ")

        if target_type == "body_text":
            body = version.body_text or ""
            pattern = re.compile(r"\b(?:100%\s+natural|certified\s+organic|pesticide[ -]free|chemical[ -]free|farm[ -]certified)\b", re.IGNORECASE)
            m = pattern.search(body)
            if m:
                matched_str = m.group(0)
                diff = self.generate_diff_preview(matched_str, replacement)
                return CorrectionSuggestion(
                    finding_id=finding.id,
                    content_item_id=item.id,
                    content_version_id=version.id,
                    source_checksum=version.checksum,
                    target_type="body_text",
                    page_number=None,
                    rule_id=rule.id if rule else None,
                    rule_code="FR-RULE-010",
                    original_text=matched_str,
                    proposed_text=replacement,
                    diff_preview=diff,
                    explanation="Removes unsupported organic/chemical-free claims and substitutes approved preservative status (FR-RULE-010).",
                    evidence_source="freshsip_brand_guidelines.pdf, Section D: Messaging and Claims",
                    correction_type="deterministic_replacement",
                    confidence="high",
                    can_auto_apply=True,
                    status="pending"
                )

        return CorrectionSuggestion(
            finding_id=finding.id,
            content_item_id=item.id,
            content_version_id=version.id,
            source_checksum=version.checksum,
            target_type=target_type,
            page_number=finding.page_number,
            rule_id=rule.id if rule else None,
            rule_code="FR-RULE-010",
            original_text=cleaned_orig,
            proposed_text="Remove uncertified organic/natural claims in creative artwork.",
            diff_preview=f"- {cleaned_orig}\n+ No added preservatives",
            explanation="Freshsip holds no organic or chemical-free certifications. Update artwork in authoring tool.",
            evidence_source="freshsip_brand_guidelines.pdf, Section D: Messaging and Claims",
            correction_type="manual_guidance",
            confidence="high",
            can_auto_apply=False,
            status="pending"
        )

    def _build_superlative_suggestion(
        self,
        finding: GovernanceFinding,
        version: ContentVersion,
        item: ContentItem,
        target_type: str,
        rule: Optional[KnowledgeRule]
    ) -> CorrectionSuggestion:
        replacement = "crafted with transparent ingredient percentages and no added preservatives"
        original_excerpt = finding.text_excerpt or "India's #1"
        cleaned_orig = re.sub(r"^\[Page \d+\]\s*", "", original_excerpt).strip("'\" ")

        if target_type == "body_text":
            body = version.body_text or ""
            pattern = re.compile(r"\b(?:India's\s+#1|India's\s+healthiest|fresher\s+than\s+any\s+other\s+brand|the\s+purest\s+juice\s+in\s+India)\b", re.IGNORECASE)
            m = pattern.search(body)
            if m:
                matched_str = m.group(0)
                diff = self.generate_diff_preview(matched_str, replacement)
                return CorrectionSuggestion(
                    finding_id=finding.id,
                    content_item_id=item.id,
                    content_version_id=version.id,
                    source_checksum=version.checksum,
                    target_type="body_text",
                    page_number=None,
                    rule_id=rule.id if rule else None,
                    rule_code="FR-RULE-011",
                    original_text=matched_str,
                    proposed_text=replacement,
                    diff_preview=diff,
                    explanation="Replaces unsubstantiated market-ranking superlative with factual formulation claim (FR-RULE-011).",
                    evidence_source="freshsip_brand_guidelines.pdf, Section D: Messaging and Claims",
                    correction_type="deterministic_replacement",
                    confidence="high",
                    can_auto_apply=True,
                    status="pending"
                )

        return CorrectionSuggestion(
            finding_id=finding.id,
            content_item_id=item.id,
            content_version_id=version.id,
            source_checksum=version.checksum,
            target_type=target_type,
            page_number=finding.page_number,
            rule_id=rule.id if rule else None,
            rule_code="FR-RULE-011",
            original_text=cleaned_orig,
            proposed_text="Remove market-ranking superlatives from creative artwork.",
            diff_preview=f"- {cleaned_orig}\n+ Crafted with transparent ingredients",
            explanation="Unsubstantiated comparative superiority claims require independent market audit. Update artwork in design tool.",
            evidence_source="freshsip_brand_guidelines.pdf, Section D: Messaging and Claims",
            correction_type="manual_guidance",
            confidence="high",
            can_auto_apply=False,
            status="pending"
        )

    def _build_price_or_fact_suggestion(
        self,
        finding: GovernanceFinding,
        version: ContentVersion,
        item: ContentItem,
        target_type: str,
        rule: Optional[KnowledgeRule],
        fact: Optional[KnowledgeFact],
        sku: Optional[str]
    ) -> CorrectionSuggestion:
        meta = CANONICAL_PRODUCT_METADATA.get(sku or "", {})
        approved_mrp = meta.get("mrp", 120)
        approved_price_str = f"₹{approved_mrp}"

        original_excerpt = finding.text_excerpt or "Price"
        cleaned_orig = re.sub(r"^\[Page \d+\]\s*", "", original_excerpt).strip("'\" ")

        # Look for price in excerpt or body
        m_price = re.search(r"[₹fF\s:.-]*(\d{2,4})\b", cleaned_orig)
        found_num = m_price.group(1) if m_price else None

        if target_type == "body_text":
            body = version.body_text or ""
            if found_num:
                pattern = re.compile(rf"[₹]?\s*{found_num}\b")
                m = pattern.search(body)
                if m:
                    matched_str = m.group(0)
                    diff = self.generate_diff_preview(matched_str, approved_price_str)
                    return CorrectionSuggestion(
                        finding_id=finding.id,
                        content_item_id=item.id,
                        content_version_id=version.id,
                        source_checksum=version.checksum,
                        target_type="body_text",
                        page_number=None,
                        rule_id=rule.id if rule else None,
                        rule_code="FR-RULE-015",
                        fact_id=fact.id if fact else None,
                        fact_key="approved_price_inr",
                        original_text=matched_str,
                        proposed_text=approved_price_str,
                        diff_preview=diff,
                        explanation=f"Corrects promotional price to approved catalogue MRP ({approved_price_str}) for {meta.get('name', 'product')} (FR-RULE-015).",
                        evidence_source=f"freshsip_products.csv (SKU: {sku or 'FS-PROD-001'}, MRP: {approved_price_str})",
                        correction_type="factual_correction",
                        confidence="high",
                        can_auto_apply=True,
                        status="pending"
                    )

        return CorrectionSuggestion(
            finding_id=finding.id,
            content_item_id=item.id,
            content_version_id=version.id,
            source_checksum=version.checksum,
            target_type=target_type,
            page_number=finding.page_number,
            rule_id=rule.id if rule else None,
            rule_code="FR-RULE-015",
            fact_id=fact.id if fact else None,
            fact_key="approved_price_inr",
            original_text=cleaned_orig,
            proposed_text=f"Correct price display to approved MRP {approved_price_str} in artwork layout.",
            diff_preview=f"- {cleaned_orig}\n+ MRP {approved_price_str}",
            explanation=f"Advertised price in creative artwork does not match catalogue MRP ({approved_price_str}). Update artwork in design file and re-upload.",
            evidence_source=f"freshsip_products.csv (SKU: {sku or 'FS-PROD-001'}, MRP: {approved_price_str})",
            correction_type="manual_guidance",
            confidence="high",
            can_auto_apply=False,
            status="pending"
        )

    def _build_discount_suggestion(
        self,
        finding: GovernanceFinding,
        version: ContentVersion,
        item: ContentItem,
        target_type: str,
        rule: Optional[KnowledgeRule]
    ) -> CorrectionSuggestion:
        replacement = "Explore our 250 mL range, priced from ₹95 to ₹130 per bottle."
        original_excerpt = finding.text_excerpt or "50% OFF"
        cleaned_orig = re.sub(r"^\[Page \d+\]\s*", "", original_excerpt).strip("'\" ")

        if target_type == "body_text":
            body = version.body_text or ""
            pattern = re.compile(r"\b(?:\d+%\s+OFF|FLASH\s+SALE|promo\s+code\s+[A-Z0-9]+|code\s+[A-Z0-9]+)\b", re.IGNORECASE)
            m = pattern.search(body)
            if m:
                matched_str = m.group(0)
                diff = self.generate_diff_preview(matched_str, replacement)
                return CorrectionSuggestion(
                    finding_id=finding.id,
                    content_item_id=item.id,
                    content_version_id=version.id,
                    source_checksum=version.checksum,
                    target_type="body_text",
                    page_number=None,
                    rule_id=rule.id if rule else None,
                    rule_code="FR-RULE-016",
                    original_text=matched_str,
                    proposed_text=replacement,
                    diff_preview=diff,
                    explanation="Freshsip has no active discount promotion in the approved dataset. Replaces unapproved discount/scarcity claim with approved catalogue pricing range (FR-RULE-016).",
                    evidence_source="freshsip_brand_guidelines.pdf, Section F: Product and Promotion Rules",
                    correction_type="deterministic_replacement",
                    confidence="high",
                    can_auto_apply=True,
                    status="pending"
                )

        return CorrectionSuggestion(
            finding_id=finding.id,
            content_item_id=item.id,
            content_version_id=version.id,
            source_checksum=version.checksum,
            target_type=target_type,
            page_number=finding.page_number,
            rule_id=rule.id if rule else None,
            rule_code="FR-RULE-016",
            original_text=cleaned_orig,
            proposed_text="Remove discount badges and promo codes from creative artwork.",
            diff_preview=f"- {cleaned_orig}\n+ Standard catalogue pricing",
            explanation="No promotional discount campaign is active for Freshsip. Update artwork in authoring tool.",
            evidence_source="freshsip_brand_guidelines.pdf, Section F: Product and Promotion Rules",
            correction_type="manual_guidance",
            confidence="high",
            can_auto_apply=False,
            status="pending"
        )

    def _build_claim_suggestion(
        self,
        finding: GovernanceFinding,
        version: ContentVersion,
        item: ContentItem,
        target_type: str,
        rule: Optional[KnowledgeRule],
        fact: Optional[KnowledgeFact],
        sku: Optional[str]
    ) -> CorrectionSuggestion:
        original_excerpt = finding.text_excerpt or "Claim"
        cleaned_orig = re.sub(r"^\[Page \d+\]\s*", "", original_excerpt).strip("'\" ")

        meta = CANONICAL_PRODUCT_METADATA.get(sku or "", {})
        approved_claim = meta.get("approved_claim")
        approved_claim_code = meta.get("approved_claim_code")

        # PRODUCT & SKU SCOPING GUARD:
        # If an approved claim exists for this EXACT SKU, we can propose substituting it.
        # Otherwise, we MUST recommend removing the unverified claim without inventing facts!
        if approved_claim and target_type == "body_text":
            body = version.body_text or ""
            # Check if an unapproved claim sentence can be replaced
            m_claim = re.search(r"[^.!?\n]+(?:cures?|prevents?|treats?|detox|cleanse|fat burning|weight loss)[^.!?\n]+[.!?]?", body, re.IGNORECASE)
            if m_claim:
                matched_str = m_claim.group(0).strip()
                diff = self.generate_diff_preview(matched_str, approved_claim)
                return CorrectionSuggestion(
                    finding_id=finding.id,
                    content_item_id=item.id,
                    content_version_id=version.id,
                    source_checksum=version.checksum,
                    target_type="body_text",
                    page_number=None,
                    rule_id=rule.id if rule else None,
                    rule_code=rule.rule_code if rule else "FR-RULE-007",
                    fact_id=fact.id if fact else None,
                    fact_key=approved_claim_code,
                    original_text=matched_str,
                    proposed_text=approved_claim,
                    diff_preview=diff,
                    explanation=f"Replaces unverified claim with approved marketing claim '{approved_claim_code}' specifically established for {meta.get('name', 'product')}.",
                    evidence_source=f"freshsip_approved_claims.csv (Claim ID: {approved_claim_code})",
                    correction_type="factual_correction",
                    confidence="high",
                    can_auto_apply=True,
                    status="pending"
                )

        # Non-replaceable claim or unapproved claim without matching approved claim
        return CorrectionSuggestion(
            finding_id=finding.id,
            content_item_id=item.id,
            content_version_id=version.id,
            source_checksum=version.checksum,
            target_type=target_type,
            page_number=finding.page_number,
            rule_id=rule.id if rule else None,
            rule_code=rule.rule_code if rule else "FR-RULE-007",
            fact_id=fact.id if fact else None,
            fact_key=fact.fact_key if fact else None,
            original_text=cleaned_orig,
            proposed_text=None,
            diff_preview=f"- {cleaned_orig}\n[Remove unsupported claim or upload verified substantiation]",
            explanation="Health, disease, or unverified performance claims cannot be substantiated from approved records for this SKU. Remove the claim or request review from an authorized Brand Governance Lead.",
            evidence_source=finding.source_citation,
            correction_type="manual_guidance",
            confidence="manual_review",
            can_auto_apply=False,
            status="pending"
        )

    def _build_disclosure_suggestion(
        self,
        finding: GovernanceFinding,
        version: ContentVersion,
        item: ContentItem,
        target_type: str,
        rule: Optional[KnowledgeRule],
        sku: Optional[str]
    ) -> CorrectionSuggestion:
        if sku == "FS-PROD-003" or "celery" in (finding.title or "").lower():
            disclosure = "Contains Celery (14%). Keep refrigerated at 2°C to 5°C; consume within 24 hours of opening."
            explanation = "Appends mandatory allergen disclosure (Contains Celery 14%) and storage instructions required for Garden Tomato Celery Press (FS-PROD-003) under FR-RULE-014."
        else:
            disclosure = "Keep refrigerated at 2°C to 5°C. Shake well before drinking. Consume within 24 hours of opening."
            explanation = "Appends mandatory storage instructions under FR-RULE-014."

        if target_type == "body_text":
            body = (version.body_text or "").strip()
            proposed_passage = f"{body}\n\n{disclosure}" if body else disclosure
            diff = f"+ {disclosure}"
            return CorrectionSuggestion(
                finding_id=finding.id,
                content_item_id=item.id,
                content_version_id=version.id,
                source_checksum=version.checksum,
                target_type="body_text",
                page_number=None,
                rule_id=rule.id if rule else None,
                rule_code="FR-RULE-014",
                original_text="[Missing Mandatory Disclosure]",
                proposed_text=disclosure,
                diff_preview=diff,
                explanation=explanation,
                evidence_source="freshsip_brand_guidelines.pdf, Section E: Mandatory Wording and Disclosures",
                correction_type="mandatory_disclosure_insertion",
                confidence="high",
                can_auto_apply=True,
                status="pending"
            )

        return CorrectionSuggestion(
            finding_id=finding.id,
            content_item_id=item.id,
            content_version_id=version.id,
            source_checksum=version.checksum,
            target_type=target_type,
            page_number=finding.page_number,
            rule_id=rule.id if rule else None,
            rule_code="FR-RULE-014",
            original_text="[Missing Artwork Disclosure]",
            proposed_text=f"Insert disclosure in artwork layout: '{disclosure}'",
            diff_preview=f"+ {disclosure}",
            explanation=f"{explanation} Disclosure must appear in creative artwork. Update design file and re-upload.",
            evidence_source="freshsip_brand_guidelines.pdf, Section E: Mandatory Wording and Disclosures",
            correction_type="manual_guidance",
            confidence="high",
            can_auto_apply=False,
            status="pending"
        )

    def _build_tone_suggestion(
        self,
        finding: GovernanceFinding,
        version: ContentVersion,
        item: ContentItem,
        target_type: str,
        rule: Optional[KnowledgeRule]
    ) -> CorrectionSuggestion:
        original_excerpt = finding.text_excerpt or "Fear-based language"
        cleaned_orig = re.sub(r"^\[Page \d+\]\s*", "", original_excerpt).strip("'\" ")
        replacement = "Looking for a crisp, refreshing afternoon pick-me-up? Enjoy a chilled bottle of Freshsip."

        if target_type == "body_text":
            body = version.body_text or ""
            pattern = re.compile(r"[^.!?\n]*(?:silently poisoning|toxic sludge|before it is too late|fear|shame)[^.!?\n]*[.!?]?", re.IGNORECASE)
            m = pattern.search(body)
            if m:
                matched_str = m.group(0).strip()
                diff = self.generate_diff_preview(matched_str, replacement)
                return CorrectionSuggestion(
                    finding_id=finding.id,
                    content_item_id=item.id,
                    content_version_id=version.id,
                    source_checksum=version.checksum,
                    target_type="body_text",
                    page_number=None,
                    rule_id=rule.id if rule else None,
                    rule_code="FR-RULE-002",
                    original_text=matched_str,
                    proposed_text=replacement,
                    diff_preview=diff,
                    explanation="Replaces fear-based, alarmist tone with friendly, approachable brand voice (FR-RULE-002).",
                    evidence_source="freshsip_brand_guidelines.pdf, Section B: Tone of Voice",
                    correction_type="tone_refinement",
                    confidence="high",
                    can_auto_apply=True,
                    status="pending"
                )

        return CorrectionSuggestion(
            finding_id=finding.id,
            content_item_id=item.id,
            content_version_id=version.id,
            source_checksum=version.checksum,
            target_type=target_type,
            page_number=finding.page_number,
            rule_id=rule.id if rule else None,
            rule_code="FR-RULE-002",
            original_text=cleaned_orig,
            proposed_text="Replace alarmist headline with approachable brand tone in design layout.",
            diff_preview=f"- {cleaned_orig}\n+ {replacement}",
            explanation="Freshsip brand voice is friendly and trustworthy. Update creative artwork in authoring tool.",
            evidence_source="freshsip_brand_guidelines.pdf, Section B: Tone of Voice",
            correction_type="manual_guidance",
            confidence="high",
            can_auto_apply=False,
            status="pending"
        )

    def _build_visual_suggestion(
        self,
        finding: GovernanceFinding,
        version: ContentVersion,
        item: ContentItem,
        target_type: str,
        rule: Optional[KnowledgeRule],
        sku: Optional[str]
    ) -> CorrectionSuggestion:
        original_excerpt = finding.text_excerpt or "Visual finding"
        page_ctx = f"on Page {finding.page_number} " if finding.page_number else "in creative artwork "

        if "contrast" in (finding.title or "").lower():
            explanation = f"Text contrast measurement fails WCAG 2.1 AA (4.5:1) {page_ctx}. Adjust typography color or increase background darkness in authoring tool to achieve at least 4.5:1 contrast."
            remediation = "Adjust font color or increase background contrast to >= 4.5:1."
        elif "clear" in (finding.title or "").lower() or "logo" in (finding.title or "").lower():
            explanation = f"Logo clear space violation detected {page_ctx}. Maintain minimum buffer of 25% of logo height around the mark without overlapping text or graphics."
            remediation = "Reposition adjacent elements to maintain 25% logo clear space buffer."
        elif "alt text" in (finding.title or "").lower():
            meta = CANONICAL_PRODUCT_METADATA.get(sku or "", {})
            prod_name = meta.get("name", "juice")
            proposed_alt = f"Bottle of Freshsip {prod_name} (250 mL) in glass packaging with fresh fruit ingredients."
            return CorrectionSuggestion(
                finding_id=finding.id,
                content_item_id=item.id,
                content_version_id=version.id,
                source_checksum=version.checksum,
                target_type="body_text",
                page_number=None,
                rule_id=rule.id if rule else None,
                rule_code="FR-RULE-017",
                original_text="[Missing Alt Text]",
                proposed_text=proposed_alt,
                diff_preview=f"+ {proposed_alt}",
                explanation="Accessibility requirement: Images must provide descriptive alt text for screen readers.",
                evidence_source="freshsip_brand_guidelines.pdf, Section G: Asset-Use Rules",
                correction_type="accessibility_remediation",
                confidence="high",
                can_auto_apply=True,
                status="pending"
            )
        else:
            explanation = f"Visual guideline finding detected {page_ctx}. Review asset specifications and update in authoring tool."
            remediation = "Review asset dimensions, resolution, and color mode in authoring software."

        return CorrectionSuggestion(
            finding_id=finding.id,
            content_item_id=item.id,
            content_version_id=version.id,
            source_checksum=version.checksum,
            target_type=target_type,
            page_number=finding.page_number,
            rule_id=rule.id if rule else None,
            rule_code=rule.rule_code if rule else "FR-RULE-017",
            original_text=original_excerpt,
            proposed_text=remediation,
            diff_preview=f"[Visual Remediation]: {remediation}",
            explanation=explanation,
            evidence_source=finding.source_citation,
            correction_type="visual_remediation",
            confidence="manual_review",
            can_auto_apply=False,
            status="pending"
        )

    # -----------------------------------------------------------------
    # LIFECYCLE ACTIONS: ACCEPT, REJECT, APPLY-CUSTOM
    # -----------------------------------------------------------------

    def accept_suggestion(
        self,
        db: Session,
        suggestion_id: str,
        user: User
    ) -> Tuple[CorrectionSuggestion, ContentItem, Optional[ContentVersion], bool, str]:
        """
        Accept a suggestion with full version-integrity safeguards:
        1. Verify staleness against current content version and checksum.
        2. If can_auto_apply and target_type == 'body_text':
           Apply edit, create new ContentVersion, recompute checksum, set status to draft.
        3. If non-editable (PDF / poster) or manual:
           Record creator acceptance intent without falsely mutating source artwork.
        """
        suggestion = db.query(CorrectionSuggestion).filter(CorrectionSuggestion.id == suggestion_id).first()
        if not suggestion:
            raise ValueError("Correction suggestion not found.")

        item = db.query(ContentItem).filter(ContentItem.id == suggestion.content_item_id).first()
        if not item:
            raise ValueError("Content item not found.")

        current_ver = db.query(ContentVersion).filter(
            ContentVersion.content_item_id == item.id,
            ContentVersion.version_num == item.current_version_num
        ).first()

        if not current_ver:
            raise ValueError("Current content version not found.")

        # 1. Staleness Check
        if suggestion.content_version_id != current_ver.id or suggestion.source_checksum != current_ver.checksum:
            suggestion.status = "stale"
            db.commit()
            raise ValueError("Suggestion is stale: content version has been modified since suggestion was generated. Re-run governance check to get fresh suggestions.")

        # 2. Check if already resolved
        if suggestion.status in ("applied", "accepted", "rejected"):
            return suggestion, item, current_ver, False, f"Suggestion has already been {suggestion.status}."

        # 3. Apply edit if auto-applicable
        if suggestion.can_auto_apply and suggestion.target_type == "body_text":
            body = current_ver.body_text or ""
            new_body = None

            if suggestion.correction_type == "mandatory_disclosure_insertion":
                new_body = f"{body.strip()}\n\n{suggestion.proposed_text}" if body.strip() else suggestion.proposed_text
            elif suggestion.correction_type == "accessibility_remediation" and suggestion.rule_code == "FR-RULE-017":
                # Alt text update on version
                pass
            else:
                # Deterministic or factual replacement
                orig = suggestion.original_text
                prop = suggestion.proposed_text or ""
                if orig in body:
                    new_body = body.replace(orig, prop, 1)
                else:
                    # Regex replacement fallback
                    new_body = re.sub(re.escape(orig), prop, body, count=1, flags=re.IGNORECASE)

            if new_body is not None and new_body != body:
                # Mint a new ContentVersion
                new_version_num = item.current_version_num + 1
                new_checksum = ContentVersion.calculate_checksum(new_body, current_ver.poster_file_path)

                new_version = ContentVersion(
                    content_item_id=item.id,
                    version_num=new_version_num,
                    body_text=new_body,
                    checksum=new_checksum,
                    created_by=user.id,
                    poster_file_path=current_ver.poster_file_path,
                    poster_asset_id=current_ver.poster_asset_id,
                    poster_alt_text=current_ver.poster_alt_text
                )
                db.add(new_version)
                item.current_version_num = new_version_num
                item.status = "draft"
                item.updated_at = datetime.utcnow()

                suggestion.status = "applied"
                suggestion.resolved_at = datetime.utcnow()
                db.commit()
                db.refresh(item)
                db.refresh(new_version)
                db.refresh(suggestion)

                return (
                    suggestion,
                    item,
                    new_version,
                    True,
                    f"Applied suggestion and created version v{new_version_num}. Previous governance runs invalidated; please re-run governance check."
                )

        # 4. Non-editable source (PDF page or raster poster) or manual guidance
        suggestion.status = "accepted"
        suggestion.resolved_at = datetime.utcnow()
        db.commit()
        db.refresh(suggestion)

        return (
            suggestion,
            item,
            current_ver,
            False,
            "Suggestion accepted. Creative artwork is non-editable; please update the asset in your authoring software and re-upload the revised file."
        )

    def reject_suggestion(self, db: Session, suggestion_id: str, user: User) -> CorrectionSuggestion:
        """Reject a suggestion without modifying content or resolving the underlying finding."""
        suggestion = db.query(CorrectionSuggestion).filter(CorrectionSuggestion.id == suggestion_id).first()
        if not suggestion:
            raise ValueError("Correction suggestion not found.")

        suggestion.status = "rejected"
        suggestion.resolved_at = datetime.utcnow()
        db.commit()
        db.refresh(suggestion)
        return suggestion

    def apply_custom_suggestion(
        self,
        db: Session,
        suggestion_id: str,
        custom_text: str,
        user: User
    ) -> Tuple[CorrectionSuggestion, ContentItem, ContentVersion, str]:
        """Apply a creator-edited custom text revision to resolve the finding."""
        suggestion = db.query(CorrectionSuggestion).filter(CorrectionSuggestion.id == suggestion_id).first()
        if not suggestion:
            raise ValueError("Correction suggestion not found.")

        item = db.query(ContentItem).filter(ContentItem.id == suggestion.content_item_id).first()
        if not item:
            raise ValueError("Content item not found.")

        current_ver = db.query(ContentVersion).filter(
            ContentVersion.content_item_id == item.id,
            ContentVersion.version_num == item.current_version_num
        ).first()

        if not current_ver:
            raise ValueError("Current content version not found.")

        # Staleness check
        if suggestion.content_version_id != current_ver.id or suggestion.source_checksum != current_ver.checksum:
            suggestion.status = "stale"
            db.commit()
            raise ValueError("Suggestion is stale: content version has been modified since suggestion was generated.")

        body = current_ver.body_text or ""
        orig = suggestion.original_text

        if orig in body:
            new_body = body.replace(orig, custom_text, 1)
        else:
            new_body = f"{body.strip()}\n\n{custom_text}" if body.strip() else custom_text

        new_version_num = item.current_version_num + 1
        new_checksum = ContentVersion.calculate_checksum(new_body, current_ver.poster_file_path)

        new_version = ContentVersion(
            content_item_id=item.id,
            version_num=new_version_num,
            body_text=new_body,
            checksum=new_checksum,
            created_by=user.id,
            poster_file_path=current_ver.poster_file_path,
            poster_asset_id=current_ver.poster_asset_id,
            poster_alt_text=current_ver.poster_alt_text
        )
        db.add(new_version)
        item.current_version_num = new_version_num
        item.status = "draft"
        item.updated_at = datetime.utcnow()

        suggestion.proposed_text = custom_text
        suggestion.diff_preview = self.generate_diff_preview(orig, custom_text)
        suggestion.status = "applied"
        suggestion.resolved_at = datetime.utcnow()

        db.commit()
        db.refresh(item)
        db.refresh(new_version)
        db.refresh(suggestion)

        return (
            suggestion,
            item,
            new_version,
            f"Applied custom correction and created version v{new_version_num}. Please re-run governance check to evaluate the revised content."
        )


suggestion_service = SuggestionService()
