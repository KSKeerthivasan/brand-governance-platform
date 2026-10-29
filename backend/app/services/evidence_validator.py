"""
Evidence and Passage Validator for Inkloom AI.

Validates that extracted candidate passages and citations are grounded in the source PDF.
Does NOT claim evidence validation is proof of semantic correctness; rather, it verifies
that cited pages and textual passages physically exist in the uploaded document, and checks
for explicit contradictions between extracted values/metadata and source text.
"""

import re
from typing import List, Dict, Any, Tuple, Optional
from pypdf import PdfReader


def extract_pdf_pages(file_path: str) -> List[str]:
    """
    Extracts raw text per page from a PDF file using pypdf.
    Returns a list of strings where index 0 is Page 1.
    """
    try:
        with open(file_path, "rb") as f:
            reader = PdfReader(f)
            pages = []
            for p in reader.pages:
                txt = p.extract_text() or ""
                pages.append(txt)
            return pages
    except Exception as e:
        return [f"[Error reading page: {e}]"]


def normalize_text(text: str) -> str:
    """
    Normalizes typography artifacts: smart quotes, unicode dashes, intra-word spacing,
    and multiple whitespace sequences.
    """
    if not text:
        return ""
    text = text.replace("“", '"').replace("”", '"').replace("‘", "'").replace("’", "'")
    text = text.replace("—", "-").replace("–", "-").replace("•", " ")
    text = re.sub(r'([a-zA-Z])\s+([a-zA-Z])', r'\1 \2', text)
    text = re.sub(r'\s+', ' ', text)
    return text.lower().strip()


def _fuzzy_search(needle: str, haystack: str) -> bool:
    """
    Checks if needle appears in haystack after alphanumeric normalization.
    """
    norm_n = re.sub(r'[^a-z0-9]', '', normalize_text(needle))
    norm_h = re.sub(r'[^a-z0-9]', '', normalize_text(haystack))
    if not norm_n or not norm_h:
        return False
    window_len = min(len(norm_n), 35)
    return norm_n[:window_len] in norm_h


class EvidenceValidationResult:
    def __init__(
        self,
        validation_status: str,  # verified_exact, verified_fuzzy, page_mismatch, unverified, unsupported_value, contradiction
        verified_page: Optional[int] = None,
        notes: Optional[str] = None
    ):
        self.validation_status = validation_status
        self.verified_page = verified_page
        self.notes = notes


def validate_candidate_evidence(
    passages: List[str],
    cited_page_numbers: List[int],
    pdf_pages: List[str]
) -> EvidenceValidationResult:
    """
    Validates a list of supporting passages against the PDF pages.
    """
    total_pages = len(pdf_pages)
    if not passages or not any(p.strip() for p in passages):
        return EvidenceValidationResult(
            validation_status="unverified",
            notes="No supporting passage was provided for this candidate."
        )

    # Validate page bounds
    valid_cited_pages = [p for p in cited_page_numbers if 1 <= p <= total_pages]
    if not valid_cited_pages and cited_page_numbers:
        return EvidenceValidationResult(
            validation_status="unverified",
            notes=f"Cited page(s) {cited_page_numbers} out of bounds (PDF has {total_pages} pages)."
        )

    for passage in passages:
        if not passage.strip():
            continue
        norm_passage = normalize_text(passage)
        
        # 1. Try exact normalized match on cited pages
        for pnum in valid_cited_pages:
            page_text = pdf_pages[pnum - 1]
            norm_page = normalize_text(page_text)
            if passage.strip() in page_text or norm_passage in norm_page:
                return EvidenceValidationResult(
                    validation_status="verified_exact",
                    verified_page=pnum,
                    notes=f"Passage match confirmed on Page {pnum}."
                )

        # 2. Try fuzzy search on cited pages
        for pnum in valid_cited_pages:
            page_text = pdf_pages[pnum - 1]
            if _fuzzy_search(passage, page_text):
                return EvidenceValidationResult(
                    validation_status="verified_fuzzy",
                    verified_page=pnum,
                    notes=f"Passage confirmed on Page {pnum} (normalized whitespace/typography match)."
                )

        # 3. Check across other pages in the document
        for idx, page_text in enumerate(pdf_pages, 1):
            if idx not in valid_cited_pages:
                norm_page = normalize_text(page_text)
                if passage.strip() in page_text or norm_passage in norm_page or _fuzzy_search(passage, page_text):
                    return EvidenceValidationResult(
                        validation_status="page_mismatch",
                        verified_page=idx,
                        notes=f"Passage found on Page {idx} (model cited Page {cited_page_numbers})."
                    )

    return EvidenceValidationResult(
        validation_status="unverified",
        notes="Supporting passage could not be verified in the document text stream."
    )


