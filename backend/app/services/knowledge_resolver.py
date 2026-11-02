import uuid
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session

from app.models.knowledge import (
    KnowledgeRule,
    KnowledgeFact,
    KnowledgeBaseVersion,
    OrganizationActiveKnowledgeBase,
    BrandAsset
)
from app.models.product import Product
from app.models.claim import Claim, RequiredDisclosure
from app.models.brand import BrandProfile, BrandColor


def _parse_date(val: Any) -> Optional[date]:
    """Parse string or date objects into datetime.date."""
    if not val:
        return None
    if isinstance(val, date) and not isinstance(val, datetime):
        return val
    if isinstance(val, datetime):
        return val.date()
    if isinstance(val, str):
        val = val.strip()
        if not val:
            return None
        try:
            return date.fromisoformat(val[:10])
        except Exception:
            return None
    return None


class ManifestProductAdapter:
    """Read-only adapter for a Product snapshot record within a KnowledgeBaseVersion manifest."""
    def __init__(self, data: Dict[str, Any], org_id: Optional[str] = None):
        self._data = data or {}
        self.id = self._data.get("id") or str(uuid.uuid4())
        self.organization_id = org_id or self._data.get("organization_id")
        self.product_id = self._data.get("product_id") or ""
        self.product_name = self._data.get("product_name") or self._data.get("name") or ""
        self.product_category = self._data.get("product_category") or self._data.get("category") or ""
        self.offering_type = self._data.get("offering_type") or ""
        self.variant_name = self._data.get("variant_name") or ""
        self.sku = self._data.get("sku") or ""
        self.pack_size = self._data.get("pack_size")
        self.pack_unit = self._data.get("pack_unit")
        self.ingredients_components = self._data.get("ingredients_components") or self._data.get("ingredients") or ""
        self.applicable_market = self._data.get("applicable_market") or self._data.get("market") or ""
        self.record_status = self._data.get("record_status") or self._data.get("status") or "Active"

    def __repr__(self) -> str:
        return f"<ManifestProductAdapter {self.product_id} ({self.product_name})>"


class ManifestClaimAdapter:
    """Read-only adapter for a Claim snapshot record within a KnowledgeBaseVersion manifest."""
    def __init__(self, data: Dict[str, Any], org_id: Optional[str] = None):
        self._data = data or {}
        self.id = self._data.get("id") or str(uuid.uuid4())
        self.organization_id = org_id or self._data.get("organization_id")
        self.claim_id = self._data.get("claim_id") or ""
        self.applicable_product_id = self._data.get("applicable_product_id") or "ALL"
        self.claim_text = self._data.get("claim_text") or ""
        self.claim_status = self._data.get("claim_status") or self._data.get("status") or "Approved"
        self.claim_type = self._data.get("claim_type") or self._data.get("type") or ""
        self.restricted_conditions = self._data.get("restricted_conditions") or ""
        self.prohibited_variations = self._data.get("prohibited_variations") or ""
        self.approved_variations = self._data.get("approved_variations") or ""
        self.applicable_market = self._data.get("applicable_market") or self._data.get("market") or ""
        self.effective_from = _parse_date(self._data.get("effective_from"))
        self.effective_until = _parse_date(self._data.get("effective_until"))

    def __repr__(self) -> str:
        return f"<ManifestClaimAdapter {self.claim_id} ({self.claim_status})>"


class ManifestDisclosureAdapter:
    """Read-only adapter for a RequiredDisclosure snapshot record within a KnowledgeBaseVersion manifest."""
    def __init__(self, data: Dict[str, Any], org_id: Optional[str] = None):
        self._data = data or {}
        self.id = self._data.get("id") or str(uuid.uuid4())
        self.organization_id = org_id or self._data.get("organization_id")
        self.disclosure_id = self._data.get("disclosure_id") or ""
        self.applicable_product_id = self._data.get("applicable_product_id") or "ALL"
        self.disclosure_text = self._data.get("disclosure_text") or self._data.get("text") or ""
        self.applies_when = self._data.get("applies_when") or ""
        self.applicable_market = self._data.get("applicable_market") or self._data.get("market") or ""
        self.effective_from = _parse_date(self._data.get("effective_from"))
        self.effective_until = _parse_date(self._data.get("effective_until"))

    def __repr__(self) -> str:
        return f"<ManifestDisclosureAdapter {self.disclosure_id}>"


