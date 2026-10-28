"""
Extraction Schemas for Inkloom AI (Production Gemini Knowledge Extraction).

Enforces strict separation of responsibilities:
1. Local Validation Schema: Strict Pydantic models with `extra="forbid"` to ensure
   no unexpected fields, invalid enums, or malformed records are silently accepted.
2. Gemini API Schema: A provider-compatible structured-output schema that avoids
   unsupported fields (like `additional_properties`) when communicating with Gemini API.
"""

import copy
from typing import List, Optional, Literal, Dict, Any
from pydantic import BaseModel, Field, ConfigDict


# ==============================================================================
# LOCAL STRICT VALIDATION SCHEMAS (extra="forbid")
# ==============================================================================

class StrictBrandRule(BaseModel):
    """
    Brand governance rule extracted from brand guidelines.
    Local validation strictly forbids unknown fields.
    """
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    rule_id: str = Field(..., description="Canonical rule code if given (e.g. FR-RULE-001) or generated code")
    title: str = Field(..., description="Descriptive, concise rule title")
    statement: str = Field(..., description="Concise, complete normative rule requirement or prohibition statement")
    category: Optional[Literal[
        "brand_identity",
        "tone_of_voice",
        "terminology",
        "messaging_and_claims",
        "mandatory_disclosures",
        "product_and_promotions",
        "asset_use",
        "governance_and_escalation",
        "other"
    ]] = Field(default=None, description="Brand governance taxonomy category (optional if in traceability matrix)")
    rule_type: Optional[Literal[
        "prohibition",
        "requirement",
        "restriction",
        "guideline",
        "escalation"
    ]] = Field(default=None, description="Normative nature of the rule (optional if in traceability matrix)")
    severity: Optional[Literal["critical", "high", "medium", "low"]] = Field(
        default=None, description="Violation severity (optional if in traceability matrix)"
    )
    enforcement_action: Optional[Literal[
        "block",
        "flag_for_review",
        "escalate_to_human",
        "warn"
    ]] = Field(default=None, description="Automated platform enforcement action (optional if in traceability matrix)")
    rationale: Optional[str] = Field(default=None, description="Concise governance or legal reason why this rule exists")
    pattern_or_keywords: List[str] = Field(default_factory=list, description="Keywords or phrases triggering this rule")
    context_condition: Optional[str] = Field(None, description="Context condition under which rule applies")
    exceptions: List[str] = Field(default_factory=list, description="Explicit exceptions (e.g. educational disclaimers)")
    scope: Optional[Literal["all_channels", "digital_only", "packaging_only", "print_only", "social_only"]] = Field(
        default="all_channels", description="Channel scope"
    )
    recommended_alternatives: List[str] = Field(default_factory=list, description="Preferred alternative wording")
    examples_bad: List[str] = Field(default_factory=list, description="Non-compliant examples from the document if explicitly present")
    examples_good: List[str] = Field(default_factory=list, description="Compliant examples from the document if explicitly present")
    source_status: Literal["approved", "pending_review", "expired", "rejected", "unknown"] = Field(
        default="unknown", description="Status explicitly assigned to this rule in the source document"
    )
    review_status: Optional[str] = Field(
        default="pending_review", description="Inkloom review status (must always start as pending_review)"
    )
    source_filename: Optional[str] = Field(default=None, description="Source document filename")
    source_page_numbers: List[int] = Field(..., description="1-indexed page numbers where rule is stated")
    supporting_passages: List[str] = Field(..., description="Exact supporting quotation(s) from document")
    evidence_validation: Optional[str] = Field(
        default="explicit_in_document", description="Confidence in direct grounding"
    )
    uncertainty_notes: Optional[str] = Field(None, description="Gaps, ambiguity, or human review reasons")


