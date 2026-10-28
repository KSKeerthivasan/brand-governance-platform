import os
import re
from datetime import datetime
from typing import List, Dict, Any, Optional, Set, Tuple
from sqlalchemy.orm import Session
from app.models.knowledge import KnowledgeRule, KnowledgeFact
from app.models.content import ContentVersion, GovernanceRun, GovernanceFinding
from app.services.image_governance import image_governance
from app.services.ocr_service import ocr_service, OCRResult
from app.services.pdf_service import pdf_service, PDFValidationError, PDFRenderError
from app.services.storage import storage_service

# Canonical Freshsip products mapping (SKU -> aliases)
CANONICAL_PRODUCTS: Dict[str, List[str]] = {
    "FS-PROD-001": [
        "valencia orange cold-pressed juice", "valencia orange juice", "valencia orange", "fs-prod-001"
    ],
    "FS-PROD-002": [
        "pink guava pomegranate nectar", "pink guava nectar", "pink guava", "fs-prod-002"
    ],
    "FS-PROD-003": [
        "garden tomato celery press", "garden tomato press", "tomato celery", "fs-prod-003"
    ],
    "FS-PROD-004": [
        "spiced carrot beetroot press", "spiced carrot press", "carrot beetroot", "fs-prod-004"
    ],
    "FS-PROD-005": [
        "green orchard cucumber spinach blend", "green orchard blend", "cucumber spinach", "green orchard", "fs-prod-005"
    ],
    "FS-PROD-006": [
        "citrus carrot ginger blend", "citrus carrot blend", "carrot ginger", "fs-prod-006"
    ],
}

# Common high-risk marketing and unverified health claims requiring supporting evidence
RISKY_HEALTH_PATTERNS = [
    (r"\b(?:cures?|prevents?|treats?|heals?)\s+(?:cancer|diabetes|illness|disease|infection|depression|anxiety)\b", "Medical Treatment Claim", "Under brand governance, consumer marketing must not claim to diagnose, cure, mitigate, treat, or prevent diseases without approved regulatory clearance."),
    (r"\b(?:guaranteed|instant|rapid|effortless)\s+(?:weight loss|fat burning|slimming|detox)\b", "Guaranteed Weight Loss / Detox Claim", "Promotional claims guaranteeing weight loss or detoxification require approved clinical substantiation."),
    (r"\b(?:100%|completely)\s+(?:chemical[ -]free|toxin[ -]free|side[ -]effect[ -]free)\b", "Absolute Chemical-Free Claim", "Scientific claims of being '100% chemical-free' are scientifically inaccurate and misleading under brand guidelines."),
    (r"\b(?:doctor|pediatrician|cardiologist)\s+(?:recommended|approved|prescribed)\b", "Professional Endorsement Claim", "Claims of medical professional endorsements require verified, approved documentation on file."),
]