class ManifestBrandProfileAdapter:
    """Read-only adapter for a BrandProfile snapshot record within a KnowledgeBaseVersion manifest."""
    def __init__(self, data: Dict[str, Any], org_id: Optional[str] = None):
        self._data = data or {}
        self.organization_id = org_id
        self.brand_name = self._data.get("brand_name") or "Brand"
        self.brand_description = self._data.get("brand_description") or self._data.get("description") or ""
        self.brand_personality = self._data.get("personality") or self._data.get("brand_personality") or []
        self.preferred_tone = self._data.get("preferred_tone") or []
        self.tones_to_avoid = self._data.get("tones_to_avoid") or []
        self.preferred_terminology = self._data.get("preferred_terminology") or []
        self.prohibited_terminology = self._data.get("prohibited_terminology") or []
        self.writing_style = self._data.get("writing_style")
        self.spelling_convention = self._data.get("spelling_convention")
        self.writing_style_instructions = self._data.get("writing_style_instructions")
        self.approved_languages = self._data.get("approved_languages") or []
        self.primary_heading_font = self._data.get("primary_heading_font") or self._data.get("heading_font")
        self.secondary_body_font = self._data.get("secondary_body_font") or self._data.get("body_font")
        self.additional_approved_fonts = self._data.get("additional_approved_fonts") or self._data.get("additional_fonts") or []
        self.visual_style = self._data.get("visual_style") or []
        self.preferred_imagery_style = self._data.get("preferred_imagery_style") or self._data.get("imagery_style") or []
        self.preferred_backgrounds = self._data.get("preferred_backgrounds") or self._data.get("backgrounds") or []
        self.preferred_visual_treatments = self._data.get("preferred_visual_treatments") or []
        self.visual_styles_to_avoid = self._data.get("visual_styles_to_avoid") or []
        self.logo_usage_instructions = self._data.get("logo_usage_instructions") or self._data.get("logo_instructions")

    def __repr__(self) -> str:
        return f"<ManifestBrandProfileAdapter {self.brand_name}>"


class ManifestBrandColorAdapter:
    """Read-only adapter for a BrandColor snapshot record within a KnowledgeBaseVersion manifest."""
    def __init__(self, data: Dict[str, Any]):
        self._data = data or {}
        self.colour_name = self._data.get("colour_name") or self._data.get("name") or ""
        self.colour_family = self._data.get("colour_family") or self._data.get("family") or ""
        self.colour_role = self._data.get("colour_role") or self._data.get("role") or ""
        self.hex_value = self._data.get("hex_value") or self._data.get("hex") or ""
        rgb = self._data.get("rgb") or []
        self.rgb_r = self._data.get("rgb_r", rgb[0] if len(rgb) > 0 else 0)
        self.rgb_g = self._data.get("rgb_g", rgb[1] if len(rgb) > 1 else 0)
        self.rgb_b = self._data.get("rgb_b", rgb[2] if len(rgb) > 2 else 0)

    def __repr__(self) -> str:
        return f"<ManifestBrandColorAdapter {self.colour_name} ({self.hex_value})>"


class ManifestBrandAssetAdapter:
    """Read-only adapter for a BrandAsset snapshot record within a KnowledgeBaseVersion manifest."""
    def __init__(self, data: Dict[str, Any]):
        self._data = data or {}
        self.id = self._data.get("id") or self._data.get("asset_id") or str(uuid.uuid4())
        self.asset_name = self._data.get("asset_name") or ""
        self.asset_type = self._data.get("asset_type") or ""
        self.file_path = self._data.get("file_path") or ""
        self.status = self._data.get("status") or "approved"

    def __repr__(self) -> str:
        return f"<ManifestBrandAssetAdapter {self.asset_name} ({self.asset_type})>"


class ManifestRuleAdapter:
    """Read-only adapter for a KnowledgeRule snapshot record within a KnowledgeBaseVersion manifest."""
    def __init__(self, data: Dict[str, Any]):
        self._data = data or {}
        self.id = self._data.get("id") or str(uuid.uuid4())
        self.rule_code = self._data.get("rule_code")
        self.category = self._data.get("category")
        self.rule_type = self._data.get("rule_type")
        self.severity = self._data.get("severity") or "warning"
        self.title = self._data.get("title") or ""
        self.explanation = self._data.get("explanation") or ""
        self.pattern = self._data.get("pattern") or ""
        self.examples_good = self._data.get("examples_good")
        self.examples_bad = self._data.get("examples_bad")
        self.source_citation = self._data.get("source_citation")
        self.scope = self._data.get("scope") or "all_channels"
        self.status = self._data.get("status") or "approved"
        self.brand_id = self._data.get("brand_id")
        self.enforcement_action = self._data.get("enforcement_action") or "block"
        self.recommended_alternatives = self._data.get("recommended_alternatives")

    def __repr__(self) -> str:
        return f"<ManifestRuleAdapter {self.rule_code}: {self.title}>"


