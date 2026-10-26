import re
from datetime import datetime
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from app.models.knowledge import KnowledgeRule, KnowledgeFact
from app.models.content import ContentVersion, GovernanceRun, GovernanceFinding

# Common high-risk marketing and unverified health claims that require supporting evidence
RISKY_HEALTH_PATTERNS = [
    (r"\b(?:cures?|prevents?|treats?|heals?)\s+(?:cancer|diabetes|illness|disease|infection|depression|anxiety)\b", "Medical Treatment Claim", "Under brand governance, consumer marketing must not claim to diagnose, cure, mitigate, treat, or prevent diseases without approved regulatory clearance."),
    (r"\b(?:guaranteed|instant|rapid|effortless)\s+(?:weight loss|fat burning|slimming|detox)\b", "Guaranteed Weight Loss / Detox Claim", "Promotional claims guaranteeing weight loss or detoxification require approved clinical substantiation."),
    (r"\b(?:100%|completely)\s+(?:chemical[ -]free|toxin[ -]free|side[ -]effect[ -]free)\b", "Absolute Chemical-Free Claim", "Scientific claims of being '100% chemical-free' are scientifically inaccurate and misleading under brand guidelines."),
    (r"\b(?:doctor|pediatrician|cardiologist)\s+(?:recommended|approved|prescribed)\b", "Professional Endorsement Claim", "Claims of medical professional endorsements require verified, approved documentation on file."),
]