class StrictProductFact(BaseModel):
    """
    Product attribute, specification, or nutritional metric.
    Explicitly distinguishes stated values from missing_not_provided or external references.
    """
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    product_id: Optional[str] = Field(None, description="Product code (e.g., FS-PROD-001) or null for catalogue-wide")
    product_name: str = Field(..., description="Exact product name or catalogue group")
    attribute: str = Field(..., description="Attribute key (e.g., ingredients, sugars, pack_size, allergen_celery)")
    value: str = Field(..., description="Factual value stated in the document or 'not_provided'")
    unit: Optional[str] = Field(None, description="Physical unit of measure (e.g. mL, g, kcal, %, INR)")
    value_status: Literal[
        "explicitly_stated",
        "missing_not_provided",
        "external_reference_needed",
        "ambiguous"
    ] = Field(default="explicitly_stated", description="Completeness of this specification")
    applicable_conditions: Optional[str] = Field(None, description="Conditions (e.g., per 100 mL, refrigerated 2-5C)")
    source_status: Literal["approved", "pending_review", "expired", "rejected", "unknown"] = Field(
        default="approved", description="Status of this specification in the source document"
    )
    review_status: Optional[str] = Field(
        default="pending_review", description="Inkloom review status (starts as pending_review)"
    )
    source_filename: Optional[str] = Field(default=None, description="Source document filename")
    source_page_numbers: List[int] = Field(..., description="1-indexed page numbers")
    supporting_evidence: str = Field(..., description="Exact text quotation verifying this fact")
    external_reference_needed: Optional[str] = Field(None, description="Referenced external file not in document")


class StrictClaim(BaseModel):
    """
    Marketing claim and its permitted/prohibited/expired/pending decision status.
    """
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    claim_id: Optional[str] = Field(None, description="Claim identifier (e.g., FS-CLAIM-011) if given")
    claim_text: str = Field(..., description="Claim statement or wording")
    claim_category: Literal[
        "health_disease",
        "nutrition",
        "processing_origin",
        "superlative_superiority",
        "environmental_sustainability",
        "pricing_discount",
        "allergen_food_safety",
        "other"
    ] = Field(..., description="Taxonomy of the claim")
    decision: Literal[
        "permitted",
        "prohibited_rejected",
        "pending_human_review",
        "expired"
    ] = Field(..., description="Decision assigned to this claim in the document")
    conditions_or_exceptions: Optional[str] = Field(
        None, description="Conditions or exceptions under which claim is permitted or restricted"
    )
    evidence_or_rationale: str = Field(..., description="Why this claim is permitted, rejected, or pending")
    source_status: Literal["approved", "pending_review", "expired", "rejected", "unknown"] = Field(
        default="unknown", description="Source document status"
    )
    review_status: Optional[str] = Field(
        default="pending_review", description="Inkloom review status"
    )
    source_filename: Optional[str] = Field(default=None, description="Source document filename")
    source_page_numbers: List[int] = Field(..., description="1-indexed page numbers")
    supporting_passages: List[str] = Field(default_factory=list, description="Exact supporting quotations")


class StrictAssetPolicy(BaseModel):
    """
    Written asset policy (e.g., logo clear-space, background pairings, permitted channels).
    """
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    policy_id: Optional[str] = Field(None, description="Parent policy or rule code (e.g., FR-RULE-017)")
    asset_target: str = Field(..., description="Target asset (e.g., Freshsip Brand Logo, Visual Creatives)")
    policy_statement: str = Field(..., description="Mandatory layout, clearance, or usage rule")
    permitted_channels: List[str] = Field(default_factory=list, description="Permitted channels")
    clearance_or_clear_space: Optional[str] = Field(None, description="Specific clearance or margin required")
    color_or_background_guidelines: Optional[str] = Field(None, description="Approved background pairings")
    approval_requirement: str = Field(..., description="Written approval requirement")
    source_status: Literal["approved", "pending_review", "expired", "rejected", "unknown"] = Field(
        default="approved", description="Source document status"
    )
    review_status: Optional[str] = Field(
        default="pending_review", description="Inkloom review status"
    )
    source_filename: Optional[str] = Field(default=None, description="Source document filename")
    source_page_numbers: List[int] = Field(..., description="1-indexed page numbers")
    supporting_passages: List[str] = Field(default_factory=list, description="Supporting quotations")