class ManifestFactAdapter:
    """Read-only adapter for a KnowledgeFact snapshot record within a KnowledgeBaseVersion manifest."""
    def __init__(self, data: Dict[str, Any]):
        self._data = data or {}
        self.id = self._data.get("id") or str(uuid.uuid4())
        self.product_id = self._data.get("product_id")
        self.product_name = self._data.get("product_name") or ""
        self.category = self._data.get("category")
        self.fact_key = self._data.get("fact_key") or ""
        self.fact_value = self._data.get("fact_value") or ""
        self.status = self._data.get("status") or "approved"
        self.valid_from = _parse_date(self._data.get("valid_from") or self._data.get("effective_from"))
        self.valid_until = _parse_date(self._data.get("valid_until") or self._data.get("effective_until"))
        self.effective_from = self.valid_from
        self.effective_until = self.valid_until
        self.source_citation = self._data.get("source_citation")
        self.brand_id = self._data.get("brand_id")

    def __repr__(self) -> str:
        return f"<ManifestFactAdapter {self.product_id} [{self.fact_key}]>"


@dataclass
class ResolvedKnowledgeBase:
    """
    Central immutable bundle of knowledge resolved for a governance run.
    Guarantees that evaluation strictly reads from the selected immutable snapshot
    without fallback queries to mutable tables when an active version is resolved.
    """
    organization_id: str
    version_id: Optional[str]
    version_num: Optional[int]
    baseline_status: str  # "versioned" or "legacy_unversioned"
    manifest_data: Optional[Dict[str, Any]]
    products: List[Any] = field(default_factory=list)
    claims: List[Any] = field(default_factory=list)
    required_disclosures: List[Any] = field(default_factory=list)
    brand_profile: Optional[Any] = None
    brand_colors: List[Any] = field(default_factory=list)
    brand_assets: List[Any] = field(default_factory=list)
    rules: List[Any] = field(default_factory=list)
    facts: List[Any] = field(default_factory=list)
    unapproved_facts: List[Any] = field(default_factory=list)

    @property
    def active_products(self) -> List[Any]:
        """Return only active products for context detection."""
        return [
            p for p in self.products
            if getattr(p, "record_status", "Active") == "Active"
        ]


