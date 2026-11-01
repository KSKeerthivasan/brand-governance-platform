import os
import re

def decouple_suggestion_service():
    path = "backend/app/services/suggestion_service.py"
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    # Step 1: Update imports
    target_import = """from app.models.content import ContentItem, ContentVersion, GovernanceRun, GovernanceFinding, CorrectionSuggestion
from app.models.knowledge import KnowledgeRule, KnowledgeFact
from app.models.organization import User"""

    replacement_import = """from app.models.content import ContentItem, ContentVersion, GovernanceRun, GovernanceFinding, CorrectionSuggestion
from app.models.knowledge import KnowledgeRule, KnowledgeFact
from app.models.organization import User
from app.models.product import Product
from app.models.claim import Claim, RequiredDisclosure
from app.models.brand import BrandProfile"""

    content = content.replace(target_import, replacement_import)

    # Step 2: Update detect_sku_from_text method signature and body
    target_detect = """    def detect_sku_from_text(self, text: str, title: str) -> Optional[str]:
        \"\"\"Identify which SKU is referenced in the copy or title.\"\"\"
        combined = f\"{title} {text}\".lower()
        if any(k in combined for k in [\"fs-prod-001\", \"valencia orange\"]):
            return \"FS-PROD-001\"
        if any(k in combined for k in [\"fs-prod-002\", \"pink guava\", \"pomegranate nectar\"]):
            return \"FS-PROD-002\"
        if any(k in combined for k in [\"fs-prod-003\", \"garden tomato\", \"tomato celery\"]):
            return \"FS-PROD-003\"
        if any(k in combined for k in [\"fs-prod-004\", \"spiced carrot\", \"carrot beetroot\"]):
            return \"FS-PROD-004\"
        if any(k in combined for k in [\"fs-prod-005\", \"green orchard\", \"cucumber spinach\"]):
            return \"FS-PROD-005\"
        if any(k in combined for k in [\"fs-prod-006\", \"citrus carrot\", \"carrot ginger\"]):
            return \"FS-PROD-006\"
        return None"""

    replacement_detect = """    def detect_sku_from_text(self, text: str, title: str, org_id: Optional[str] = None, db: Optional[Session] = None) -> Optional[str]:
        \"\"\"Identify which SKU is referenced in the copy or title dynamically from DB or fallback.\"\"\"
        combined = f\"{title} {text}\".lower()
        if db and org_id:
            try:
                products = db.query(Product).filter(
                    Product.organization_id == org_id,
                    Product.record_status == \"Active\"
                ).all()
                for p in products:
                    aliases = [p.product_id.lower()]
                    if p.product_name:
                        aliases.append(p.product_name.lower())
                    if p.variant_name:
                        aliases.append(p.variant_name.lower())
                    if p.sku:
                        aliases.append(p.sku.lower())
                    if any(re.search(rf\"\\b{re.escape(alias)}\\b\", combined) for alias in aliases):
                        return p.product_id
            except Exception:
                pass

        if any(k in combined for k in [\"fs-prod-001\", \"valencia orange\"]):
            return \"FS-PROD-001\"
        if any(k in combined for k in [\"fs-prod-002\", \"pink guava\", \"pomegranate nectar\"]):
            return \"FS-PROD-002\"
        if any(k in combined for k in [\"fs-prod-003\", \"garden tomato\", \"tomato celery\"]):
            return \"FS-PROD-003\"
        if any(k in combined for k in [\"fs-prod-004\", \"spiced carrot\", \"carrot beetroot\"]):
            return \"FS-PROD-004\"
        if any(k in combined for k in [\"fs-prod-005\", \"green orchard\", \"cucumber spinach\"]):
            return \"FS-PROD-005\"
        if any(k in combined for k in [\"fs-prod-006\", \"citrus carrot\", \"carrot ginger\"]):
            return \"FS-PROD-006\"
        return None"""

    content = content.replace(target_detect, replacement_detect)

    # Step 3: Pass org_id and db to detect_sku_from_text in generate_suggestions_for_run
    target_gen = """        detected_sku = self.detect_sku_from_text(version.body_text or \"\", item.title or \"\")"""
    replacement_gen = """        detected_sku = self.detect_sku_from_text(version.body_text or \"\", item.title or \"\", org_id=item.organization_id, db=db)"""
    content = content.replace(target_gen, replacement_gen)

    # Step 4: Resolve brand_name in _generate_suggestion_for_finding
    target_func = """    def _generate_suggestion_for_finding(
        self,
        db: Session,
        finding: GovernanceFinding,
        version: ContentVersion,
        item: ContentItem,
        detected_sku: Optional[str]
    ) -> Optional[CorrectionSuggestion]:
        \"\"\"Route finding to appropriate category generator.\"\"\""""

    replacement_func = """    def _generate_suggestion_for_finding(
        self,
        db: Session,
        finding: GovernanceFinding,
        version: ContentVersion,
        item: ContentItem,
        detected_sku: Optional[str]
    ) -> Optional[CorrectionSuggestion]:
        \"\"\"Route finding to appropriate category generator.\"\"\"
        org_id = item.organization_id
        brand_profile = db.query(BrandProfile).filter(BrandProfile.organization_id == org_id).first() if org_id else None
        brand_name = brand_profile.brand_name if brand_profile else \"Freshsip\""""

    content = content.replace(target_func, replacement_func)

    # Replace citations and specific builders
    content = content.replace('\"freshsip_brand_guidelines.pdf, Section C: Terminology Rules\"', 'f\"{brand_name} Brand Guidelines, Section C: Terminology Rules\"')
    content = content.replace('\"freshsip_brand_guidelines.pdf, Section A: Brand Identity\"', 'f\"{brand_name} Brand Guidelines, Section A: Brand Identity\"')
    content = content.replace('\"freshsip_brand_guidelines.pdf, Section D: Messaging and Claims\"', 'f\"{brand_name} Brand Guidelines, Section D: Messaging and Claims\"')
    content = content.replace('\"freshsip_brand_guidelines.pdf, Section F: Product and Promotion Rules\"', 'f\"{brand_name} Brand Guidelines, Section F: Product and Promotion Rules\"')
    content = content.replace('\"freshsip_brand_guidelines.pdf, Section E: Mandatory Wording and Disclosures\"', 'f\"{brand_name} Brand Guidelines, Section E: Mandatory Wording and Disclosures\"')
    content = content.replace('\"freshsip_brand_guidelines.pdf, Section B: Tone of Voice\"', 'f\"{brand_name} Brand Guidelines, Section B: Tone of Voice\"')
    content = content.replace('\"freshsip_brand_guidelines.pdf, Section G: Asset-Use Rules\"', 'f\"{brand_name} Brand Guidelines, Section G: Asset-Use Rules\"')
    content = content.replace('f\"freshsip_products.csv (SKU: {sku or \'FS-PROD-001\'}, MRP: {approved_price_str})\"', 'f\"{brand_name} Product Catalogue (SKU: {sku or \'FS-PROD-001\'}, MRP: {approved_price_str})\"')
    content = content.replace('f\"freshsip_approved_claims.csv (Claim ID: {approved_claim_code})\"', 'f\"{brand_name} Claims Register (Claim ID: {approved_claim_code})\"')

    # Pass db and brand_name into _build_* helpers
    content = content.replace('return self._build_sugar_terminology_suggestion(finding, version, item, target_type, rule, detected_sku)',
                              'return self._build_sugar_terminology_suggestion(finding, version, item, target_type, rule, detected_sku, brand_name, db)')
    content = content.replace('return self._build_miracle_terminology_suggestion(finding, version, item, target_type, rule)',
                              'return self._build_miracle_terminology_suggestion(finding, version, item, target_type, rule, brand_name, db)')
    content = content.replace('return self._build_processing_terminology_suggestion(finding, version, item, target_type, rule, detected_sku)',
                              'return self._build_processing_terminology_suggestion(finding, version, item, target_type, rule, detected_sku, brand_name, db)')
    content = content.replace('return self._build_naming_suggestion(finding, version, item, target_type, rule)',
                              'return self._build_naming_suggestion(finding, version, item, target_type, rule, brand_name, db)')
    content = content.replace('return self._build_natural_organic_suggestion(finding, version, item, target_type, rule, detected_sku)',
                              'return self._build_natural_organic_suggestion(finding, version, item, target_type, rule, detected_sku, brand_name, db)')
    content = content.replace('return self._build_superlative_suggestion(finding, version, item, target_type, rule)',
                              'return self._build_superlative_suggestion(finding, version, item, target_type, rule, brand_name, db)')
    content = content.replace('return self._build_price_or_fact_suggestion(finding, version, item, target_type, rule, fact, detected_sku)',
                              'return self._build_price_or_fact_suggestion(finding, version, item, target_type, rule, fact, detected_sku, brand_name, db)')
    content = content.replace('return self._build_discount_suggestion(finding, version, item, target_type, rule)',
                              'return self._build_discount_suggestion(finding, version, item, target_type, rule, brand_name, db)')
    content = content.replace('return self._build_claim_suggestion(finding, version, item, target_type, rule, fact, detected_sku)',
                              'return self._build_claim_suggestion(finding, version, item, target_type, rule, fact, detected_sku, brand_name, db)')
    content = content.replace('return self._build_disclosure_suggestion(finding, version, item, target_type, rule, detected_sku)',
                              'return self._build_disclosure_suggestion(finding, version, item, target_type, rule, detected_sku, brand_name, db)')
    content = content.replace('return self._build_tone_suggestion(finding, version, item, target_type, rule)',
                              'return self._build_tone_suggestion(finding, version, item, target_type, rule, brand_name, db)')
    content = content.replace('return self._build_visual_suggestion(finding, version, item, target_type, rule, detected_sku)',
                              'return self._build_visual_suggestion(finding, version, item, target_type, rule, detected_sku, brand_name, db)')

    # Update helper signatures and implementations
    # Naming suggestion
    old_naming = """    def _build_naming_suggestion(
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
            pattern = re.compile(r"\\bFreshsip(?:\\s+Organic)?(?:\\s+Pvt\\.?\\s*Ltd\\.?)\\b", re.IGNORECASE)"""

    new_naming = """    def _build_naming_suggestion(
        self,
        finding: GovernanceFinding,
        version: ContentVersion,
        item: ContentItem,
        target_type: str,
        rule: Optional[KnowledgeRule],
        brand_name: str = "Freshsip",
        db: Optional[Session] = None
    ) -> CorrectionSuggestion:
        original_excerpt = finding.text_excerpt or f"{brand_name} Organic Pvt. Ltd."
        cleaned_orig = re.sub(r"^\[Page \d+\]\s*", "", original_excerpt).strip("'\" ")
        replacement = f"{brand_name} Beverages" if brand_name == "Freshsip" else brand_name

        if target_type == "body_text":
            body = version.body_text or ""
            pattern = re.compile(rf"\\b{re.escape(brand_name)}(?:\\s+Organic)?(?:\\s+Pvt\\.?\\s*Ltd\\.?)\\b", re.IGNORECASE)"""

    content = content.replace(old_naming, new_naming)

    # Tone suggestion
    old_tone = """    def _build_tone_suggestion(
        self,
        finding: GovernanceFinding,
        version: ContentVersion,
        item: ContentItem,
        target_type: str,
        rule: Optional[KnowledgeRule]
    ) -> CorrectionSuggestion:
        original_excerpt = finding.text_excerpt or "Fear-based language"
        cleaned_orig = re.sub(r"^\[Page \d+\]\s*", "", original_excerpt).strip("'\" ")
        replacement = "Looking for a crisp, refreshing afternoon pick-me-up? Enjoy a chilled bottle of Freshsip.\""""

    new_tone = """    def _build_tone_suggestion(
        self,
        finding: GovernanceFinding,
        version: ContentVersion,
        item: ContentItem,
        target_type: str,
        rule: Optional[KnowledgeRule],
        brand_name: str = "Freshsip",
        db: Optional[Session] = None
    ) -> CorrectionSuggestion:
        original_excerpt = finding.text_excerpt or "Fear-based language"
        cleaned_orig = re.sub(r"^\[Page \d+\]\s*", "", original_excerpt).strip("'\" ")
        replacement = f"Looking for a crisp, refreshing afternoon pick-me-up? Enjoy a chilled bottle of {brand_name}.\""""

    content = content.replace(old_tone, new_tone)

    # Update explanation in tone suggestion
    content = content.replace(
        'explanation="Freshsip brand voice is friendly and trustworthy. Update creative artwork in authoring tool."',
        'explanation=f"{brand_name} brand voice is friendly and trustworthy. Update creative artwork in authoring tool."'
    )

    # Update sugar suggestion signature
    content = content.replace(
        'def _build_sugar_terminology_suggestion(\n        self,\n        finding: GovernanceFinding,\n        version: ContentVersion,\n        item: ContentItem,\n        target_type: str,\n        rule: Optional[KnowledgeRule],\n        sku: Optional[str]\n    ) -> CorrectionSuggestion:',
        'def _build_sugar_terminology_suggestion(\n        self,\n        finding: GovernanceFinding,\n        version: ContentVersion,\n        item: ContentItem,\n        target_type: str,\n        rule: Optional[KnowledgeRule],\n        sku: Optional[str],\n        brand_name: str = "Freshsip",\n        db: Optional[Session] = None\n    ) -> CorrectionSuggestion:'
    )

    # Update miracle suggestion signature
    content = content.replace(
        'def _build_miracle_terminology_suggestion(\n        self,\n        finding: GovernanceFinding,\n        version: ContentVersion,\n        item: ContentItem,\n        target_type: str,\n        rule: Optional[KnowledgeRule]\n    ) -> CorrectionSuggestion:',
        'def _build_miracle_terminology_suggestion(\n        self,\n        finding: GovernanceFinding,\n        version: ContentVersion,\n        item: ContentItem,\n        target_type: str,\n        rule: Optional[KnowledgeRule],\n        brand_name: str = "Freshsip",\n        db: Optional[Session] = None\n    ) -> CorrectionSuggestion:'
    )

    # Update processing suggestion signature and replacement
    content = content.replace(
        'def _build_processing_terminology_suggestion(\n        self,\n        finding: GovernanceFinding,\n        version: ContentVersion,\n        item: ContentItem,\n        target_type: str,\n        rule: Optional[KnowledgeRule],\n        sku: Optional[str]\n    ) -> CorrectionSuggestion:',
        'def _build_processing_terminology_suggestion(\n        self,\n        finding: GovernanceFinding,\n        version: ContentVersion,\n        item: ContentItem,\n        target_type: str,\n        rule: Optional[KnowledgeRule],\n        sku: Optional[str],\n        brand_name: str = "Freshsip",\n        db: Optional[Session] = None\n    ) -> CorrectionSuggestion:'
    )
    content = content.replace(
        'explanation=f"All packaged Freshsip beverages undergo processing ({approved_processing}). Revise design file and re-upload."',
        'explanation=f"All packaged {brand_name} beverages undergo processing ({approved_processing}). Revise design file and re-upload."'
    )

    # Update natural organic signature
    content = content.replace(
        'def _build_natural_organic_suggestion(\n        self,\n        finding: GovernanceFinding,\n        version: ContentVersion,\n        item: ContentItem,\n        target_type: str,\n        rule: Optional[KnowledgeRule],\n        sku: Optional[str]\n    ) -> CorrectionSuggestion:',
        'def _build_natural_organic_suggestion(\n        self,\n        finding: GovernanceFinding,\n        version: ContentVersion,\n        item: ContentItem,\n        target_type: str,\n        rule: Optional[KnowledgeRule],\n        sku: Optional[str],\n        brand_name: str = "Freshsip",\n        db: Optional[Session] = None\n    ) -> CorrectionSuggestion:'
    )
    content = content.replace(
        'explanation="Freshsip holds no organic or chemical-free certifications. Update artwork in authoring tool."',
        'explanation=f"{brand_name} holds no organic or chemical-free certifications. Update artwork in authoring tool."'
    )

    # Update superlative signature
    content = content.replace(
        'def _build_superlative_suggestion(\n        self,\n        finding: GovernanceFinding,\n        version: ContentVersion,\n        item: ContentItem,\n        target_type: str,\n        rule: Optional[KnowledgeRule]\n    ) -> CorrectionSuggestion:',
        'def _build_superlative_suggestion(\n        self,\n        finding: GovernanceFinding,\n        version: ContentVersion,\n        item: ContentItem,\n        target_type: str,\n        rule: Optional[KnowledgeRule],\n        brand_name: str = "Freshsip",\n        db: Optional[Session] = None\n    ) -> CorrectionSuggestion:'
    )

    # Update price or fact signature
    content = content.replace(
        'def _build_price_or_fact_suggestion(\n        self,\n        finding: GovernanceFinding,\n        version: ContentVersion,\n        item: ContentItem,\n        target_type: str,\n        rule: Optional[KnowledgeRule],\n        fact: Optional[KnowledgeFact],\n        sku: Optional[str]\n    ) -> CorrectionSuggestion:',
        'def _build_price_or_fact_suggestion(\n        self,\n        finding: GovernanceFinding,\n        version: ContentVersion,\n        item: ContentItem,\n        target_type: str,\n        rule: Optional[KnowledgeRule],\n        fact: Optional[KnowledgeFact],\n        sku: Optional[str],\n        brand_name: str = "Freshsip",\n        db: Optional[Session] = None\n    ) -> CorrectionSuggestion:'
    )

    # Update discount signature
    content = content.replace(
        'def _build_discount_suggestion(\n        self,\n        finding: GovernanceFinding,\n        version: ContentVersion,\n        item: ContentItem,\n        target_type: str,\n        rule: Optional[KnowledgeRule]\n    ) -> CorrectionSuggestion:',
        'def _build_discount_suggestion(\n        self,\n        finding: GovernanceFinding,\n        version: ContentVersion,\n        item: ContentItem,\n        target_type: str,\n        rule: Optional[KnowledgeRule],\n        brand_name: str = "Freshsip",\n        db: Optional[Session] = None\n    ) -> CorrectionSuggestion:'
    )
    content = content.replace(
        'explanation="Freshsip has no active discount promotion in the approved dataset. Replaces unapproved discount/scarcity claim with approved catalogue pricing range (FR-RULE-016)."',
        'explanation=f"{brand_name} has no active discount promotion in the approved dataset. Replaces unapproved discount/scarcity claim with approved catalogue pricing range (FR-RULE-016)."'
    )
    content = content.replace(
        'explanation="No promotional discount campaign is active for Freshsip. Update artwork in authoring tool."',
        'explanation=f"No promotional discount campaign is active for {brand_name}. Update artwork in authoring tool."'
    )

    # Update claim signature
    content = content.replace(
        'def _build_claim_suggestion(\n        self,\n        finding: GovernanceFinding,\n        version: ContentVersion,\n        item: ContentItem,\n        target_type: str,\n        rule: Optional[KnowledgeRule],\n        fact: Optional[KnowledgeFact],\n        sku: Optional[str]\n    ) -> CorrectionSuggestion:',
        'def _build_claim_suggestion(\n        self,\n        finding: GovernanceFinding,\n        version: ContentVersion,\n        item: ContentItem,\n        target_type: str,\n        rule: Optional[KnowledgeRule],\n        fact: Optional[KnowledgeFact],\n        sku: Optional[str],\n        brand_name: str = "Freshsip",\n        db: Optional[Session] = None\n    ) -> CorrectionSuggestion:'
    )

    # Update disclosure signature
    content = content.replace(
        'def _build_disclosure_suggestion(\n        self,\n        finding: GovernanceFinding,\n        version: ContentVersion,\n        item: ContentItem,\n        target_type: str,\n        rule: Optional[KnowledgeRule],\n        sku: Optional[str]\n    ) -> CorrectionSuggestion:',
        'def _build_disclosure_suggestion(\n        self,\n        finding: GovernanceFinding,\n        version: ContentVersion,\n        item: ContentItem,\n        target_type: str,\n        rule: Optional[KnowledgeRule],\n        sku: Optional[str],\n        brand_name: str = "Freshsip",\n        db: Optional[Session] = None\n    ) -> CorrectionSuggestion:'
    )

    # Update visual suggestion signature
    content = content.replace(
        'def _build_visual_suggestion(\n        self,\n        finding: GovernanceFinding,\n        version: ContentVersion,\n        item: ContentItem,\n        target_type: str,\n        rule: Optional[KnowledgeRule],\n        sku: Optional[str]\n    ) -> CorrectionSuggestion:',
        'def _build_visual_suggestion(\n        self,\n        finding: GovernanceFinding,\n        version: ContentVersion,\n        item: ContentItem,\n        target_type: str,\n        rule: Optional[KnowledgeRule],\n        sku: Optional[str],\n        brand_name: str = "Freshsip",\n        db: Optional[Session] = None\n    ) -> CorrectionSuggestion:'
    )
    content = content.replace(
        'proposed_alt = f"Bottle of Freshsip {prod_name} (250 mL) in glass packaging with fresh fruit ingredients."',
        'proposed_alt = f"Bottle of {brand_name} {prod_name} (250 mL) in glass packaging with fresh fruit ingredients."'
    )

    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print("Decoupling applied to suggestion_service.py successfully.")

if __name__ == "__main__":
    decouple_suggestion_service()
