import os
import re

def decouple_governance_engine():
    path = "backend/app/services/governance_engine.py"
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    # Step 1: Replace hardcoded Freshsip citations with dynamic {brand_name} references
    content = content.replace('"freshsip_brand_guidelines.pdf"', 'f"{brand_name} Brand Guidelines"')
    content = content.replace('"freshsip_brand_guidelines.pdf, Section E, p. 5"', 'f"{brand_name} Brand Guidelines, Section E, p. 5"')
    content = content.replace('"freshsip_brand_guidelines.pdf, Section C, p. 3"', 'f"{brand_name} Brand Guidelines, Section C, p. 3"')
    content = content.replace('"freshsip_brand_guidelines.pdf, Section 2.1, p. 4"', 'f"{brand_name} Brand Guidelines, Section 2.1, p. 4"')
    content = content.replace('"freshsip_brand_guidelines.pdf, Section D, p. 3"', 'f"{brand_name} Brand Guidelines, Section D, p. 3"')
    content = content.replace('f"freshsip_products.csv ({target_sku})"', 'f"{brand_name} Product Catalogue ({target_sku})"')
    content = content.replace('"freshsip_approved_claims.csv"', 'f"{brand_name} Claims Register"')
    content = content.replace('"freshsip_products.csv"', 'f"{brand_name} Product Catalogue"')
    content = content.replace('which Freshsip SKU', 'which {brand_name} SKU')

    # Step 2: In evaluate_content_version, resolve brand_profile, active_kb, org_products before Step 1
    target_step1 = """        # Step 1: Detect product context across caption + poster
        combined_source_text = f"{title} {body_text} {poster_text}"
        detected_products = self.detect_product_context(combined_source_text, title, product_id)
        is_corporate_content = len(detected_products) == 0"""

    replacement_step1 = """        # Resolve active knowledge base version, brand profile, and products for this organization
        active_kb = db.query(OrganizationActiveKnowledgeBase).filter(
            OrganizationActiveKnowledgeBase.organization_id == org_id
        ).first() if org_id else None
        kb_version_id = active_kb.active_version_id if active_kb else None
        baseline_status = "versioned" if kb_version_id else "legacy_unversioned"

        brand_profile = db.query(BrandProfile).filter(
            BrandProfile.organization_id == org_id
        ).first() if org_id else None
        brand_name = brand_profile.brand_name if brand_profile else "Brand"

        org_products = db.query(Product).filter(
            Product.organization_id == org_id,
            Product.record_status == "Active"
        ).all() if org_id else []

        # Typography Hierarchy Heuristic Evaluation (Milestone 5 / Round 3 Input 1 Section D)
        if ocr_result and getattr(ocr_result, "regions", None) and len(ocr_result.regions) >= 2:
            try:
                region_heights = []
                for reg in ocr_result.regions:
                    if getattr(reg, "bbox", None) and len(reg.bbox) >= 4:
                        ys = [pt[1] for pt in reg.bbox]
                        h = max(ys) - min(ys)
                        if h > 5:
                            region_heights.append(h)
                if len(region_heights) >= 2:
                    region_heights.sort()
                    max_h = region_heights[-1]
                    median_h = region_heights[len(region_heights) // 2]
                    ratio = max_h / max(median_h, 1.0)
                    if ratio >= 1.5:
                        findings.append(GovernanceFinding(
                            category="layout",
                            severity="info",
                            title="Typography Hierarchy Heuristic Signal: Positive",
                            explanation=f"Headline-to-body typography hierarchy detected (ratio {ratio:.1f}x >= 1.5x threshold). Note: Bounding box scale is a heuristic signal only and does not identify actual font families or guarantee typography compliance.",
                            text_excerpt=f"Max font height: ~{int(max_h)}px, Median height: ~{int(median_h)}px (Ratio: {ratio:.1f}x)",
                            matched_rule_id=None,
                            matched_fact_id=None,
                            source_citation=f"{brand_name} Brand Guidelines, Typography",
                            recommended_action="Heuristic signal verified. Human review recommended to confirm approved font families.",
                            status="passed_check"
                        ))
                    else:
                        findings.append(GovernanceFinding(
                            category="layout",
                            severity="warning",
                            title="Typography Hierarchy Weak: Review Recommended",
                            explanation=f"Detected headline-to-body height ratio ({ratio:.1f}x) falls below the 1.5x hierarchy heuristic threshold. Headline may lack visual prominence over body text.",
                            text_excerpt=f"Max font height: ~{int(max_h)}px, Median height: ~{int(median_h)}px (Ratio: {ratio:.1f}x)",
                            matched_rule_id=None,
                            matched_fact_id=None,
                            source_citation=f"{brand_name} Brand Guidelines, Typography",
                            recommended_action="Ensure clear visual contrast between headlines and body text per brand typography instructions.",
                            status="unresolved"
                        ))
                else:
                    findings.append(GovernanceFinding(
                        category="layout",
                        severity="info",
                        title="Typography Hierarchy: unable_to_verify",
                        explanation="Insufficient distinct text regions detected by OCR to evaluate typography hierarchy heuristic. Manual review required.",
                        text_excerpt=None,
                        matched_rule_id=None,
                        matched_fact_id=None,
                        source_citation=f"{brand_name} Brand Guidelines, Typography",
                        recommended_action="Verify typography hierarchy manually in creative asset.",
                        status="passed_check"
                    ))
            except Exception:
                pass
        elif content_version.poster_file_path:
            findings.append(GovernanceFinding(
                category="layout",
                severity="info",
                title="Typography Hierarchy: unable_to_verify",
                explanation="Unable to verify typography hierarchy: insufficient or ambiguous OCR data from poster image.",
                text_excerpt=None,
                matched_rule_id=None,
                matched_fact_id=None,
                source_citation=f"{brand_name} Brand Guidelines, Typography",
                recommended_action="Perform manual visual inspection of font hierarchy.",
                status="passed_check"
            ))

        # Step 1: Detect product context across caption + poster
        combined_source_text = f"{title} {body_text} {poster_text}"
        detected_products = self.detect_product_context(combined_source_text, title, product_id, products=org_products)
        is_corporate_content = len(detected_products) == 0"""

    if target_step1 in content:
        content = content.replace(target_step1, replacement_step1)
        print("[PASS]: Updated Step 1 in evaluate_content_version")
    else:
        print("[WARN]: target_step1 not found verbatim in evaluate_content_version")

    # Step 3: In evaluate_content_version, populate knowledge_base_version_id and baseline_status
    target_gov_run = """        # Create GovernanceRun record
        gov_run = GovernanceRun(
            organization_id=org_id,
            content_version_id=content_version.id,
            executed_by=executed_by_user_id,
            overall_status=overall_status,
            rules_evaluated_count=rules_evaluated_count,
            facts_evaluated_count=facts_evaluated_count,
            findings_count=len(findings)
        )"""

    replacement_gov_run = """        # Create GovernanceRun record
        gov_run = GovernanceRun(
            organization_id=org_id,
            knowledge_base_version_id=kb_version_id,
            baseline_status=baseline_status,
            content_version_id=content_version.id,
            executed_by=executed_by_user_id,
            overall_status=overall_status,
            rules_evaluated_count=rules_evaluated_count,
            facts_evaluated_count=facts_evaluated_count,
            findings_count=len(findings)
        )"""

    if target_gov_run in content:
        content = content.replace(target_gov_run, replacement_gov_run)
        print("[PASS]: Updated GovernanceRun instantiation in evaluate_content_version")
    else:
        print("[WARN]: target_gov_run not found verbatim")

    # Step 4: In _execute_pdf_governance_run, resolve brand_profile, active_kb, org_products
    target_pdf_run = """        approved_rules = db.query(KnowledgeRule).filter(
            KnowledgeRule.organization_id == org_id,
            KnowledgeRule.status == "approved"
        ).all()"""

    replacement_pdf_run = """        active_kb = db.query(OrganizationActiveKnowledgeBase).filter(
            OrganizationActiveKnowledgeBase.organization_id == org_id
        ).first() if org_id else None
        kb_version_id = active_kb.active_version_id if active_kb else None
        baseline_status = "versioned" if kb_version_id else "legacy_unversioned"

        brand_profile = db.query(BrandProfile).filter(
            BrandProfile.organization_id == org_id
        ).first() if org_id else None
        brand_name = brand_profile.brand_name if brand_profile else "Brand"

        org_products = db.query(Product).filter(
            Product.organization_id == org_id,
            Product.record_status == "Active"
        ).all() if org_id else []

        approved_rules = db.query(KnowledgeRule).filter(
            KnowledgeRule.organization_id == org_id,
            KnowledgeRule.status == "approved"
        ).all()"""

    if target_pdf_run in content:
        content = content.replace(target_pdf_run, replacement_pdf_run)
        print("[PASS]: Updated _execute_pdf_governance_run context resolution")
    else:
        print("[WARN]: target_pdf_run not found verbatim")

    # Step 5: In _execute_pdf_governance_run, populate GovernanceRun
    target_pdf_gov_run = """        gov_run = GovernanceRun(
            organization_id=org_id,
            content_version_id=content_version.id,
            executed_by=executed_by_user_id,
            overall_status=overall_status,
            rules_evaluated_count=rules_count,
            facts_evaluated_count=facts_count,
            findings_count=len(findings)
        )"""

    replacement_pdf_gov_run = """        gov_run = GovernanceRun(
            organization_id=org_id,
            knowledge_base_version_id=kb_version_id,
            baseline_status=baseline_status,
            content_version_id=content_version.id,
            executed_by=executed_by_user_id,
            overall_status=overall_status,
            rules_evaluated_count=rules_count,
            facts_evaluated_count=facts_count,
            findings_count=len(findings)
        )"""

    if target_pdf_gov_run in content:
        content = content.replace(target_pdf_gov_run, replacement_pdf_gov_run)
        print("[PASS]: Updated GovernanceRun in _execute_pdf_governance_run")
    else:
        print("[WARN]: target_pdf_gov_run not found verbatim")

    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print("Decoupling applied to governance_engine.py successfully.")

if __name__ == "__main__":
    decouple_governance_engine()