def validate_fact_consistency(
    value: str,
    unit: Optional[str],
    supporting_evidence: str,
    page_text: Optional[str] = None
) -> Tuple[str, Optional[str]]:
    """
    Checks for contradictions and ungrounded claims between an extracted product fact
    and its supporting evidence / page text.
    
    Returns:
        (consistency_status, note)
        where status is 'consistent', 'data_gap', 'unsupported_value', or 'contradiction'.
    """
    val_clean = value.strip().lower()
    if val_clean in ("not_provided", "missing", "none", "unknown"):
        return ("data_gap", "Attribute is an explicit data gap (not_provided).")

    combined_text = normalize_text(f"{supporting_evidence} {page_text or ''}")

    # 1. Contradiction check: Packaging format (can vs bottle / aluminum vs glass)
    if any(k in val_clean for k in ("can", "aluminum", "tin")):
        if any(k in combined_text for k in ("glass bottle", "bottled", "glass-bottled")):
            return (
                "contradiction",
                f"Contradiction: Extracted value claims '{value}', but source explicitly specifies glass bottles."
            )

    # 2. Check numeric quantities in value
    # Extract numbers like 250, 330, 95, 130, 55, 14, 28, etc.
    num_matches = re.findall(r'\b\d+(?:\.\d+)?\b', val_clean)
    if num_matches:
        for num in num_matches:
            # Check if this exact number exists in the source text
            # Normalize source text numbers
            if not re.search(rf'\b{re.escape(num)}\b', combined_text):
                return (
                    "unsupported_value",
                    f"Unsupported numeric value: Number '{num}' in extracted value '{value}' was not found in supporting passage or page."
                )

    # 3. Unit consistency check
    if unit:
        u_clean = unit.strip().lower()
        if u_clean in ("ml", "g", "kcal", "%", "days"):
            if u_clean not in combined_text and not _fuzzy_search(u_clean, combined_text):
                # Only flag if not found in combined text
                return (
                    "unsupported_value",
                    f"Unit '{unit}' not found in supporting passage."
                )

    return ("consistent", None)