class StrictDocumentMetadata(BaseModel):
    """
    Document metadata and explicit non-governance exclusions.
    """
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    document_title: str = Field(..., description="Official document title")
    document_id: Optional[str] = Field(None, description="Document code (e.g. FS-GOV-MAN-001)")
    version: Optional[str] = Field(None, description="Document version (e.g. 1.0)")
    effective_date: Optional[str] = Field(None, description="Effective date (YYYY-MM-DD)")
    market: Optional[str] = Field(None, description="Target geographic market")
    non_governance_elements: List[str] = Field(
        default_factory=list,
        description="Elements explicitly identified as informational, examples, or disclaimers"
    )
    external_documents_referenced: List[str] = Field(
        default_factory=list,
        description="External documents referenced (e.g. brand_rules.csv, FS-SPEC-001)"
    )


class StrictKnowledgeDocumentExtraction(BaseModel):
    """
    Root extraction model validated strictly by Inkloom AI backend.
    Any extra or malformed fields will trigger local ValidationError.
    """
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    document_metadata: StrictDocumentMetadata
    brand_rules: List[StrictBrandRule] = Field(default_factory=list)
    product_facts: List[StrictProductFact] = Field(default_factory=list)
    claims: List[StrictClaim] = Field(default_factory=list)
    asset_policies: List[StrictAssetPolicy] = Field(default_factory=list)


# ==============================================================================
# GEMINI API SCHEMA SANITIZER & BUILDER
# ==============================================================================

REDUNDANT_GEMINI_FIELDS = {
    "source_filename",
    "review_status",
    "evidence_validation",
    "scope"
}


def _strip_unsupported_gemini_keys(node: Any) -> Any:
    """
    Recursively removes schema keywords unsupported by Gemini structured output:
    - 'additionalProperties' / 'additional_properties'
    - Redundant repetitive fields ('source_filename', 'review_status', 'evidence_validation', 'scope')
    """
    if isinstance(node, dict):
        cleaned: Dict[str, Any] = {}
        req = node.get("required")
        cleaned_req = [r for r in req if r not in REDUNDANT_GEMINI_FIELDS] if isinstance(req, list) else None

        for k, v in node.items():
            if k in ("additionalProperties", "additional_properties"):
                continue
            if k in REDUNDANT_GEMINI_FIELDS:
                continue
            if k == "properties" and isinstance(v, dict):
                cleaned_props = {
                    pk: _strip_unsupported_gemini_keys(pv)
                    for pk, pv in v.items()
                    if pk not in REDUNDANT_GEMINI_FIELDS
                }
                cleaned[k] = cleaned_props
            elif k == "required" and cleaned_req is not None:
                cleaned[k] = cleaned_req
            else:
                cleaned[k] = _strip_unsupported_gemini_keys(v)
        return cleaned
    elif isinstance(node, list):
        return [_strip_unsupported_gemini_keys(item) for item in node]
    return node


def get_gemini_extraction_response_schema() -> Dict[str, Any]:
    """
    Generates a Gemini API-compliant JSON Schema derived from the strict Pydantic model.
    Strips `additionalProperties` so Gemini API does not return HTTP 400 INVALID_ARGUMENT,
    and omits redundant fields (like filename and review status) to minimize generation latency.
    The response from Gemini is then validated against StrictKnowledgeDocumentExtraction
    with extra="forbid" to ensure absolute local data integrity.
    """
    raw_schema = StrictKnowledgeDocumentExtraction.model_json_schema()
    sanitized = _strip_unsupported_gemini_keys(copy.deepcopy(raw_schema))
    return sanitized