def resolve_knowledge_base(
    db: Session,
    org_id: Optional[str],
    target_version_id: Optional[str] = None
) -> ResolvedKnowledgeBase:
    """
    Resolves the exact knowledge baseline for governance evaluation.

    Resolution Strategy:
    1. If target_version_id is provided, resolve that specific KnowledgeBaseVersion snapshot.
    2. Otherwise, check OrganizationActiveKnowledgeBase for org_id. If active, resolve that snapshot.
    3. When an immutable snapshot is resolved:
       - Products, Claims, Disclosures, Brand Profile, Colors, and Assets are loaded strictly from manifest_data.
       - Rules and Facts: If serialized in manifest_data, loaded from manifest. If absent (e.g. legacy v1 manifest),
         loads approved rules and facts from DB for that organisation as backward compatibility.
       - NO queries are made to mutable Product, Claim, or RequiredDisclosure tables.
    4. If no version exists (legacy_unversioned):
       - Fallback to mutable tables directly, preserving documented legacy behaviour.
    """
    if not org_id:
        return ResolvedKnowledgeBase(
            organization_id="",
            version_id=None,
            version_num=None,
            baseline_status="legacy_unversioned",
            manifest_data=None
        )

    kb_version: Optional[KnowledgeBaseVersion] = None

    if target_version_id:
        kb_version = db.query(KnowledgeBaseVersion).filter(
            KnowledgeBaseVersion.id == target_version_id,
            KnowledgeBaseVersion.organization_id == org_id
        ).first()
        if not kb_version:
            raise ValueError(
                f"KnowledgeBaseVersion '{target_version_id}' does not exist or does not belong to organization '{org_id}'."
            )
    else:
        active_kb = db.query(OrganizationActiveKnowledgeBase).filter(
            OrganizationActiveKnowledgeBase.organization_id == org_id
        ).first()
        if active_kb and active_kb.active_version_id:
            kb_version = db.query(KnowledgeBaseVersion).filter(
                KnowledgeBaseVersion.id == active_kb.active_version_id,
                KnowledgeBaseVersion.organization_id == org_id
            ).first()

    # Case A: Immutable snapshot found (Versioned baseline)
    if kb_version and kb_version.manifest_data:
        m = kb_version.manifest_data

        products = [ManifestProductAdapter(p, org_id) for p in m.get("products", [])]
        claims = [ManifestClaimAdapter(c, org_id) for c in m.get("claims", [])]
        disclosures = [ManifestDisclosureAdapter(d, org_id) for d in m.get("required_disclosures", [])]
        profile_data = m.get("brand_profile")
        brand_profile = ManifestBrandProfileAdapter(profile_data, org_id) if profile_data else None
        colors = [ManifestBrandColorAdapter(c) for c in m.get("brand_colors", [])]
        assets = [ManifestBrandAssetAdapter(a) for a in m.get("brand_assets", [])]

        # Rules
        if "rules" in m and isinstance(m["rules"], list):
            rules = [ManifestRuleAdapter(r) for r in m["rules"]]
        else:
            # Backward-compatibility for manifests created before rules serialization
            rules = db.query(KnowledgeRule).filter(
                KnowledgeRule.organization_id == org_id,
                KnowledgeRule.status == "approved"
            ).all()

        # Facts
        if "facts" in m and isinstance(m["facts"], list):
            facts = [ManifestFactAdapter(f) for f in m["facts"]]
        else:
            # Backward-compatibility for manifests created before facts serialization
            facts = db.query(KnowledgeFact).filter(
                KnowledgeFact.organization_id == org_id,
                KnowledgeFact.status == "approved"
            ).all()

        # Query pending/rejected/expired facts for FR-RULE-018 unapproved claim escalation
        unapproved_facts = db.query(KnowledgeFact).filter(
            KnowledgeFact.organization_id == org_id,
            KnowledgeFact.status.in_(["pending_review", "rejected", "expired"])
        ).all()

        return ResolvedKnowledgeBase(
            organization_id=org_id,
            version_id=kb_version.id,
            version_num=kb_version.version_num,
            baseline_status="versioned",
            manifest_data=m,
            products=products,
            claims=claims,
            required_disclosures=disclosures,
            brand_profile=brand_profile,
            brand_colors=colors,
            brand_assets=assets,
            rules=rules,
            facts=facts,
            unapproved_facts=unapproved_facts
        )

    # Case B: Legacy / Unversioned Organization (Fallback to mutable tables)
    brand_profile = db.query(BrandProfile).filter(BrandProfile.organization_id == org_id).first()
    products = db.query(Product).filter(Product.organization_id == org_id).all()
    claims = db.query(Claim).filter(Claim.organization_id == org_id).all()
    disclosures = db.query(RequiredDisclosure).filter(RequiredDisclosure.organization_id == org_id).all()
    colors = db.query(BrandColor).filter(BrandColor.organization_id == org_id).all()
    assets = db.query(BrandAsset).filter(
        BrandAsset.organization_id == org_id,
        BrandAsset.status == "approved"
    ).all()
    rules = db.query(KnowledgeRule).filter(
        KnowledgeRule.organization_id == org_id,
        KnowledgeRule.status == "approved"
    ).all()
    facts = db.query(KnowledgeFact).filter(
        KnowledgeFact.organization_id == org_id,
        KnowledgeFact.status == "approved"
    ).all()
    unapproved_facts = db.query(KnowledgeFact).filter(
        KnowledgeFact.organization_id == org_id,
        KnowledgeFact.status.in_(["pending_review", "rejected", "expired"])
    ).all()

    return ResolvedKnowledgeBase(
        organization_id=org_id,
        version_id=None,
        version_num=None,
        baseline_status="legacy_unversioned",
        manifest_data=None,
        products=products,
        claims=claims,
        required_disclosures=disclosures,
        brand_profile=brand_profile,
        brand_colors=colors,
        brand_assets=assets,
        rules=rules,
        facts=facts,
        unapproved_facts=unapproved_facts
    )