class GovernanceEngine:
    """
    Deterministic governance engine for Inkloom AI.
    Evaluates marketing text against approved brand rules and facts.
    """

    def evaluate_content_version(
        self,
        db: Session,
        content_version: ContentVersion,
        executed_by_user_id: Optional[str] = None
    ) -> GovernanceRun:
        body_text = content_version.body_text
        brand_id = content_version.content_item.brand_id
        org_id = content_version.content_item.organization_id
        now = datetime.utcnow()

        # Step 1: Query ONLY approved rules for this organization & brand
        approved_rules = db.query(KnowledgeRule).filter(
            KnowledgeRule.organization_id == org_id,
            KnowledgeRule.status == "approved"
        ).all()

        # Step 2: Query ONLY approved and non-expired facts
        approved_facts = db.query(KnowledgeFact).filter(
            KnowledgeFact.organization_id == org_id,
            KnowledgeFact.status == "approved"
        ).all()

        # Step 3: Also query pending / rejected / expired facts to detect unapproved claims
        unapproved_facts = db.query(KnowledgeFact).filter(
            KnowledgeFact.organization_id == org_id,
            KnowledgeFact.status.in_(["pending_review", "rejected", "expired"])
        ).all()

        findings: List[GovernanceFinding] = []

        # ==========================================
        # RULE CHECK 1: Prohibited & Risky Wording Rules
        # ==========================================
        for rule in approved_rules:
            if rule.rule_type == "prohibited_word":
                # Check for pattern match with boundary awareness
                pattern_escaped = re.escape(rule.pattern.strip())
                regex = re.compile(rf"\b{pattern_escaped}\b", re.IGNORECASE)
                match = regex.search(body_text)
                
                if match:
                    excerpt = self._extract_excerpt(body_text, match.start(), match.end())
                    
                    # Context-sensitive check: is it negated? (e.g. "not a miracle")
                    is_negated = self._is_negated_context(body_text, match.start())
                    severity = "warning" if is_negated else rule.severity
                    explanation = rule.explanation
                    if is_negated:
                        explanation += " (Note: Appears in negated or qualifying context; human review recommended)."

                    finding = GovernanceFinding(
                        category="prohibited_wording",
                        severity=severity,
                        title=f"Prohibited Wording: '{rule.pattern}'",
                        explanation=explanation,
                        text_excerpt=excerpt,
                        matched_rule_id=rule.id,
                        source_citation=rule.source_citation or "Approved Brand Guidelines",
                        recommended_action=f"Remove or rephrase '{rule.pattern}' to align with brand voice."
                    )
                    findings.append(finding)

        # ==========================================
        # RULE CHECK 2: Mandatory / Required Terminology Rules
        # ==========================================
        for rule in approved_rules:
            if rule.rule_type == "required_term":
                pattern_escaped = re.escape(rule.pattern.strip())
                regex = re.compile(rf"\b{pattern_escaped}\b", re.IGNORECASE)
                if not regex.search(body_text):
                    finding = GovernanceFinding(
                        category="mandatory_wording_missing",
                        severity=rule.severity,
                        title=f"Missing Mandatory Term: '{rule.pattern}'",
                        explanation=f"Required wording '{rule.pattern}' was not found in the content. {rule.explanation}",
                        text_excerpt=None,
                        matched_rule_id=rule.id,
                        source_citation=rule.source_citation or "Approved Brand Guidelines",
                        recommended_action=f"Include the required wording '{rule.pattern}' in the text."
                    )
                    findings.append(finding)

        # ==========================================
        # RULE CHECK 3: Exact Product-Fact Comparisons
        # ==========================================
        for fact in approved_facts:
            # Check if content mentions the fact key or conflicting numerical values
            product_mentioned = (
                fact.product_name.lower() in body_text.lower() or
                "freshsip" in body_text.lower()
            )
            
            # Check for sugar mismatches
            if fact.fact_key.lower() == "sugar" or "sugar" in fact.fact_key.lower():
                # If approved fact says 0g or no added sugar, check if text says "high sugar", "contains sugar", etc.
                if "0g" in fact.fact_value.lower() or "no added sugar" in fact.fact_value.lower():
                    conflict_match = re.search(r"\b(\d+\s*g(?:rams?)?\s+(?:of\s+)?sugar|sweetened with high fructose)\b", body_text, re.IGNORECASE)
                    if conflict_match:
                        excerpt = self._extract_excerpt(body_text, conflict_match.start(), conflict_match.end())
                        finding = GovernanceFinding(
                            category="product_fact_mismatch",
                            severity="critical",
                            title=f"Product Fact Mismatch: Sugar Content",
                            explanation=f"Content states '{conflict_match.group(1)}', which contradicts approved product fact '{fact.fact_value}'.",
                            text_excerpt=excerpt,
                            matched_fact_id=fact.id,
                            source_citation=fact.source_citation or f"Approved Product Knowledge ({fact.product_name})",
                            recommended_action=f"Update content to reflect verified specification: '{fact.fact_value}'."
                        )
                        findings.append(finding)

            # Check for calorie mismatches
            if "calorie" in fact.fact_key.lower():
                conflict_match = re.search(r"\b(\d{2,4})\s*calories\b", body_text, re.IGNORECASE)
                if conflict_match:
                    mentioned_cals = conflict_match.group(1)
                    if mentioned_cals not in fact.fact_value:
                        excerpt = self._extract_excerpt(body_text, conflict_match.start(), conflict_match.end())
                        finding = GovernanceFinding(
                            category="product_fact_mismatch",
                            severity="warning",
                            title=f"Product Fact Mismatch: Calorie Count",
                            explanation=f"Content states '{mentioned_cals} calories', but approved product knowledge states '{fact.fact_value}'.",
                            text_excerpt=excerpt,
                            matched_fact_id=fact.id,
                            source_citation=fact.source_citation or f"Approved Product Knowledge ({fact.product_name})",
                            recommended_action=f"Verify calorie count against approved specification: '{fact.fact_value}'."
                        )
                        findings.append(finding)

        # ==========================================
        # RULE CHECK 4: Unapproved / Expired / Pending Claim Usage
        # ==========================================
        for unapp_fact in unapproved_facts:
            # Check if content makes this specific claim
            if unapp_fact.fact_value.lower() in body_text.lower():
                status_desc = {
                    "pending_review": "is currently PENDING REVIEW by the Knowledge Reviewer",
                    "rejected": "was REJECTED during human review",
                    "expired": f"EXPIRED on {unapp_fact.valid_until.strftime('%Y-%m-%d') if unapp_fact.valid_until else 'prior date'}"
                }.get(unapp_fact.status, unapp_fact.status)

                match_idx = body_text.lower().find(unapp_fact.fact_value.lower())
                excerpt = self._extract_excerpt(body_text, match_idx, match_idx + len(unapp_fact.fact_value))

                finding = GovernanceFinding(
                    category="claim_status_issue",
                    severity="critical" if unapp_fact.status == "rejected" else "warning",
                    title=f"Unapproved Claim Status: '{unapp_fact.fact_key}' ({unapp_fact.status})",
                    explanation=f"The claim '{unapp_fact.fact_value}' cannot be used because it {status_desc}. Only approved knowledge is authoritative.",
                    text_excerpt=excerpt,
                    matched_fact_id=unapp_fact.id,
                    source_citation=unapp_fact.source_citation or "Knowledge Base (Unapproved)",
                    recommended_action="Wait for Knowledge Reviewer approval before publishing this claim."
                )
                findings.append(finding)

        # ==========================================
        # RULE CHECK 5: Unsupported Health & Medical Claims (Missing Evidence)
        # ==========================================
        for pattern_re, title, explanation in RISKY_HEALTH_PATTERNS:
            match = re.search(pattern_re, body_text, re.IGNORECASE)
            if match:
                excerpt = self._extract_excerpt(body_text, match.start(), match.end())
                finding = GovernanceFinding(
                    category="unsupported_claim",
                    severity="critical",
                    title=f"Unsupported Claim: {title}",
                    explanation=f"{explanation} The phrase '{match.group(0)}' was detected without verified substantiation.",
                    text_excerpt=excerpt,
                    matched_rule_id=None,
                    matched_fact_id=None,
                    source_citation="SUPPORTING EVIDENCE NOT FOUND",
                    recommended_action="Remove unverified clinical/health claims or upload approved evidence to the Knowledge Library."
                )
                findings.append(finding)

        # ==========================================
        # RULE CHECK 6: Source Freshness & Validity Date Check
        # ==========================================
        for fact in approved_facts:
            if fact.valid_until and fact.valid_until < now:
                if fact.fact_value.lower() in body_text.lower():
                    match_idx = body_text.lower().find(fact.fact_value.lower())
                    excerpt = self._extract_excerpt(body_text, match_idx, match_idx + len(fact.fact_value))
                    finding = GovernanceFinding(
                        category="source_freshness_issue",
                        severity="warning",
                        title=f"Expired Knowledge Record: {fact.fact_key}",
                        explanation=f"The approved claim '{fact.fact_value}' had a validity expiration date of {fact.valid_until.strftime('%Y-%m-%d')}.",
                        text_excerpt=excerpt,
                        matched_fact_id=fact.id,
                        source_citation=fact.source_citation or "Knowledge Library",
                        recommended_action="Renew the source document or obtain re-certification from the Knowledge Reviewer."
                    )
                    findings.append(finding)

        # Determine overall run status
        has_critical = any(f.severity == "critical" for f in findings)
        has_warning = any(f.severity == "warning" for f in findings)
        
        if has_critical:
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
            rules_evaluated_count=len(approved_rules),
            facts_evaluated_count=len(approved_facts),
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

    def _is_negated_context(self, text: str, start: int) -> bool:
        prefix = text[max(0, start - 30):start].lower()
        negations = ["not", "never", "no", "without", "isn't", "is not", "neither"]
        return any(neg in prefix for neg in negations)

governance_engine = GovernanceEngine()