class GovernanceEngine:
    """
    Deterministic context-aware governance engine with local poster OCR for Inkloom AI.
    Evaluates marketing copy and creative assets against approved brand guidelines,
    product catalogues, and verified claims according to documented scope and conditions.
    """

    def normalize_channel(self, channel: Optional[str]) -> str:
        """Normalize free-form channel strings to canonical scope categories."""
        if not channel:
            return "all_channels"
        c = channel.strip().lower()
        if any(k in c for k in ["social", "instagram", "tweet", "facebook", "linkedin"]):
            return "social_posts"
        if any(k in c for k in ["pack", "label", "bottle"]):
            return "packaging"
        if any(k in c for k in ["product description", "pdp", "description"]):
            return "product_descriptions"
        if any(k in c for k in ["ecommerce", "amazon", "blinkit", "flipkart", "listing"]):
            return "ecommerce_listings"
        if any(k in c for k in ["promo", "newsletter", "email"]):
            return "promotional_content"
        if any(k in c for k in ["educational", "blog", "article"]):
            return "educational_content"
        if any(k in c for k in ["banner", "regional", "digital ad"]):
            return "regional_digital_ads"
        return c

    def is_rule_in_channel_scope(self, rule_scope: Optional[str], content_channel: Optional[str]) -> bool:
        """Check if a rule applies to the specified marketing channel."""
        if not rule_scope or rule_scope.strip().lower() == "all_channels":
            return True
        norm_chan = self.normalize_channel(content_channel)
        if norm_chan == "all_channels":
            return True
        allowed_scopes = [s.strip().lower() for s in rule_scope.split(",") if s.strip()]
        if "all_channels" in allowed_scopes:
            return True
        return norm_chan in allowed_scopes

    def detect_product_context(
        self,
        text: str,
        title: str,
        explicit_product_id: Optional[str] = None
    ) -> List[str]:
        """Identify which canonical Freshsip SKUs are mentioned or targeted in the copy."""
        if explicit_product_id:
            pid = explicit_product_id.strip().upper()
            if pid in CANONICAL_PRODUCTS:
                return [pid]
            # Check by name matching if a name was passed instead of SKU
            for sku, aliases in CANONICAL_PRODUCTS.items():
                if any(alias in pid.lower() for alias in aliases):
                    return [sku]
            return [pid]

        combined = f"{title} {text}".lower()
        matched_skus: List[str] = []
        for sku, aliases in CANONICAL_PRODUCTS.items():
            for alias in aliases:
                if re.search(rf"\b{re.escape(alias)}\b", combined):
                    if sku not in matched_skus:
                        matched_skus.append(sku)
                    break
        return matched_skus

    def is_negated_or_quoted(self, text: str, start: int, end: int) -> bool:
        """
        Check if a matched prohibited phrase appears in a negated, qualifying,
        or editorial quotation context (e.g. 'We do not claim our juice is a miracle').
        """
        clause_start = max(0, start - 200)
        last_punct = max(text.rfind(".", clause_start, start),
                         text.rfind("!", clause_start, start),
                         text.rfind("?", clause_start, start),
                         text.rfind(";", clause_start, start))
        if last_punct != -1:
            clause_start = last_punct + 1

        preceding = text[clause_start:start].lower()
        following = text[end:min(len(text), end + 80)].lower()

        # Negation keywords preceding match
        negation_tokens = [
            "not", "never", "no", "without", "isn't", "is not", "does not", "doesn't",
            "cannot", "can't", "neither", "nor", "avoid", "avoids", "refrain from",
            "do not claim", "don't claim", "never claim", "no claim"
        ]
        for token in negation_tokens:
            if re.search(rf"\b{re.escape(token)}\b", preceding):
                return True

        # Quotation / editorial debunking check
        prec_strip = preceding.rstrip()
        foll_strip = following.lstrip()
        if (prec_strip.endswith('"') or prec_strip.endswith("'")) and (foll_strip.startswith('"') or foll_strip.startswith("'")):
            combined_context = preceding + following
            if any(term in combined_context for term in ["myth", "avoid", "false", "misleading", "ask", "question", "claim"]):
                return True

        return False

    def _find_poster_region(self, ocr_result: Optional[OCRResult], pattern: str) -> Optional[Tuple[str, List[List[float]]]]:
        """Locate the bounding box coordinates and line text for a pattern matched in poster text."""
        if not ocr_result or not ocr_result.regions:
            return None
        regex = re.compile(rf"\b{re.escape(pattern)}\b", re.IGNORECASE)
        for r in ocr_result.regions:
            if regex.search(r.text):
                return (r.text, r.bbox)
        # Substring fallback
        for r in ocr_result.regions:
            if pattern.lower() in r.text.lower():
                return (r.text, r.bbox)
        return None

    def evaluate_content_version(
        self,
        db: Session,
        content_version: ContentVersion,
        executed_by_user_id: Optional[str] = None,
        product_id: Optional[str] = None
    ) -> GovernanceRun:
        body_text = content_version.body_text or ""
        content_item = content_version.content_item
        channel = content_item.channel if content_item else "Social Media"
        title = content_item.title if content_item else ""
        brand_id = content_item.brand_id if content_item else None
        org_id = content_item.organization_id if content_item else None
        now = datetime.utcnow()

        findings: List[GovernanceFinding] = []

        # Check if attached asset is a multi-page PDF creative
        is_pdf = False
        if content_version.poster_file_path:
            p_lower = content_version.poster_file_path.lower()
            if p_lower.endswith(".pdf"):
                is_pdf = True
            elif storage_service.check_exists(content_version.poster_file_path):
                try:
                    local_p = storage_service.get_file_path_for_processing(content_version.poster_file_path)
                    with open(local_p, "rb") as f:
                        if f.read(1024).startswith(b"%PDF-"):
                            is_pdf = True
                except Exception:
                    pass

        if is_pdf:
            return self._execute_pdf_governance_run(
                db=db,
                content_version=content_version,
                channel=channel,
                title=title,
                body_text=body_text,
                brand_id=brand_id,
                org_id=org_id,
                executed_by_user_id=executed_by_user_id,
                product_id=product_id
            )

        # ==========================================
        # STEP 0: LOCAL OCR POSTER TEXT EXTRACTION
        # ==========================================
        poster_text = ""
        ocr_result: Optional[OCRResult] = None
        if content_version.poster_file_path:
            local_poster_path = storage_service.get_file_path_for_processing(content_version.poster_file_path)
            ocr_result = ocr_service.extract_text_from_image(local_poster_path)
            if ocr_result.status in ("success", "low_confidence"):
                poster_text = ocr_result.extracted_text

            if ocr_result.status == "failed":
                findings.append(GovernanceFinding(
                    category="image_guideline_issue",
                    severity="warning",
                    title="OCR Processing Failed: Poster Text Unverified",
                    explanation=f"Local OCR could not process poster image: {ocr_result.error_message}. Visual copy could not be automatically evaluated and requires human review.",
                    text_excerpt=None,
                    matched_rule_id=None,
                    matched_fact_id=None,
                    source_citation="System OCR Gate",
                    recommended_action="Hold draft for human review. Verify poster text manually.",
                    status="unresolved"
                ))
            elif ocr_result.status == "unsupported_format":
                findings.append(GovernanceFinding(
                    category="image_guideline_issue",
                    severity="warning",
                    title="Unsupported Image Format: Poster Text Unverified",
                    explanation=f"{ocr_result.error_message}. Raster formats (.png, .jpg, .webp) are required for automated text governance.",
                    text_excerpt=None,
                    matched_rule_id=None,
                    matched_fact_id=None,
                    source_citation="Brand Asset Standard",
                    recommended_action="Convert creative asset to high-resolution PNG or JPEG.",
                    status="unresolved"
                ))
            elif ocr_result.status == "low_confidence":
                findings.append(GovernanceFinding(
                    category="missing_evidence",
                    severity="warning",
                    title="Uncertain OCR Text Recognition: Human Review Recommended",
                    explanation=f"Poster text recognition confidence ({ocr_result.mean_confidence:.1%}) fell below verification threshold (60%). Preview: '{ocr_result.extracted_text[:120]}...'. Requires manual inspection.",
                    text_excerpt=ocr_result.extracted_text[:150] if ocr_result.extracted_text else None,
                    matched_rule_id=None,
                    matched_fact_id=None,
                    source_citation="System OCR Gate",
                    recommended_action="Review poster text manually before publishing.",
                    status="unresolved"
                ))

        # Step 1: Detect product context across caption + poster
        combined_source_text = f"{title} {body_text} {poster_text}"
        detected_products = self.detect_product_context(combined_source_text, title, product_id)
        is_corporate_content = len(detected_products) == 0

        # Step 2: Query active approved rules
        approved_rules = db.query(KnowledgeRule).filter(
            KnowledgeRule.organization_id == org_id,
            KnowledgeRule.status == "approved"
        ).all()

        # Step 3: Query product facts (approved)
        approved_facts = db.query(KnowledgeFact).filter(
            KnowledgeFact.organization_id == org_id,
            KnowledgeFact.status == "approved"
        ).all()

        # Step 4: Query unapproved facts (pending, expired, rejected)
        unapproved_facts = db.query(KnowledgeFact).filter(
            KnowledgeFact.organization_id == org_id,
            KnowledgeFact.status.in_(["pending_review", "rejected", "expired"])
        ).all()

        rules_evaluated_count = 0
        facts_evaluated_count = 0

        # Combined text for checking disclosures
        combined_content = f"{body_text}\n{poster_text}" if poster_text else body_text

        # ==========================================
        # 1. PROHIBITED CLAIMS AND TERMINOLOGY CHECKS
        # ==========================================
        for rule in approved_rules:
            if rule.rule_type not in ("prohibition", "restriction", "prohibited_word") and rule.rule_code != "FR-RULE-005":
                continue

            # Scope Check: Is rule in scope for this channel?
            if not self.is_rule_in_channel_scope(rule.scope, channel):
                continue

            rules_evaluated_count += 1
            sub_patterns = [p.strip() for p in rule.pattern.split(",") if p.strip()] if "," in rule.pattern else [rule.pattern.strip()]

            for pat in sub_patterns:
                pattern_escaped = re.escape(pat)
                regex = re.compile(rf"\b{pattern_escaped}\b", re.IGNORECASE)

                match_caption = regex.search(body_text) if body_text else None
                match_poster = regex.search(poster_text) if poster_text else None

                if not match_caption and not match_poster:
                    continue

                rule_code_prefix = f"[{rule.rule_code}] " if rule.rule_code else ""

                caption_neg = self.is_negated_or_quoted(body_text, match_caption.start(), match_caption.end()) if match_caption else False
                poster_neg = self.is_negated_or_quoted(poster_text, match_poster.start(), match_poster.end()) if match_poster else False

                # Case 1: Match in BOTH caption and poster (Deduplicated finding)
                if match_caption and match_poster:
                    if caption_neg and poster_neg:
                        findings.append(GovernanceFinding(
                            category="prohibited_wording",
                            severity="info",
                            title=f"Contextual Mention Noted (Negated): '{pat}'",
                            explanation=f"Phrase '{pat}' appeared in a qualifying or negated context in both caption and poster. Rule: {rule.title}.",
                            text_excerpt=self._extract_excerpt(body_text, match_caption.start(), match_caption.end()),
                            matched_rule_id=rule.id,
                            source_citation=rule.source_citation or "freshsip_brand_guidelines.pdf",
                            recommended_action="No action required if used strictly to clarify or negate unverified claims.",
                            status="passed_check"
                        ))
                    else:
                        region_info = self._find_poster_region(ocr_result, pat)
                        bbox_str = f" [Poster Region bbox: {region_info[1]}]" if region_info else ""
                        c_excerpt = self._extract_excerpt(body_text, match_caption.start(), match_caption.end())
                        p_text = region_info[0] if region_info else pat
                        findings.append(GovernanceFinding(
                            category="prohibited_wording",
                            severity=rule.severity,
                            title=f"{rule_code_prefix}Prohibited Term Detected: '{pat}' (Caption & Poster)",
                            explanation=f"Content contains prohibited language '{pat}' in both caption copy and attached poster image. Rule: {rule.title}. Reason: {rule.explanation}",
                            text_excerpt=f"Caption: '{c_excerpt}' | Poster: '{p_text}'{bbox_str}",
                            matched_rule_id=rule.id,
                            source_citation=rule.source_citation or "freshsip_brand_guidelines.pdf",
                            recommended_action=f"Remove or rephrase '{pat}' from caption and poster artwork. Action: {rule.enforcement_action or 'block'}.",
                            status="unresolved"
                        ))

                # Case 2: Match in caption ONLY
                elif match_caption:
                    if caption_neg:
                        findings.append(GovernanceFinding(
                            category="prohibited_wording",
                            severity="info",
                            title=f"Contextual Mention Noted (Negated): '{pat}'",
                            explanation=f"Phrase '{pat}' appeared in a qualifying or negated context in caption copy. Rule: {rule.title}. Reason: {rule.explanation}",
                            text_excerpt=self._extract_excerpt(body_text, match_caption.start(), match_caption.end()),
                            matched_rule_id=rule.id,
                            source_citation=rule.source_citation or "freshsip_brand_guidelines.pdf",
                            recommended_action="No action required if used strictly to clarify or negate unverified claims.",
                            status="passed_check"
                        ))
                    else:
                        findings.append(GovernanceFinding(
                            category="prohibited_wording",
                            severity=rule.severity,
                            title=f"{rule_code_prefix}Prohibited Term in Caption: '{pat}'",
                            explanation=f"Caption copy contains prohibited language '{pat}'. Rule: {rule.title}. Context condition: {rule.context_condition or 'All channels'}. Reason: {rule.explanation}",
                            text_excerpt=self._extract_excerpt(body_text, match_caption.start(), match_caption.end()),
                            matched_rule_id=rule.id,
                            source_citation=rule.source_citation or "freshsip_brand_guidelines.pdf",
                            recommended_action=f"Remove or rephrase '{pat}' from caption copy. Action: {rule.enforcement_action or 'block'}.",
                            status="unresolved"
                        ))

                # Case 3: Match in poster image ONLY
                elif match_poster:
                    if poster_neg:
                        findings.append(GovernanceFinding(
                            category="prohibited_wording",
                            severity="info",
                            title=f"Contextual Mention Noted (Negated): '{pat}'",
                            explanation=f"Phrase '{pat}' appeared in a qualifying or negated context in attached poster image. Rule: {rule.title}.",
                            text_excerpt=pat,
                            matched_rule_id=rule.id,
                            source_citation=rule.source_citation or "freshsip_brand_guidelines.pdf",
                            recommended_action="No action required if used strictly to clarify or negate unverified claims.",
                            status="passed_check"
                        ))
                    else:
                        region_info = self._find_poster_region(ocr_result, pat)
                        bbox_str = f" [Poster Region bbox: {region_info[1]}]" if region_info else ""
                        p_text = region_info[0] if region_info else pat
                        findings.append(GovernanceFinding(
                            category="prohibited_wording",
                            severity=rule.severity,
                            title=f"{rule_code_prefix}Prohibited Term in Poster: '{pat}'",
                            explanation=f"Attached poster image contains prohibited language '{pat}'. Rule: {rule.title}. Context condition: {rule.context_condition or 'All channels'}. Reason: {rule.explanation}",
                            text_excerpt=f"Poster: '{p_text}'{bbox_str}",
                            matched_rule_id=rule.id,
                            source_citation=rule.source_citation or "freshsip_brand_guidelines.pdf",
                            recommended_action=f"Remove or replace poster graphic containing '{pat}'. Action: {rule.enforcement_action or 'block'}.",
                            status="unresolved"
                        ))

        # ==========================================
        # 2. REQUIRED WORDING & MANDATORY DISCLOSURES
        # ==========================================
        for rule in approved_rules:
            if rule.rule_type not in ("required_term", "requirement"):
                continue

            # Scope Check: Channel & format applicability
            if not self.is_rule_in_channel_scope(rule.scope, channel):
                continue

            rules_evaluated_count += 1

            # Case A: Allergen & Storage Disclosure Alignment (FR-RULE-014)
            if rule.rule_code == "FR-RULE-014":
                if is_corporate_content:
                    continue

                if "FS-PROD-003" in detected_products:
                    # Garden Tomato Celery Press requires Celery allergen disclosure in copy OR poster
                    if not re.search(r"\b(?:contains\s+celery|allergen[:\s]+celery)\b", combined_content, re.IGNORECASE):
                        findings.append(GovernanceFinding(
                            category="mandatory_wording_missing",
                            severity="critical",
                            title="[FR-RULE-014] Missing Mandatory Allergen Disclosure: Celery",
                            explanation="Garden Tomato Celery Press (FS-PROD-003) must disclose 'Contains Celery (14%)' on product descriptions, packaging, and listings (checked in caption and poster).",
                            text_excerpt=None,
                            matched_rule_id=rule.id,
                            source_citation=rule.source_citation or "freshsip_brand_guidelines.pdf, Section E, p. 5",
                            recommended_action="Add mandatory allergen statement: 'Contains Celery (14%)' in copy or poster artwork.",
                            status="unresolved"
                        ))

                if "FS-PROD-004" in detected_products:
                    # Spiced Carrot Beetroot Press: allergen status is not_provided
                    if re.search(r"\b(?:allergen[ -]free|100%\s+allergen[ -]free|suitable for all allergy)\b", combined_content, re.IGNORECASE):
                        findings.append(GovernanceFinding(
                            category="missing_evidence",
                            severity="critical",
                            title="[FR-RULE-014] Prohibited Allergen Claim: Allergen Status Not Provided (FS-PROD-004)",
                            explanation="Spiced Carrot Beetroot Press (FS-PROD-004) has allergen status marked 'not_provided'. Claiming allergen-free in caption or poster violates brand guidelines.",
                            text_excerpt=None,
                            matched_rule_id=rule.id,
                            source_citation=rule.source_citation or "freshsip_brand_guidelines.pdf, Section E, p. 5",
                            recommended_action="Remove allergen-free claim or upload certified allergen cross-contact test results.",
                            status="unresolved"
                        ))
                continue

            # Case B: Accurate Sugar Terminology Requirement (FR-RULE-005 / FR-RULE-006)
            if rule.rule_code in ("FR-RULE-005", "FR-RULE-006") or "sugar" in rule.title.lower():
                if re.search(r"\bsugar\b", combined_content, re.IGNORECASE):
                    # If 'no added sugar' is present in caption OR poster, it is satisfied!
                    if not re.search(r"\bno added sugar\b", combined_content, re.IGNORECASE):
                        findings.append(GovernanceFinding(
                            category="mandatory_wording_missing",
                            severity=rule.severity,
                            title=f"[{rule.rule_code or 'REQUIREMENT'}] Missing Required Term: 'No Added Sugar'",
                            explanation="When describing sugar content in fruit/vegetable juices, approved policy requires stating 'No Added Sugar' rather than 'Zero Sugar' (checked in caption and poster).",
                            text_excerpt=None,
                            matched_rule_id=rule.id,
                            source_citation=rule.source_citation or "freshsip_brand_guidelines.pdf, Section C, p. 3",
                            recommended_action="Use 'No Added Sugar' and acknowledge naturally occurring fruit sugars.",
                            status="unresolved"
                        ))
                continue

            # Case C: Tagline Requirement (FR-RULE-007)
            if rule.rule_code == "FR-RULE-007" or "tagline" in rule.title.lower():
                norm_chan = self.normalize_channel(channel)
                if norm_chan in ("promotional_content", "packaging"):
                    pattern_escaped = re.escape(rule.pattern.strip())
                    # Check in caption OR poster
                    if not re.search(rf"\b{pattern_escaped}\b", combined_content, re.IGNORECASE):
                        findings.append(GovernanceFinding(
                            category="mandatory_wording_missing",
                            severity=rule.severity,
                            title=f"[{rule.rule_code or 'REQUIREMENT'}] Missing Brand Tagline: '{rule.pattern}'",
                            explanation=f"Required brand tagline '{rule.pattern}' was not found in campaign copy or poster artwork.",
                            text_excerpt=None,
                            matched_rule_id=rule.id,
                            source_citation=rule.source_citation or "freshsip_brand_guidelines.pdf, Section 2.1, p. 4",
                            recommended_action=f"Include brand tagline '{rule.pattern}' in copy or poster.",
                            status="unresolved"
                        ))
                continue

            # Case D: General required terms
            if rule.rule_type == "required_term":
                pattern_escaped = re.escape(rule.pattern.strip())
                if not re.search(rf"\b{pattern_escaped}\b", combined_content, re.IGNORECASE):
                    findings.append(GovernanceFinding(
                        category="mandatory_wording_missing",
                        severity=rule.severity,
                        title=f"Missing Mandatory Term: '{rule.pattern}'",
                        explanation=f"Required wording '{rule.pattern}' was not found in copy or poster artwork. {rule.explanation}",
                        text_excerpt=None,
                        matched_rule_id=rule.id,
                        source_citation=rule.source_citation or "freshsip_brand_guidelines.pdf",
                        recommended_action=f"Include the required wording '{rule.pattern}' in the text or poster.",
                        status="unresolved"
                    ))

        # ==========================================
        # 3. PRODUCT FACTS & SPECIFICATION VALIDATION
        # ==========================================
        if is_corporate_content:
            unattributed_claim = re.search(r"\b(\d+\s*calories|\d+\s*kcal|mrp\s*₹\d+|price\s*₹\d+)\b", combined_content, re.IGNORECASE)
            if unattributed_claim:
                findings.append(GovernanceFinding(
                    category="missing_evidence",
                    severity="warning",
                    title="Missing Product Context: Unattributed Specification Claim",
                    explanation=f"Content mentions '{unattributed_claim.group(0)}' without specifying which Freshsip SKU is referenced. Product fact verification requires identifying the product.",
                    text_excerpt=unattributed_claim.group(0),
                    matched_rule_id=None,
                    matched_fact_id=None,
                    source_citation="freshsip_products.csv",
                    recommended_action="Specify the exact product name (e.g., 'Valencia Orange Cold-Pressed Juice') or supply product context.",
                    status="unresolved"
                ))
        else:
            flagged_mismatches: Set[Tuple[str, str, str]] = set()

            for target_sku in detected_products:
                target_facts = [f for f in approved_facts if f.product_id == target_sku or (f.product_name and target_sku.lower() in f.product_name.lower())]

                for fact in target_facts:
                    facts_evaluated_count += 1

                    # Check Sugar Content Fact
                    if fact.fact_key.lower() == "sugar" or "sugar" in fact.fact_key.lower():
                        if "no added sugar" in fact.fact_value.lower() or "0g" in fact.fact_value.lower():
                            conflict_c = re.search(r"\b(\d+\s*g(?:rams?)?\s+(?:of\s+)?(?:added\s+)?sugar|sweetened with (?:sugar|corn syrup)|high sugar)\b", body_text, re.IGNORECASE) if body_text else None
                            conflict_p = re.search(r"\b(\d+\s*g(?:rams?)?\s+(?:of\s+)?(?:added\s+)?sugar|(?:100%\s*)?sugar[ -]free|zero\s*sugar|sweetened with (?:sugar|corn syrup)|high sugar)\b", poster_text, re.IGNORECASE) if poster_text else None

                            if conflict_c:
                                key = ("sugar", target_sku, conflict_c.group(1).lower())
                                if key not in flagged_mismatches:
                                    flagged_mismatches.add(key)
                                    findings.append(GovernanceFinding(
                                        category="product_fact_mismatch",
                                        severity="critical",
                                        title=f"Product Fact Mismatch in Caption: Sugar Content ({target_sku})",
                                        explanation=f"Caption states '{conflict_c.group(1)}', which contradicts approved specification: '{fact.fact_value}'.",
                                        text_excerpt=self._extract_excerpt(body_text, conflict_c.start(), conflict_c.end()),
                                        matched_fact_id=fact.id,
                                        source_citation=fact.source_citation or f"freshsip_products.csv ({target_sku})",
                                        recommended_action=f"Update caption copy to align with verified fact: '{fact.fact_value}'.",
                                        status="unresolved"
                                    ))
                            if conflict_p:
                                key = ("sugar_poster", target_sku, conflict_p.group(1).lower())
                                if key not in flagged_mismatches:
                                    flagged_mismatches.add(key)
                                    region_info = self._find_poster_region(ocr_result, conflict_p.group(1))
                                    bbox_str = f" [Poster Region bbox: {region_info[1]}]" if region_info else ""
                                    findings.append(GovernanceFinding(
                                        category="product_fact_mismatch",
                                        severity="critical",
                                        title=f"Product Fact Mismatch in Poster: Sugar Content ({target_sku})",
                                        explanation=f"Poster artwork states '{conflict_p.group(1)}', which contradicts approved specification: '{fact.fact_value}'.",
                                        text_excerpt=f"Poster: '{region_info[0] if region_info else conflict_p.group(1)}'{bbox_str}",
                                        matched_fact_id=fact.id,
                                        source_citation=fact.source_citation or f"freshsip_products.csv ({target_sku})",
                                        recommended_action=f"Correct poster artwork to match verified fact: '{fact.fact_value}'.",
                                        status="unresolved"
                                    ))

                    # Check Calorie / Energy Count Fact
                    if "calorie" in fact.fact_key.lower() or "energy" in fact.fact_key.lower():
                        cals_match = re.search(r"\b(\d{2,4})\s*(?:calories|kcal)\b", combined_content, re.IGNORECASE)
                        if cals_match:
                            mentioned_cals = cals_match.group(1)
                            if mentioned_cals not in fact.fact_value:
                                key = ("calories", target_sku, mentioned_cals)
                                if key not in flagged_mismatches:
                                    flagged_mismatches.add(key)
                                    findings.append(GovernanceFinding(
                                        category="product_fact_mismatch",
                                        severity="warning",
                                        title=f"Product Fact Mismatch: Calorie Count ({target_sku})",
                                        explanation=f"Content states '{mentioned_cals} calories', but approved specification states '{fact.fact_value}'.",
                                        text_excerpt=cals_match.group(0),
                                        matched_fact_id=fact.id,
                                        source_citation=fact.source_citation or f"freshsip_products.csv ({target_sku})",
                                        recommended_action=f"Verify calorie count against approved record: '{fact.fact_value}'.",
                                        status="unresolved"
                                    ))

                    # Check Pack Size / Price
                    if "price" in fact.fact_key.lower() or "mrp" in fact.fact_key.lower():
                        price_match_c = re.search(r"(?:\b(?:mrp|price|buy\s*for|inr|rs\.?)\s*)?[₹]\s*(\d{2,4})\b", body_text, re.IGNORECASE) if body_text else None
                        price_match_p = re.search(r"\b(?:buy\s*for|mrp|price|inr|rs\.?)[^\d\w\n\r]*[₹fF\s:.-]*(\d{2,4})\b", poster_text, re.IGNORECASE) if poster_text else None
                        if not price_match_p and poster_text:
                            price_match_p = re.search(r"[₹]\s*(\d{2,4})\b", poster_text)

                        # Extract approved price digits from fact value (e.g. '₹95 MRP (250 mL)' -> '95')
                        approved_price_digits = None
                        m_app = re.search(r"[₹]\s*(\d{2,4})\b", fact.fact_value)
                        if m_app:
                            approved_price_digits = m_app.group(1)
                        else:
                            m_num = re.search(r"\b(\d{2,4})\b", fact.fact_value.split("(")[0])
                            if m_num:
                                approved_price_digits = m_num.group(1)

                        if price_match_c and approved_price_digits:
                            mentioned_price = price_match_c.group(1)
                            if mentioned_price != approved_price_digits:
                                key = ("price_c", target_sku, mentioned_price)
                                if key not in flagged_mismatches:
                                    flagged_mismatches.add(key)
                                    findings.append(GovernanceFinding(
                                        category="product_fact_mismatch",
                                        severity="critical",
                                        title=f"Product Fact Mismatch in Caption: Price / MRP ({target_sku})",
                                        explanation=f"Caption states '₹{mentioned_price}', but approved catalogue MRP is '{fact.fact_value}'.",
                                        text_excerpt=self._extract_excerpt(body_text, price_match_c.start(), price_match_c.end()),
                                        matched_fact_id=fact.id,
                                        source_citation=fact.source_citation or f"freshsip_products.csv ({target_sku})",
                                        recommended_action=f"Correct price in caption to match approved catalogue MRP: '{fact.fact_value}'.",
                                        status="unresolved"
                                    ))

                        if price_match_p and approved_price_digits:
                            mentioned_price_p = price_match_p.group(1)
                            if mentioned_price_p != approved_price_digits:
                                key = ("price_p", target_sku, mentioned_price_p)
                                if key not in flagged_mismatches:
                                    flagged_mismatches.add(key)
                                    region_info = self._find_poster_region(ocr_result, mentioned_price_p) or self._find_poster_region(ocr_result, price_match_p.group(0))
                                    bbox_str = f" [Poster Region bbox: {region_info[1]}]" if region_info else ""
                                    findings.append(GovernanceFinding(
                                        category="product_fact_mismatch",
                                        severity="critical",
                                        title=f"Product Fact Mismatch in Poster: Price / MRP ({target_sku})",
                                        explanation=f"Poster states '{price_match_p.group(0)}', but approved catalogue MRP is '{fact.fact_value}'.",
                                        text_excerpt=f"Poster: '{region_info[0] if region_info else price_match_p.group(0)}'{bbox_str}",
                                        matched_fact_id=fact.id,
                                        source_citation=fact.source_citation or f"freshsip_products.csv ({target_sku})",
                                        recommended_action=f"Correct price on poster artwork to match approved catalogue MRP: '{fact.fact_value}'.",
                                        status="unresolved"
                                    ))

        # ==========================================
        # 4. APPROVED CLAIMS & LIFECYCLE GOVERNANCE
        # ==========================================
        for unapp_fact in unapproved_facts:
            if len(unapp_fact.fact_value) > 10:
                in_caption = unapp_fact.fact_value.lower() in body_text.lower()
                in_poster = poster_text and unapp_fact.fact_value.lower() in poster_text.lower()

                if in_caption or in_poster:
                    loc = "Caption & Poster" if in_caption and in_poster else ("Poster Image" if in_poster else "Caption")
                    excerpt = unapp_fact.fact_value

                    if in_poster:
                        reg = self._find_poster_region(ocr_result, unapp_fact.fact_value)
                        if reg:
                            excerpt = f"Poster: '{reg[0]}' [bbox: {reg[1]}]"

                    if unapp_fact.status == "pending_review":
                        findings.append(GovernanceFinding(
                            category="missing_evidence",
                            severity="critical",
                            title=f"[FR-RULE-018] Escalation Required: Pending Claim in {loc} ({unapp_fact.fact_key})",
                            explanation=f"Claim '{unapp_fact.fact_value}' detected in {loc} is currently PENDING REVIEW by the Knowledge Reviewer. Under FR-RULE-018, unapproved claims must be escalated to human governance.",
                            text_excerpt=excerpt,
                            matched_fact_id=unapp_fact.id,
                            source_citation=unapp_fact.source_citation or "freshsip_approved_claims.csv",
                            recommended_action="Hold draft for human review. Escalate to Brand Governance Manager.",
                            status="unresolved"
                        ))
                    elif unapp_fact.status == "expired":
                        findings.append(GovernanceFinding(
                            category="source_freshness_issue",
                            severity="critical",
                            title=f"[FR-RULE-018] Escalation Required: Expired Claim in {loc} ({unapp_fact.fact_key})",
                            explanation=f"Claim '{unapp_fact.fact_value}' detected in {loc} expired on {unapp_fact.valid_until.strftime('%Y-%m-%d') if unapp_fact.valid_until else 'prior date'}. Under FR-RULE-018, expired claims require revalidation.",
                            text_excerpt=excerpt,
                            matched_fact_id=unapp_fact.id,
                            source_citation=unapp_fact.source_citation or "freshsip_approved_claims.csv",
                            recommended_action="Revalidate claim with Brand Governance Lead before reuse.",
                            status="unresolved"
                        ))
                    elif unapp_fact.status == "rejected":
                        findings.append(GovernanceFinding(
                            category="claim_status_issue",
                            severity="critical",
                            title=f"Prohibited Claim: Rejected Claim in {loc} ({unapp_fact.fact_key})",
                            explanation=f"Claim '{unapp_fact.fact_value}' detected in {loc} was permanently REJECTED during brand governance review.",
                            text_excerpt=excerpt,
                            matched_fact_id=unapp_fact.id,
                            source_citation=unapp_fact.source_citation or "freshsip_approved_claims.csv",
                            recommended_action="Remove permanently rejected claim immediately.",
                            status="unresolved"
                        ))

        # ==========================================
        # 5. GENERAL RISKY HEALTH & MEDICAL CLAIMS (SAFETY NET)
        # ==========================================
        for pattern_re, title_desc, explanation_desc in RISKY_HEALTH_PATTERNS:
            match_c = re.search(pattern_re, body_text, re.IGNORECASE) if body_text else None
            match_p = re.search(pattern_re, poster_text, re.IGNORECASE) if poster_text else None

            if not match_c and not match_p:
                continue

            loc = "Caption & Poster" if match_c and match_p else ("Poster Image" if match_p else "Caption")
            match_sample = match_c or match_p

            is_neg = False
            if match_c:
                is_neg = self.is_negated_or_quoted(body_text, match_c.start(), match_c.end())
            elif match_p:
                is_neg = self.is_negated_or_quoted(poster_text, match_p.start(), match_p.end())

            if is_neg:
                findings.append(GovernanceFinding(
                    category="unsupported_claim",
                    severity="info",
                    title=f"Contextual Health Mention Noted: {title_desc}",
                    explanation=f"Medical claim phrase '{match_sample.group(0)}' detected in negated/editorial context in {loc}. Verified compliant under editorial exception.",
                    text_excerpt=match_sample.group(0),
                    matched_rule_id=None,
                    matched_fact_id=None,
                    source_citation="freshsip_brand_guidelines.pdf, Section D, p. 3",
                    recommended_action="Ensure copy continues to clearly negate medical claims.",
                    status="passed_check"
                ))
            else:
                region_info = self._find_poster_region(ocr_result, match_p.group(0)) if match_p else None
                bbox_str = f" [Poster Region bbox: {region_info[1]}]" if region_info else ""
                excerpt = f"Poster: '{region_info[0] if region_info else match_p.group(0)}'{bbox_str}" if match_p and not match_c else self._extract_excerpt(body_text, match_c.start(), match_c.end())

                findings.append(GovernanceFinding(
                    category="unsupported_claim",
                    severity="critical",
                    title=f"Unsupported Claim in {loc}: {title_desc}",
                    explanation=f"{explanation_desc} The phrase '{match_sample.group(0)}' was detected in {loc} without verified substantiation.",
                    text_excerpt=excerpt,
                    matched_rule_id=None,
                    matched_fact_id=None,
                    source_citation="SUPPORTING EVIDENCE NOT FOUND",
                    recommended_action="Remove unverified clinical/health claims or upload approved evidence to the Knowledge Library.",
                    status="unresolved"
                ))

        # ==========================================
        # 6. VISUAL GOVERNANCE CHECKS (If Poster Attached)
        # ==========================================
        if content_version.poster_file_path:
            local_poster_path = storage_service.get_file_path_for_processing(content_version.poster_file_path)
            visual_findings = image_governance.evaluate_poster_for_governance(
                file_path=local_poster_path,
                channel=channel,
                alt_text=content_version.poster_alt_text,
                org_id=org_id,
                db=db,
                brand_id=brand_id,
                ocr_result=ocr_result
            )
            findings.extend(visual_findings)

        # ==========================================
        # 7. DETERMINE OVERALL GOVERNANCE RUN STATUS
        # ==========================================
        has_blocker = any(
            f.severity in ("critical", "high") and getattr(f, "status", "unresolved") != "passed_check"
            for f in findings
        )
        has_warning = any(
            f.severity in ("warning", "medium", "low") and getattr(f, "status", "unresolved") != "passed_check"
            for f in findings
        )

        if has_blocker:
            overall_status = "failed"
        elif has_warning:
            overall_status = "warnings"
        else:
            overall_status = "passed"

        # Create GovernanceRun record
        gov_run = GovernanceRun(
            content_version_id=content_version.id,
            executed_by=executed_by_user_id,
            overall_status=overall_status,
            rules_evaluated_count=rules_evaluated_count,
            facts_evaluated_count=facts_evaluated_count,
            findings_count=len(findings)
        )
        db.add(gov_run)
        db.flush()

        # Associate findings with run
        for finding in findings:
            finding.governance_run_id = gov_run.id
            db.add(finding)

        db.commit()
        db.refresh(gov_run)
        return gov_run

    def _extract_excerpt(self, text: str, start: int, end: int, window: int = 40) -> str:
        s = max(0, start - window)
        e = min(len(text), end + window)
        prefix = "..." if s > 0 else ""
        suffix = "..." if e < len(text) else ""
        return f"{prefix}{text[s:e].strip()}{suffix}"

    def _execute_pdf_governance_run(
        self,
        db: Session,
        content_version: ContentVersion,
        channel: str,
        title: str,
        body_text: str,
        brand_id: Optional[str],
        org_id: Optional[str],
        executed_by_user_id: Optional[str],
        product_id: Optional[str]
    ) -> GovernanceRun:
        """
        Executes end-to-end governance checks on a multi-page PDF creative asset.
        Evaluates each page locally, maps findings to specific page numbers, checks
        document-level disclosures, and persists an immutable GovernanceRun.
        """
        approved_rules = db.query(KnowledgeRule).filter(
            KnowledgeRule.organization_id == org_id,
            KnowledgeRule.status == "approved"
        ).all()
        approved_facts = db.query(KnowledgeFact).filter(
            KnowledgeFact.organization_id == org_id,
            KnowledgeFact.status == "approved"
        ).all()
        unapproved_facts = db.query(KnowledgeFact).filter(
            KnowledgeFact.organization_id == org_id,
            KnowledgeFact.status.in_(["pending_review", "rejected", "expired"])
        ).all()

        pdf_findings, rules_count, facts_count = self._evaluate_pdf_creative_version(
            db=db,
            content_version=content_version,
            channel=channel,
            title=title,
            body_text=body_text,
            brand_id=brand_id,
            org_id=org_id,
            approved_rules=approved_rules,
            approved_facts=approved_facts,
            unapproved_facts=unapproved_facts,
            product_id=product_id
        )

        findings: List[GovernanceFinding] = list(pdf_findings)

        if body_text and body_text.strip():
            caption_findings = self._evaluate_caption_copy_for_pdf(
                body_text=body_text,
                channel=channel,
                approved_rules=approved_rules,
                approved_facts=approved_facts,
                unapproved_facts=unapproved_facts,
                title=title,
                product_id=product_id
            )
            findings.extend(caption_findings)

        has_blocker = any(
            f.severity in ("critical", "high") and getattr(f, "status", "unresolved") != "passed_check"
            for f in findings
        )
        has_warning = any(
            f.severity in ("warning", "medium", "low") and getattr(f, "status", "unresolved") != "passed_check"
            for f in findings
        )

        if has_blocker:
            overall_status = "failed"
        elif has_warning:
            overall_status = "warnings"
        else:
            overall_status = "passed"

        gov_run = GovernanceRun(
            content_version_id=content_version.id,
            executed_by=executed_by_user_id,
            overall_status=overall_status,
            rules_evaluated_count=rules_count,
            facts_evaluated_count=facts_count,
            findings_count=len(findings)
        )
        db.add(gov_run)
        db.flush()

        for finding in findings:
            finding.governance_run_id = gov_run.id
            db.add(finding)

        db.commit()
        db.refresh(gov_run)
        return gov_run

    def _evaluate_pdf_creative_version(
        self,
        db: Session,
        content_version: ContentVersion,
        channel: str,
        title: str,
        body_text: str,
        brand_id: Optional[str],
        org_id: Optional[str],
        approved_rules: List[KnowledgeRule],
        approved_facts: List[KnowledgeFact],
        unapproved_facts: List[KnowledgeFact],
        product_id: Optional[str]
    ) -> Tuple[List[GovernanceFinding], int, int]:
        all_findings: List[GovernanceFinding] = []
        rules_eval_count = 0
        facts_eval_count = 0

        pdf_ref = content_version.poster_file_path
        if not pdf_ref or not storage_service.check_exists(pdf_ref):
            return [GovernanceFinding(
                category="image_guideline_issue",
                severity="critical",
                title="PDF Creative Asset Missing on Disk",
                explanation=f"Attached creative file could not be located at '{pdf_ref}'.",
                text_excerpt=pdf_ref,
                matched_rule_id=None,
                matched_fact_id=None,
                source_citation="Storage Service",
                recommended_action="Re-upload the PDF creative asset.",
                status="unresolved",
                page_number=None
            )], 0, 0

        pdf_path = storage_service.get_file_path_for_processing(pdf_ref)

        # Validate PDF structure, signature, encryption, page limits
        try:
            meta = pdf_service.validate_pdf_file(pdf_path)
        except PDFValidationError as e:
            return [GovernanceFinding(
                category="image_guideline_issue",
                severity="critical",
                title="PDF Creative Asset Invalid: Governance Check Aborted",
                explanation=f"PDF validation failed: {str(e)}. Creative assets cannot be verified.",
                text_excerpt=pdf_path,
                matched_rule_id=None,
                matched_fact_id=None,
                source_citation="System PDF Parser Gate",
                recommended_action="Upload a valid, unencrypted, non-empty PDF within 30 pages and 25MB.",
                status="unresolved",
                page_number=None
            )], 0, 0

        cache_dir = os.path.join(os.path.dirname(pdf_path), f"pages_{content_version.id}")
        os.makedirs(cache_dir, exist_ok=True)

        all_page_texts: Dict[int, str] = {}
        doc_detected_products = self.detect_product_context(f"{title} {body_text}", title, product_id)

        # -------------------------------------------------------------
        # PER-PAGE EVALUATION LOOP
        # -------------------------------------------------------------
        for page_num in range(1, meta.page_count + 1):
            page_findings: List[GovernanceFinding] = []

            # 1. Render page raster
            try:
                page_raster = pdf_service.get_or_render_page_cache(pdf_path, page_num, cache_dir)
            except Exception as e:
                all_findings.append(GovernanceFinding(
                    category="image_guideline_issue",
                    severity="warning",
                    title=f"[Page {page_num}] PDF Page Rendering Failed: Page Unverified",
                    explanation=f"[Page {page_num}] Local rendering engine could not rasterize page {page_num}: {str(e)}. Page copy and visuals require human inspection.",
                    text_excerpt=None,
                    source_citation="System PDF Parser Gate",
                    recommended_action="Inspect PDF page manually.",
                    status="unresolved",
                    page_number=page_num
                ))
                continue

            # 2. Extract OCR and native PDF text
            page_ocr_res = ocr_service.extract_text_from_image(page_raster)
            native_text = pdf_service.extract_native_text(pdf_path, page_num)

            native_lines = [l.strip() for l in native_text.splitlines() if l.strip()]
            ocr_lines = [l.strip() for l in page_ocr_res.extracted_text.splitlines() if l.strip()]
            combined_lines = list(native_lines)
            for l in ocr_lines:
                if not any(l.lower() in nl.lower() or nl.lower() in l.lower() for nl in native_lines):
                    combined_lines.append(l)
            page_text = "\n".join(combined_lines)
            all_page_texts[page_num] = page_text

            # OCR confidence handling
            if page_ocr_res.status == "low_confidence":
                page_findings.append(GovernanceFinding(
                    category="missing_evidence",
                    severity="warning",
                    title=f"[Page {page_num}] Uncertain OCR Text Recognition: Human Review Recommended",
                    explanation=f"[Page {page_num}] Page text recognition confidence ({page_ocr_res.mean_confidence:.1%}) fell below verification threshold (60%). Preview: '{page_ocr_res.extracted_text[:120]}...'. Requires manual inspection.",
                    text_excerpt=page_ocr_res.extracted_text[:150] if page_ocr_res.extracted_text else None,
                    source_citation="System OCR Gate",
                    recommended_action="Review text on page manually before publishing.",
                    status="unresolved",
                    page_number=page_num
                ))
            elif page_ocr_res.status == "failed":
                page_findings.append(GovernanceFinding(
                    category="image_guideline_issue",
                    severity="warning",
                    title=f"[Page {page_num}] OCR Processing Failed: Page Copy Unverified",
                    explanation=f"[Page {page_num}] Local OCR could not process page image: {page_ocr_res.error_message}. Visual copy could not be automatically evaluated and requires human review.",
                    text_excerpt=None,
                    source_citation="System OCR Gate",
                    recommended_action="Hold draft for human review. Verify page text manually.",
                    status="unresolved",
                    page_number=page_num
                ))

            # Product scoping for this page
            page_detected_prods = self.detect_product_context(f"{title} {page_text}", title, product_id) or doc_detected_products

            # 3. Brand terminology & Prohibited wording on page
            for rule in approved_rules:
                if rule.rule_type not in ("prohibition", "restriction", "prohibited_word") and rule.rule_code != "FR-RULE-005":
                    continue
                if not self.is_rule_in_channel_scope(rule.scope, channel):
                    continue

                rules_eval_count += 1
                sub_patterns = [p.strip() for p in rule.pattern.split(",") if p.strip()] if "," in rule.pattern else [rule.pattern.strip()]
                for pat in sub_patterns:
                    pat_escaped = re.escape(pat)
                    regex = re.compile(rf"\b{pat_escaped}\b", re.IGNORECASE)
                    match_p = regex.search(page_text)
                    if not match_p:
                        continue

                    is_neg = self.is_negated_or_quoted(page_text, match_p.start(), match_p.end())
                    rule_code_prefix = f"[{rule.rule_code}] " if rule.rule_code else ""

                    if is_neg:
                        page_findings.append(GovernanceFinding(
                            category="prohibited_wording",
                            severity="info",
                            title=f"[Page {page_num}] Contextual Mention Noted (Negated): '{pat}'",
                            explanation=f"[Page {page_num}] Phrase '{pat}' appeared in a qualifying or negated context. Rule: {rule.title}.",
                            text_excerpt=f"[Page {page_num}] {pat}",
                            matched_rule_id=rule.id,
                            source_citation=rule.source_citation or "freshsip_brand_guidelines.pdf",
                            recommended_action="No action required if used strictly to clarify or negate unverified claims.",
                            status="passed_check",
                            page_number=page_num
                        ))
                    else:
                        region_info = self._find_poster_region(page_ocr_res, pat)
                        bbox_str = f" [Bbox: {region_info[1]}]" if region_info else ""
                        p_text = region_info[0] if region_info else pat
                        page_findings.append(GovernanceFinding(
                            category="prohibited_wording",
                            severity=rule.severity,
                            title=f"[Page {page_num}] {rule_code_prefix}Prohibited Term Detected: '{pat}'",
                            explanation=f"[Page {page_num}] Content on page contains prohibited language '{pat}'. Rule: {rule.title}. Reason: {rule.explanation}",
                            text_excerpt=f"[Page {page_num}] '{p_text}'{bbox_str}",
                            matched_rule_id=rule.id,
                            source_citation=rule.source_citation or "freshsip_brand_guidelines.pdf",
                            recommended_action=f"Remove or replace copy containing '{pat}' on Page {page_num}. Action: {rule.enforcement_action or 'block'}.",
                            status="unresolved",
                            page_number=page_num
                        ))

            # 4. Product facts on page
            for target_sku in page_detected_prods:
                facts_for_sku = [f for f in approved_facts if f.product_id == target_sku]
                for fact in facts_for_sku:
                    facts_eval_count += 1
                    if fact.fact_key.lower() == "sugar" or "sugar" in fact.fact_key.lower():
                        if "no added sugar" in fact.fact_value.lower() or "0g" in fact.fact_value.lower():
                            conflict_p = re.search(r"\b(\d+\s*g(?:rams?)?\s+(?:of\s+)?(?:added\s+)?sugar|(?:100%\s*)?sugar[ -]free|zero\s*sugar|sweetened with (?:sugar|corn syrup)|high sugar)\b", page_text, re.IGNORECASE)
                            if conflict_p:
                                reg = self._find_poster_region(page_ocr_res, conflict_p.group(1))
                                bbox_str = f" [Bbox: {reg[1]}]" if reg else ""
                                page_findings.append(GovernanceFinding(
                                    category="product_fact_mismatch",
                                    severity="critical",
                                    title=f"[Page {page_num}] Product Fact Mismatch: Sugar Content ({target_sku})",
                                    explanation=f"[Page {page_num}] Page states '{conflict_p.group(1)}', which contradicts approved specification: '{fact.fact_value}'.",
                                    text_excerpt=f"[Page {page_num}] '{reg[0] if reg else conflict_p.group(1)}'{bbox_str}",
                                    matched_fact_id=fact.id,
                                    source_citation=fact.source_citation or f"freshsip_products.csv ({target_sku})",
                                    recommended_action=f"Correct copy on Page {page_num} to match verified fact: '{fact.fact_value}'.",
                                    status="unresolved",
                                    page_number=page_num
                                ))
                    if "calorie" in fact.fact_key.lower() or "energy" in fact.fact_key.lower():
                        cals_match = re.search(r"\b(\d{2,4})\s*(?:calories|kcal)\b", page_text, re.IGNORECASE)
                        if cals_match:
                            mentioned_cals = cals_match.group(1)
                            if mentioned_cals not in fact.fact_value:
                                page_findings.append(GovernanceFinding(
                                    category="product_fact_mismatch",
                                    severity="warning",
                                    title=f"[Page {page_num}] Product Fact Mismatch: Calorie Count ({target_sku})",
                                    explanation=f"[Page {page_num}] Page states '{mentioned_cals} calories', but approved specification states '{fact.fact_value}'.",
                                    text_excerpt=f"[Page {page_num}] {cals_match.group(0)}",
                                    matched_fact_id=fact.id,
                                    source_citation=fact.source_citation or f"freshsip_products.csv ({target_sku})",
                                    recommended_action=f"Verify calorie count on Page {page_num} against approved record: '{fact.fact_value}'.",
                                    status="unresolved",
                                    page_number=page_num
                                ))
                    if "price" in fact.fact_key.lower() or "mrp" in fact.fact_key.lower():
                        price_match_p = re.search(r"\b(?:buy\s*for|mrp|price|inr|rs\.?)[^\d\w\n\r]*[₹fF\s:.-]*(\d{2,4})\b", page_text, re.IGNORECASE)
                        if not price_match_p:
                            price_match_p = re.search(r"[₹]\s*(\d{2,4})\b", page_text)
                        m_app_p = re.search(r"[₹]\s*(\d{2,4})\b", fact.fact_value)
                        app_price_p = m_app_p.group(1) if m_app_p else None
                        if not app_price_p:
                            m_num_p = re.search(r"\b(\d{2,4})\b", fact.fact_value.split("(")[0])
                            if m_num_p:
                                app_price_p = m_num_p.group(1)

                        if price_match_p and app_price_p:
                            mentioned_price_p = price_match_p.group(1)
                            if mentioned_price_p != app_price_p:
                                reg = self._find_poster_region(page_ocr_res, mentioned_price_p) or self._find_poster_region(page_ocr_res, price_match_p.group(0))
                                bbox_str = f" [Bbox: {reg[1]}]" if reg else ""
                                page_findings.append(GovernanceFinding(
                                    category="product_fact_mismatch",
                                    severity="critical",
                                    title=f"[Page {page_num}] Product Fact Mismatch: Price / MRP ({target_sku})",
                                    explanation=f"[Page {page_num}] Page states '{price_match_p.group(0)}', but approved catalogue MRP is '{fact.fact_value}'.",
                                    text_excerpt=f"[Page {page_num}] '{reg[0] if reg else price_match_p.group(0)}'{bbox_str}",
                                    matched_fact_id=fact.id,
                                    source_citation=fact.source_citation or f"freshsip_products.csv ({target_sku})",
                                    recommended_action=f"Correct price on Page {page_num} to match approved catalogue MRP: '{fact.fact_value}'.",
                                    status="unresolved",
                                    page_number=page_num
                                ))

            # 5. Unapproved facts & claims on page
            for unapp_fact in unapproved_facts:
                if unapp_fact.fact_value and len(unapp_fact.fact_value) > 10:
                    if unapp_fact.fact_value.lower() in page_text.lower():
                        reg = self._find_poster_region(page_ocr_res, unapp_fact.fact_value)
                        bbox_str = f" [Bbox: {reg[1]}]" if reg else ""
                        excerpt = f"[Page {page_num}] '{reg[0] if reg else unapp_fact.fact_value}'{bbox_str}"
                        if unapp_fact.status == "pending_review":
                            page_findings.append(GovernanceFinding(
                                category="missing_evidence",
                                severity="critical",
                                title=f"[Page {page_num}] [FR-RULE-018] Escalation Required: Pending Claim ({unapp_fact.fact_key})",
                                explanation=f"[Page {page_num}] Claim '{unapp_fact.fact_value}' detected on Page {page_num} is currently PENDING REVIEW by the Knowledge Reviewer. Under FR-RULE-018, unapproved claims must be escalated to human governance.",
                                text_excerpt=excerpt,
                                matched_fact_id=unapp_fact.id,
                                source_citation=unapp_fact.source_citation or "freshsip_approved_claims.csv",
                                recommended_action="Hold draft for human review. Escalate to Brand Governance Manager.",
                                status="unresolved",
                                page_number=page_num
                            ))
                        elif unapp_fact.status == "expired":
                            page_findings.append(GovernanceFinding(
                                category="source_freshness_issue",
                                severity="critical",
                                title=f"[Page {page_num}] [FR-RULE-018] Escalation Required: Expired Claim ({unapp_fact.fact_key})",
                                explanation=f"[Page {page_num}] Claim '{unapp_fact.fact_value}' detected on Page {page_num} expired on {unapp_fact.valid_until.strftime('%Y-%m-%d') if unapp_fact.valid_until else 'prior date'}. Under FR-RULE-018, expired claims require revalidation.",
                                text_excerpt=excerpt,
                                matched_fact_id=unapp_fact.id,
                                source_citation=unapp_fact.source_citation or "freshsip_approved_claims.csv",
                                recommended_action="Revalidate claim with Brand Governance Lead before reuse.",
                                status="unresolved",
                                page_number=page_num
                            ))
                        elif unapp_fact.status == "rejected":
                            page_findings.append(GovernanceFinding(
                                category="claim_status_issue",
                                severity="critical",
                                title=f"[Page {page_num}] Prohibited Claim: Rejected Claim ({unapp_fact.fact_key})",
                                explanation=f"[Page {page_num}] Claim '{unapp_fact.fact_value}' detected on Page {page_num} was permanently REJECTED during brand governance review.",
                                text_excerpt=excerpt,
                                matched_fact_id=unapp_fact.id,
                                source_citation=unapp_fact.source_citation or "freshsip_approved_claims.csv",
                                recommended_action="Remove permanently rejected claim immediately.",
                                status="unresolved",
                                page_number=page_num
                            ))

            # 6. General risky health claims on page
            for pattern_re, title_desc, explanation_desc in RISKY_HEALTH_PATTERNS:
                match_p = re.search(pattern_re, page_text, re.IGNORECASE)
                if match_p:
                    is_neg = self.is_negated_or_quoted(page_text, match_p.start(), match_p.end())
                    if is_neg:
                        page_findings.append(GovernanceFinding(
                            category="unsupported_claim",
                            severity="info",
                            title=f"[Page {page_num}] Contextual Health Mention Noted: {title_desc}",
                            explanation=f"[Page {page_num}] Medical claim phrase '{match_p.group(0)}' detected in negated/editorial context. Verified compliant under editorial exception.",
                            text_excerpt=match_p.group(0),
                            source_citation="freshsip_brand_guidelines.pdf, Section D, p. 3",
                            recommended_action="Ensure copy continues to clearly negate medical claims.",
                            status="passed_check",
                            page_number=page_num
                        ))
                    else:
                        reg = self._find_poster_region(page_ocr_res, match_p.group(0))
                        bbox_str = f" [Bbox: {reg[1]}]" if reg else ""
                        excerpt = f"[Page {page_num}] '{reg[0] if reg else match_p.group(0)}'{bbox_str}"
                        page_findings.append(GovernanceFinding(
                            category="unsupported_claim",
                            severity="critical",
                            title=f"[Page {page_num}] Unsupported Claim: {title_desc}",
                            explanation=f"[Page {page_num}] {explanation_desc} The phrase '{match_p.group(0)}' was detected on Page {page_num} without verified substantiation.",
                            text_excerpt=excerpt,
                            source_citation="SUPPORTING EVIDENCE NOT FOUND",
                            recommended_action="Remove unverified clinical/health claims or upload approved evidence to the Knowledge Library.",
                            status="unresolved",
                            page_number=page_num
                        ))

            # 7. Visual Governance Checks for page
            visual_findings = image_governance.evaluate_poster_for_governance(
                file_path=page_raster,
                channel=channel,
                alt_text=content_version.poster_alt_text,
                org_id=org_id,
                db=db,
                brand_id=brand_id,
                ocr_result=page_ocr_res,
                page_number=page_num
            )
            page_findings.extend(visual_findings)

            # 8. Deduplication within Page {page_num}
            seen_page = set()
            unique_page_findings: List[GovernanceFinding] = []
            for f in page_findings:
                key = (f.category, f.matched_rule_id, f.matched_fact_id, f.title)
                if key not in seen_page:
                    seen_page.add(key)
                    unique_page_findings.append(f)

            all_findings.extend(unique_page_findings)

        # -------------------------------------------------------------
        # DOCUMENT-LEVEL ALLERGEN & DISCLOSURE CHECKS
        # -------------------------------------------------------------
        combined_all = f"{body_text}\n" + "\n".join(all_page_texts.values())

        for rule in approved_rules:
            if rule.rule_type not in ("required_term", "requirement"):
                continue
            if not self.is_rule_in_channel_scope(rule.scope, channel):
                continue

            rules_eval_count += 1

            if rule.rule_code == "FR-RULE-014":
                if "FS-PROD-003" in doc_detected_products:
                    if not re.search(r"\b(?:contains\s+celery|allergen[:\s]+celery)\b", combined_all, re.IGNORECASE):
                        all_findings.append(GovernanceFinding(
                            category="mandatory_wording_missing",
                            severity="critical",
                            title="[FR-RULE-014] Missing Mandatory Allergen Disclosure: Celery (Multi-Page PDF)",
                            explanation="Garden Tomato Celery Press (FS-PROD-003) must disclose 'Contains Celery (14%)' on product descriptions, packaging, and listings. Checked across all PDF pages and caption copy.",
                            text_excerpt=None,
                            matched_rule_id=rule.id,
                            source_citation=rule.source_citation or "freshsip_brand_guidelines.pdf, Section E, p. 5",
                            recommended_action="Add mandatory allergen statement: 'Contains Celery (14%)' in creative or caption.",
                            status="unresolved",
                            page_number=None
                        ))
                if "FS-PROD-004" in doc_detected_products:
                    if re.search(r"\b(?:allergen[ -]free|100%\s+allergen[ -]free|suitable for all allergy)\b", combined_all, re.IGNORECASE):
                        all_findings.append(GovernanceFinding(
                            category="missing_evidence",
                            severity="critical",
                            title="[FR-RULE-014] Prohibited Allergen Claim: Allergen Status Not Provided (FS-PROD-004)",
                            explanation="Spiced Carrot Beetroot Press (FS-PROD-004) has allergen status marked 'not_provided'. Claiming allergen-free violates brand guidelines.",
                            text_excerpt=None,
                            matched_rule_id=rule.id,
                            source_citation=rule.source_citation or "freshsip_brand_guidelines.pdf, Section E, p. 5",
                            recommended_action="Remove allergen-free claim or upload certified allergen cross-contact test results.",
                            status="unresolved",
                            page_number=None
                        ))

            if rule.rule_code in ("FR-RULE-005", "FR-RULE-006") or "sugar" in rule.title.lower():
                if re.search(r"\bsugar\b", combined_all, re.IGNORECASE):
                    if not re.search(r"\bno added sugar\b", combined_all, re.IGNORECASE):
                        all_findings.append(GovernanceFinding(
                            category="mandatory_wording_missing",
                            severity=rule.severity,
                            title=f"[{rule.rule_code or 'REQUIREMENT'}] Missing Required Term: 'No Added Sugar'",
                            explanation="When describing sugar content in fruit/vegetable juices, approved policy requires stating 'No Added Sugar' rather than 'Zero Sugar' (checked across caption and all PDF pages).",
                            text_excerpt=None,
                            matched_rule_id=rule.id,
                            source_citation=rule.source_citation or "freshsip_brand_guidelines.pdf, Section C, p. 3",
                            recommended_action="Use 'No Added Sugar' and acknowledge naturally occurring fruit sugars.",
                            status="unresolved",
                            page_number=None
                        ))

            if rule.rule_code == "FR-RULE-007" or "tagline" in rule.title.lower():
                norm_chan = self.normalize_channel(channel)
                if norm_chan in ("promotional_content", "packaging"):
                    pattern_escaped = re.escape(rule.pattern.strip())
                    if not re.search(rf"\b{pattern_escaped}\b", combined_all, re.IGNORECASE):
                        all_findings.append(GovernanceFinding(
                            category="mandatory_wording_missing",
                            severity=rule.severity,
                            title=f"[{rule.rule_code or 'REQUIREMENT'}] Missing Brand Tagline: '{rule.pattern}'",
                            explanation=f"Required brand tagline '{rule.pattern}' was not found in campaign copy or any PDF page.",
                            text_excerpt=None,
                            matched_rule_id=rule.id,
                            source_citation=rule.source_citation or "freshsip_brand_guidelines.pdf",
                            recommended_action=f"Add approved brand tagline: '{rule.pattern}'.",
                            status="unresolved",
                            page_number=None
                        ))

        return all_findings, rules_eval_count, facts_eval_count

    def _evaluate_caption_copy_for_pdf(
        self,
        body_text: str,
        channel: str,
        approved_rules: List[KnowledgeRule],
        approved_facts: List[KnowledgeFact],
        unapproved_facts: List[KnowledgeFact],
        title: str,
        product_id: Optional[str]
    ) -> List[GovernanceFinding]:
        findings: List[GovernanceFinding] = []
        detected_prods = self.detect_product_context(f"{title} {body_text}", title, product_id)

        for rule in approved_rules:
            if rule.rule_type not in ("prohibition", "restriction", "prohibited_word") and rule.rule_code != "FR-RULE-005":
                continue
            if not self.is_rule_in_channel_scope(rule.scope, channel):
                continue

            sub_patterns = [p.strip() for p in rule.pattern.split(",") if p.strip()] if "," in rule.pattern else [rule.pattern.strip()]
            for pat in sub_patterns:
                pat_escaped = re.escape(pat)
                regex = re.compile(rf"\b{pat_escaped}\b", re.IGNORECASE)
                m = regex.search(body_text)
                if not m:
                    continue

                is_neg = self.is_negated_or_quoted(body_text, m.start(), m.end())
                rule_prefix = f"[{rule.rule_code}] " if rule.rule_code else ""
                if is_neg:
                    findings.append(GovernanceFinding(
                        category="prohibited_wording",
                        severity="info",
                        title=f"Contextual Mention Noted (Negated): '{pat}'",
                        explanation=f"Phrase '{pat}' appeared in a qualifying or negated context in caption copy. Rule: {rule.title}.",
                        text_excerpt=self._extract_excerpt(body_text, m.start(), m.end()),
                        matched_rule_id=rule.id,
                        source_citation=rule.source_citation or "freshsip_brand_guidelines.pdf",
                        recommended_action="No action required if used strictly to clarify or negate unverified claims.",
                        status="passed_check",
                        page_number=None
                    ))
                else:
                    findings.append(GovernanceFinding(
                        category="prohibited_wording",
                        severity=rule.severity,
                        title=f"{rule_prefix}Prohibited Term in Caption: '{pat}'",
                        explanation=f"Caption copy contains prohibited language '{pat}'. Rule: {rule.title}. Reason: {rule.explanation}",
                        text_excerpt=self._extract_excerpt(body_text, m.start(), m.end()),
                        matched_rule_id=rule.id,
                        source_citation=rule.source_citation or "freshsip_brand_guidelines.pdf",
                        recommended_action=f"Remove or rephrase '{pat}' from caption copy. Action: {rule.enforcement_action or 'block'}.",
                        status="unresolved",
                        page_number=None
                    ))

        for pattern_re, title_desc, explanation_desc in RISKY_HEALTH_PATTERNS:
            match_c = re.search(pattern_re, body_text, re.IGNORECASE)
            if match_c:
                is_neg = self.is_negated_or_quoted(body_text, match_c.start(), match_c.end())
                if is_neg:
                    findings.append(GovernanceFinding(
                        category="unsupported_claim",
                        severity="info",
                        title=f"Contextual Health Mention Noted: {title_desc}",
                        explanation=f"Medical claim phrase '{match_c.group(0)}' detected in negated/editorial context in caption. Verified compliant under editorial exception.",
                        text_excerpt=match_c.group(0),
                        source_citation="freshsip_brand_guidelines.pdf, Section D, p. 3",
                        recommended_action="Ensure copy continues to clearly negate medical claims.",
                        status="passed_check",
                        page_number=None
                    ))
                else:
                    findings.append(GovernanceFinding(
                        category="unsupported_claim",
                        severity="critical",
                        title=f"Unsupported Claim in Caption: {title_desc}",
                        explanation=f"{explanation_desc} The phrase '{match_c.group(0)}' was detected in caption without verified substantiation.",
                        text_excerpt=self._extract_excerpt(body_text, match_c.start(), match_c.end()),
                        source_citation="SUPPORTING EVIDENCE NOT FOUND",
                        recommended_action="Remove unverified clinical/health claims or upload approved evidence to the Knowledge Library.",
                        status="unresolved",
                        page_number=None
                    ))

        return findings

governance_engine = GovernanceEngine()