def extract_rule_traceability_matrix(pdf_pages: List[str]) -> Dict[str, Dict[str, Any]]:
    """
    Extracts structured rule metadata deterministically from the document text
    when an explicit Rule Traceability Matrix or structured table is present.
    
    Returns a dictionary mapping canonical rule_code (e.g. 'FR-RULE-001') to:
    {
        "rule_code": str,
        "title": str,
        "category": str,
        "rule_type": str,
        "severity": str,
        "enforcement_action": str,
        "section": Optional[str],
        "source_status": str,
        "is_deterministic": True
    }
    
    If no matrix is present, returns an empty dictionary, allowing semantic
    fallback without guessing.
    """
    if not pdf_pages:
        return {}

    full_text = "\n".join(pdf_pages)
    matrix: Dict[str, Dict[str, Any]] = {}

    pattern = re.compile(
        r'([A-Z]{2,6}-RULE-\d{2,4})\s+'
        r'([\s\S]*?)'
        r'([a-z_]+)\s*\((requirement|prohibition|restriction|guideline|escalation)\)\s+'
        r'(critical|high|medium|low)\s*(?:/|—|-)\s*([a-z_ ]+?)\s+'
        r'(?:Section\s*([A-Z0-9]+)\s+)?'
        r'(approved|pending_review|expired|rejected|unknown)',
        re.IGNORECASE
    )

    valid_cats = {
        "brand_identity", "tone_of_voice", "terminology",
        "messaging_and_claims", "mandatory_disclosures",
        "product_and_promotions", "asset_use", "governance_and_escalation", "other"
    }
    valid_types = {"requirement", "prohibition", "restriction", "guideline", "escalation"}
    valid_sevs = {"critical", "high", "medium", "low"}
    valid_acts = {"block", "warn", "flag_for_review", "escalate_to_human"}

    for m in pattern.finditer(full_text):
        rule_id = m.group(1).upper()
        raw_name = m.group(2)
        cleaned_title = re.sub(r'-\s+', '-', raw_name)
        cleaned_title = ' '.join(cleaned_title.split())
        
        cat = m.group(3).lower().strip()
        rtype = m.group(4).lower().strip()
        sev = m.group(5).lower().strip()
        act_raw = m.group(6).lower().strip()
        act = re.sub(r'\s+', '_', act_raw)
        sec = m.group(7).upper() if m.group(7) else None
        stat = m.group(8).lower().strip()

        if cat in valid_cats and rtype in valid_types and sev in valid_sevs and act in valid_acts:
            matrix[rule_id] = {
                "rule_code": rule_id,
                "title": cleaned_title,
                "category": cat,
                "rule_type": rtype,
                "severity": sev,
                "enforcement_action": act,
                "section": sec,
                "source_status": stat,
                "is_deterministic": True
            }

    return matrix


def validate_rule_consistency(
    rule_id: str,
    severity: str,
    enforcement_action: str,
    supporting_passages: List[str],
    page_text: Optional[str] = None,
    document_text: Optional[str] = None,
    known_matrix: Optional[Dict[str, Any]] = None
) -> Tuple[str, Optional[str]]:
    """
    Validates that extracted rule metadata (rule_id, severity, enforcement_action) matches
    the source document's explicit notation, avoiding cross-rule false alarms on multi-rule pages.
    
    Rule-Specific Matching Principles:
    1. Prefer rule's own supporting passage(s) and explicit rule heading.
    2. If rule ID is mentioned in the supporting passage, verify that candidate rule_id matches.
    3. If searching page text, scope specifically to this rule's heading or row (forward slice).
    4. Validate severity and enforcement action against this rule's scoped entry or traceability matrix.
    5. Distinguish genuine conflicts from multi-rule page noise.
    
    Returns:
        (consistency_status, note)
    """
    norm_passages = normalize_text(" ".join(supporting_passages))

    # Base canonical rule code (e.g., 'FR-RULE-017' from 'FR-RULE-017-AP01')
    base_match = re.match(r'^(FR-RULE-\d{3})', rule_id, re.IGNORECASE)
    base_rule_id = base_match.group(1).upper() if base_match else rule_id.upper()

    # 1. Rule ID check in supporting passage:
    # If the passage explicitly quotes a rule code (e.g. 'FR-RULE-002'), verify that it matches base_rule_id.
    passage_rule_matches = re.findall(r'\b(fr-rule-\d{3})\b', norm_passages, re.IGNORECASE)
    if passage_rule_matches:
        passage_codes = [c.upper() for c in passage_rule_matches]
        if base_rule_id not in passage_codes:
            # Check if passage states a governing rule declaration (e.g. "Under FR-RULE-002" or "Rule FR-RULE-002")
            gov_match = re.search(r'\b(?:under|rule|section)\s+(fr-rule-\d{3})\b', norm_passages, re.IGNORECASE)
            if gov_match:
                gov_code = gov_match.group(1).upper()
                if gov_code != base_rule_id:
                    return (
                        "rule_metadata_conflict",
                        f"Rule ID mismatch: Supporting passage explicitly specifies governing '{gov_code}', but candidate is labeled '{rule_id}'."
                    )
            elif not (page_text and base_rule_id.lower() in page_text.lower()):
                return (
                    "rule_metadata_conflict",
                    f"Rule ID mismatch: Supporting passage cites {passage_codes}, and '{base_rule_id}' was not found on cited page."
                )

    # 2. Known Traceability Matrix Check (Deterministic Verification)
    if known_matrix and base_rule_id in known_matrix:
        exp_meta = known_matrix[base_rule_id]
        exp_sev = exp_meta.get("severity", "").lower()
        exp_act = exp_meta.get("enforcement_action", "").lower().replace(" ", "_")
        cur_sev = severity.lower()
        cur_act = enforcement_action.lower().replace(" ", "_")

        mismatches = []
        if exp_sev and cur_sev != exp_sev:
            mismatches.append(f"severity is '{severity}' (source specifies '{exp_sev}')")
        if exp_act and cur_act != exp_act:
            mismatches.append(f"action is '{enforcement_action}' (source specifies '{exp_act}')")

        if mismatches:
            return (
                "rule_metadata_conflict",
                f"Rule matrix conflict: {rule_id} specifies '{exp_sev} / {exp_act}', but candidate assigned '{cur_sev} / {cur_act}'."
            )
        return ("consistent", None)

    # 3. Scoped Severity and Enforcement Action Validation:
    # Look for explicit severity/action notation: (High / Block), (Critical / Flag for Review), etc.
    sev_act_pattern = r'\b(critical|high|medium|low)\s*(?:/|—|-)\s*(block|warn|flag[ _]for[ _]review|escalate_to_human)\b'
    scoped_text: Optional[str] = None

    # Priority A: Check if rule's own supporting passage contains severity/action notation
    m_passage = re.search(sev_act_pattern, norm_passages, re.IGNORECASE)
    if m_passage:
        scoped_text = m_passage.group(0)

    # Priority B: If not in passage, search forward from base_rule_id on cited page
    if not scoped_text and page_text:
        idx = page_text.lower().find(base_rule_id.lower())
        if idx != -1:
            snippet = page_text[idx:idx + 250]
            # Clip at next rule ID if present to avoid cross-rule bleed
            next_rule = re.search(r'\bfr-rule-\d{3}\b', snippet[len(base_rule_id):], re.IGNORECASE)
            if next_rule:
                snippet = snippet[:len(base_rule_id) + next_rule.start()]
            m_page = re.search(sev_act_pattern, snippet, re.IGNORECASE)
            if m_page:
                scoped_text = m_page.group(0)

    # Priority C: If not on cited page, search in document text (Traceability Matrix on pages 5-8)
    if not scoped_text and document_text:
        for m in re.finditer(rf'\b{re.escape(base_rule_id)}\b', document_text, re.IGNORECASE):
            idx = m.start()
            snippet = document_text[idx:idx + 250]
            next_rule = re.search(r'\bfr-rule-\d{3}\b', snippet[len(base_rule_id):], re.IGNORECASE)
            if next_rule:
                snippet = snippet[:len(base_rule_id) + next_rule.start()]
            m_doc = re.search(sev_act_pattern, snippet, re.IGNORECASE)
            if m_doc:
                scoped_text = m_doc.group(0)
                break

    # If a rule-specific severity/action pair was found, compare against candidate values
    if scoped_text:
        m = re.search(sev_act_pattern, scoped_text, re.IGNORECASE)
        if m:
            exp_sev = m.group(1).lower()
            exp_act = m.group(2).lower().replace(" ", "_")
            cur_sev = severity.lower()
            cur_act = enforcement_action.lower().replace(" ", "_")

            mismatches = []
            if cur_sev != exp_sev:
                mismatches.append(f"severity is '{severity}' (source specifies '{exp_sev}')")
            if cur_act != exp_act:
                mismatches.append(f"action is '{enforcement_action}' (source specifies '{exp_act}')")

            if mismatches:
                return (
                    "rule_metadata_conflict",
                    f"Rule matrix conflict: {rule_id} specifies '{exp_sev} / {exp_act}', but candidate assigned '{cur_sev} / {cur_act}'."
                )

    return ("consistent", None)

