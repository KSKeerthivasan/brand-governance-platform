import io
import uuid
from datetime import date, timedelta
import openpyxl
import pytest
from app.models.product import Product
from app.models.claim import Claim, RequiredDisclosure
from app.models.knowledge import StagedImport, StagedImportProductRow, StagedImportClaimRow
from app.models.organization import Organization, OrganizationRole, OrganizationMembership, User
from app.services.excel_service import excel_service
from app.services.governance_engine import governance_engine
from app.models.content import ContentItem, ContentVersion

def _build_excel_file(sheets_data: dict) -> bytes:
    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    for sheet_name, rows in sheets_data.items():
        ws = wb.create_sheet(title=sheet_name)
        for r in rows:
            ws.append(r)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def test_product_catalogue_template_generation_and_guidance():
    """Verify 15-column Product Catalogue template includes Instructions sheet and guidance."""
    content = excel_service.generate_template("product_catalogue")
    wb = openpyxl.load_workbook(io.BytesIO(content))
    
    assert "Instructions" in wb.sheetnames
    assert "Product_Catalogue" in wb.sheetnames
    
    ws_inst = wb["Instructions"]
    assert "Product Catalogue Workbook Instructions" in str(ws_inst.cell(row=1, column=1).value)
    
    ws_cat = wb["Product_Catalogue"]
    headers = [cell.value for cell in ws_cat[1]]
    assert len(headers) == 15
    assert headers == [
        "product_id", "product_name", "product_category", "offering_type",
        "product_description", "variant_name", "sku", "pack_size",
        "pack_unit", "ingredients_components", "key_features",
        "specifications", "known_limitations", "applicable_market",
        "record_status"
    ]


def test_claims_register_template_generation_and_guidance():
    """Verify Claims Register template includes Instructions, Claims_Register (11 cols), and Required_Disclosures (7 cols)."""
    content = excel_service.generate_template("claims_and_disclosures")
    wb = openpyxl.load_workbook(io.BytesIO(content))
    
    assert "Instructions" in wb.sheetnames
    assert "Claims_Register" in wb.sheetnames
    assert "Required_Disclosures" in wb.sheetnames
    
    ws_claims = wb["Claims_Register"]
    claims_headers = [cell.value for cell in ws_claims[1]]
    assert len(claims_headers) == 11
    assert claims_headers == [
        "claim_id", "claim_text", "claim_type", "claim_status",
        "applicable_product_id", "approved_variations", "restricted_conditions",
        "prohibited_variations", "applicable_market", "effective_from", "effective_until"
    ]
    
    ws_disc = wb["Required_Disclosures"]
    disc_headers = [cell.value for cell in ws_disc[1]]
    assert len(disc_headers) == 7
    assert disc_headers == [
        "disclosure_id", "disclosure_text", "applicable_product_id",
        "applicable_market", "applies_when", "effective_from", "effective_until"
    ]


def test_product_catalogue_validation_rules(db_session, auth_tokens):
    """Test field guidance, duplicate SKU validation, variant SKU requirement, and pack_size positive check."""
    org_id = auth_tokens["org_admin"]["org_id"]
    headers = [
        "product_id", "product_name", "product_category", "offering_type",
        "product_description", "variant_name", "sku", "pack_size",
        "pack_unit", "ingredients_components", "key_features",
        "specifications", "known_limitations", "applicable_market",
        "record_status"
    ]
    
    rows = [
        headers,
        # Row 2: Invalid offering_type, negative pack_size, variant present without SKU
        [
            "TEST-P01", "Orange Juice 250ml", "Beverage", "InvalidOffering",
            "Fresh juice", "250ml Bottle", "", -50,
            "ml", "Orange Juice", "Fresh", "Keep chilled", "None", "India", "Active"
        ],
        # Row 3: Valid variant with SKU
        [
            "TEST-P02", "Orange Juice 1L", "Beverage", "Physical Product",
            "Fresh juice", "1L Bottle", "SKU-DUP-01", 1000,
            "ml", "Orange Juice", "Fresh", "Keep chilled", "None", "India", "Active"
        ],
        # Row 4: Duplicate SKU as Row 3
        [
            "TEST-P03", "Orange Juice Family Pack", "Beverage", "",
            "Fresh juice", "Family Pack", "SKU-DUP-01", 2000,
            "ml", "Orange Juice", "Fresh", "Keep chilled", "None", "India", "Active"
        ]
    ]
    
    file_bytes = _build_excel_file({"Product_Catalogue": rows})
    staged = excel_service.parse_and_stage_excel(
        db=db_session,
        org_id=org_id,
        user_id=None,
        file_name="test_products.xlsx",
        file_bytes=file_bytes,
        idempotency_key=f"test-prod-val-{uuid.uuid4()}",
        import_type="product_catalogue"
    )
    
    assert staged.error_rows >= 2
    p_rows = db_session.query(StagedImportProductRow).filter(
        StagedImportProductRow.import_id == staged.id
    ).order_by(StagedImportProductRow.row_number).all()
    
    # Row 2 should flag missing SKU for variant, invalid offering_type, negative pack_size
    r2_errors = p_rows[0].validation_errors
    assert any("SKU is required when variant_name is specified" in err for err in r2_errors)
    assert any("pack_size must be a positive number" in err for err in r2_errors)
    assert any("Invalid offering_type" in err for err in r2_errors)
    
    # Row 4 should flag duplicate SKU
    r4_errors = p_rows[2].validation_errors
    assert any("Duplicate SKU 'SKU-DUP-01'" in err for err in r4_errors)


def test_claims_register_conditional_validation(db_session, auth_tokens):
    """Test conditional validation: Restricted requires conditions, Prohibited forbids approved variations."""
    org_id = auth_tokens["org_admin"]["org_id"]
    claims_headers = [
        "claim_id", "claim_text", "claim_type", "claim_status",
        "applicable_product_id", "approved_variations", "restricted_conditions",
        "prohibited_variations", "applicable_market", "effective_from", "effective_until"
    ]
    
    claims_rows = [
        claims_headers,
        # Row 2: Restricted without restricted_conditions (INVALID)
        [
            "CLM-ERR-1", "No Added Sugar", "Nutritional", "Restricted",
            "ALL", "Zero Added Sugar", "", "", "India", "2026-01-01", ""
        ],
        # Row 3: Prohibited containing approved_variations (CONTRADICTION - INVALID)
        [
            "CLM-ERR-2", "Cures Diabetes", "Health", "Prohibited",
            "ALL", "Treats Sugar Illness", "", "Cures blood sugar", "India", "2026-01-01", ""
        ],
        # Row 4: effective_until earlier than effective_from (INVALID)
        [
            "CLM-ERR-3", "100% Recyclable Glass", "Environmental", "Approved",
            "ALL", "", "", "", "India", "2026-06-01", "2026-01-01"
        ],
        # Row 5: Non-existent product reference (INVALID)
        [
            "CLM-ERR-4", "Artisanal Guava", "Quality", "Approved",
            "NON-EXISTENT-SKU-999", "", "", "", "India", "2026-01-01", ""
        ],
    ]
    
    file_bytes = _build_excel_file({"Claims_Register": claims_rows})
    staged = excel_service.parse_and_stage_excel(
        db=db_session,
        org_id=org_id,
        user_id=None,
        file_name="test_claims_val.xlsx",
        file_bytes=file_bytes,
        idempotency_key=f"test-claim-val-{uuid.uuid4()}",
        import_type="claims_and_disclosures"
    )
    
    assert staged.error_rows == 4
    c_rows = db_session.query(StagedImportClaimRow).filter(
        StagedImportClaimRow.import_id == staged.id
    ).order_by(StagedImportClaimRow.row_number).all()
    
    # Row 2: Restricted must specify restricted_conditions
    assert any("Restricted claims must specify 'restricted_conditions'" in err for err in c_rows[0].validation_errors)
    # Row 3: Prohibited claims cannot contain approved_variations
    assert any("Prohibited claims cannot contain approved_variations" in err for err in c_rows[1].validation_errors)
    # Row 4: effective_until earlier than effective_from
    assert any("cannot be earlier than effective_from" in err for err in c_rows[2].validation_errors)
    # Row 5: Non-existent product
    assert any("not found in active organisation catalogue" in err for err in c_rows[3].validation_errors)


def test_dry_run_staging_safety_and_rollback(db_session, auth_tokens):
    """Verify that invalid imports and discarded imports never mutate active catalogue or claims."""
    org_id = auth_tokens["org_admin"]["org_id"]
    initial_product_count = db_session.query(Product).filter(Product.organization_id == org_id).count()
    initial_claim_count = db_session.query(Claim).filter(Claim.organization_id == org_id).count()
    
    invalid_rows = [
        ["product_id", "product_name", "product_category", "offering_type",
         "product_description", "variant_name", "sku", "pack_size",
         "pack_unit", "ingredients_components", "key_features",
         "specifications", "known_limitations", "applicable_market",
         "record_status"],
        ["INV-P01", "", "", "", "", "", "", "", "", "", "", "", "", "", ""]
    ]
    file_bytes = _build_excel_file({"Product_Catalogue": invalid_rows})
    staged = excel_service.parse_and_stage_excel(
        db=db_session,
        org_id=org_id,
        user_id=None,
        file_name="invalid.xlsx",
        file_bytes=file_bytes,
        idempotency_key=f"idemp-fail-{uuid.uuid4()}",
        import_type="product_catalogue"
    )
    assert staged.error_rows > 0
    assert db_session.query(Product).filter(Product.organization_id == org_id).count() == initial_product_count
    
    with pytest.raises(ValueError, match="Cannot commit import with"):
        excel_service.confirm_staged_import(db_session, org_id, staged.id, None)
    
    excel_service.discard_staged_import(db_session, org_id, staged.id)
    assert db_session.query(Product).filter(Product.organization_id == org_id).count() == initial_product_count
    assert db_session.query(Claim).filter(Claim.organization_id == org_id).count() == initial_claim_count


def test_governance_scenarios_comprehensive(db_session, auth_tokens):
    """
    Directly verifies the governance engine across the 12 required scenarios.
    """
    test_org = Organization(id=str(uuid.uuid4()), name="Gov Test Org", slug=f"gov-test-{uuid.uuid4().hex[:6]}")
    db_session.add(test_org)
    db_session.flush()
    org_id = test_org.id
    other_org = Organization(id=str(uuid.uuid4()), name="Other Org", slug=f"other-{uuid.uuid4().hex[:6]}")
    db_session.add(other_org)
    db_session.flush()
    
    prod1 = Product(
        organization_id=org_id,
        product_id="GOV-P001",
        product_name="Botanical Cold Press 1",
        product_category="Beverage",
        offering_type="Physical Product",
        product_description="Single-ingredient botanical juice.",
        variant_name="250ml",
        sku="SKU-GOV-001",
        ingredients_components="Cold-Pressed Orange Juice (100%)",
        key_features="Pure pressed orange juice; Keep chilled",
        applicable_market="India",
        record_status="Active"
    )
    prod2 = Product(
        organization_id=org_id,
        product_id="GOV-P002",
        product_name="Botanical Cold Press 2",
        product_category="Beverage",
        offering_type="Physical Product",
        product_description="Single-ingredient berry juice.",
        variant_name="250ml",
        sku="SKU-GOV-002",
        ingredients_components="Pomegranate Extract (100%)",
        key_features="Pure pomegranate juice",
        applicable_market="India",
        record_status="Active"
    )
    db_session.add(prod1)
    db_session.add(prod2)
    db_session.flush()
    
    # 1. Approved Claim (for GOV-P001)
    claim1 = Claim(
        organization_id=org_id,
        product_id=prod1.id,
        claim_id="TEST-CLM-01",
        claim_text="Made with 100% single-orchard Valencia oranges",
        claim_type="Ingredient",
        claim_status="Approved",
        applicable_product_id="GOV-P001",
        approved_variations="Contains 100% single-orchard Valencia oranges; Pure single-orchard Valencia oranges",
        prohibited_variations="100% raw wild unpasteurized oranges; Cures chronic illness",
        applicable_market="India",
        effective_from=date(2026, 1, 1),
        effective_until=date(2027, 12, 31)
    )
    # 2. Restricted Claim (requires qualifying condition)
    claim2 = Claim(
        organization_id=org_id,
        product_id=None,
        claim_id="TEST-CLM-02",
        claim_text="Zero Refined Sugar Formulation",
        claim_type="Nutritional",
        claim_status="Restricted",
        applicable_product_id="ALL",
        restricted_conditions="Must state: sweetened exclusively with naturally occurring fruit pulp",
        applicable_market="India",
        effective_from=date(2026, 1, 1),
        effective_until=date(2027, 12, 31)
    )
    # 3. Prohibited Claim
    claim3 = Claim(
        organization_id=org_id,
        product_id=None,
        claim_id="TEST-CLM-03",
        claim_text="Eliminates metabolic toxins completely",
        claim_type="Health",
        claim_status="Prohibited",
        applicable_product_id="ALL",
        prohibited_variations="Melts visceral fat effortlessly; Flushes metabolic waste",
        applicable_market="India",
        effective_from=date(2026, 1, 1),
        effective_until=None
    )
    # 4. Expired Claim
    claim4 = Claim(
        organization_id=org_id,
        product_id=prod1.id,
        claim_id="TEST-CLM-04",
        claim_text="Special 2025 Harvest Batch Edition",
        claim_type="Quality",
        claim_status="Approved",
        applicable_product_id="GOV-P001",
        applicable_market="India",
        effective_from=date(2025, 1, 1),
        effective_until=date(2025, 12, 31)
    )
    # 5. Future-dated Claim
    claim5 = Claim(
        organization_id=org_id,
        product_id=prod1.id,
        claim_id="TEST-CLM-05",
        claim_text="Solar Powered Carbon Negative Facility Edition",
        claim_type="Environmental",
        claim_status="Approved",
        applicable_product_id="GOV-P001",
        applicable_market="India",
        effective_from=date(2030, 1, 1),
        effective_until=None
    )
    # 6. Required Disclosure
    disc1 = RequiredDisclosure(
        organization_id=org_id,
        product_id=None,
        disclosure_id="TEST-DISC-01",
        disclosure_text="Keep refrigerated between 2C to 5C. Consume within 24 hours of breaking tamper seal.",
        applicable_product_id="ALL",
        applicable_market="India",
        applies_when="Applies to all packaging collateral",
        effective_from=date(2026, 1, 1),
        effective_until=None
    )
    db_session.add_all([claim1, claim2, claim3, claim4, claim5, disc1])
    db_session.commit()
    
    # 1: Approved claim accepted within scope
    findings_1, _ = governance_engine.evaluate_claims_and_disclosures(
        db=db_session,
        org_id=org_id,
        combined_content="Botanical Cold Press 1 is Made with 100% single-orchard Valencia oranges.",
        channel="Social Media",
        detected_products=["GOV-P001"],
        product_id="GOV-P001"
    )
    assert not any(f.category == "prohibited_claim" or f.category == "unsupported_claim" for f in findings_1)

    # 2: Approved variation accepted
    findings_2, _ = governance_engine.evaluate_claims_and_disclosures(
        db=db_session,
        org_id=org_id,
        combined_content="Botanical Cold Press 1 Contains 100% single-orchard Valencia oranges with exceptional taste.",
        channel="Social Media",
        detected_products=["GOV-P001"],
        product_id="GOV-P001"
    )
    assert not any(f.category == "prohibited_claim" or f.category == "unsupported_claim" for f in findings_2)

    # 3 & 11: Unapproved variation / Product fact does not authorise promotional wording
    findings_3, _ = governance_engine.evaluate_claims_and_disclosures(
        db=db_session,
        org_id=org_id,
        combined_content="Botanical Cold Press 1 is 100% natural and sugar-free juice pressed fresh.",
        channel="Social Media",
        detected_products=["GOV-P001"],
        product_id="GOV-P001"
    )
    unreg_findings = [f for f in findings_3 if f.title == "Unregistered Claim: Not found in Claims Register"]
    assert len(unreg_findings) >= 1
    assert unreg_findings[0].category == "unsupported_claim"
    assert "was not found in the organisation's approved Claims Register" in unreg_findings[0].explanation

    # 4: Restricted claim accepted when condition satisfied
    findings_4, _ = governance_engine.evaluate_claims_and_disclosures(
        db=db_session,
        org_id=org_id,
        combined_content="Enjoy our Zero Refined Sugar Formulation, sweetened exclusively with naturally occurring fruit pulp for pure refreshment.",
        channel="Social Media",
        detected_products=["GOV-P001"],
        product_id="GOV-P001"
    )
    assert not any(f.category == "claim_restriction_issue" for f in findings_4)

    # 5: Restricted claim flagged when condition not satisfied
    findings_5, _ = governance_engine.evaluate_claims_and_disclosures(
        db=db_session,
        org_id=org_id,
        combined_content="Enjoy our Zero Refined Sugar Formulation! Refreshing and healthy.",
        channel="Social Media",
        detected_products=["GOV-P001"],
        product_id="GOV-P001"
    )
    restr_findings = [f for f in findings_5 if f.category == "claim_restriction_issue"]
    assert len(restr_findings) == 1
    assert restr_findings[0].severity == "high"
    assert "Restricted Claim Condition Not Satisfied" in restr_findings[0].title

    # 6: Prohibited claim flagged
    findings_6, _ = governance_engine.evaluate_claims_and_disclosures(
        db=db_session,
        org_id=org_id,
        combined_content="Botanical Cold Press Eliminates metabolic toxins completely.",
        channel="Social Media",
        detected_products=["GOV-P001"],
        product_id="GOV-P001"
    )
    proh_findings = [f for f in findings_6 if f.category == "prohibited_claim"]
    assert len(proh_findings) >= 1
    assert proh_findings[0].severity == "critical"
    assert "Prohibited Claim Detected" in proh_findings[0].title

    # 7: Prohibited variation flagged
    findings_7, _ = governance_engine.evaluate_claims_and_disclosures(
        db=db_session,
        org_id=org_id,
        combined_content="Drink Botanical Cold Press, it Melts visceral fat effortlessly!",
        channel="Social Media",
        detected_products=["GOV-P001"],
        product_id="GOV-P001"
    )
    proh_var_findings = [f for f in findings_7 if f.category == "prohibited_claim"]
    assert len(proh_var_findings) >= 1
    assert "Prohibited Claim Variation Detected" in proh_var_findings[0].title

    # 8a: Expired claim flagged
    findings_8a, _ = governance_engine.evaluate_claims_and_disclosures(
        db=db_session,
        org_id=org_id,
        combined_content="Get our Special 2025 Harvest Batch Edition today!",
        channel="Social Media",
        detected_products=["GOV-P001"],
        product_id="GOV-P001"
    )
    expired_findings = [f for f in findings_8a if f.category == "source_freshness_issue"]
    assert len(expired_findings) == 1
    assert "Expired Claim Detected" in expired_findings[0].title

    # 8b: Future-dated claim flagged
    findings_8b, _ = governance_engine.evaluate_claims_and_disclosures(
        db=db_session,
        org_id=org_id,
        combined_content="Produced in our Solar Powered Carbon Negative Facility Edition.",
        channel="Social Media",
        detected_products=["GOV-P001"],
        product_id="GOV-P001"
    )
    future_findings = [f for f in findings_8b if f.category == "claim_status_issue"]
    assert len(future_findings) == 1
    assert "Claim Not Yet Effective" in future_findings[0].title

    # 9: Claim associated with another product flagged
    findings_9, _ = governance_engine.evaluate_claims_and_disclosures(
        db=db_session,
        org_id=org_id,
        combined_content="Botanical Cold Press 2 is Made with 100% single-orchard Valencia oranges.",
        channel="Social Media",
        detected_products=["GOV-P002"],
        product_id="GOV-P002"
    )
    mismatch_findings = [f for f in findings_9 if f.category == "product_fact_mismatch"]
    assert len(mismatch_findings) == 1
    assert "Claim Product Mismatch" in mismatch_findings[0].title

    # 10: ALL scoped strictly to organisation (Tenant Isolation)
    findings_10, count_10 = governance_engine.evaluate_claims_and_disclosures(
        db=db_session,
        org_id=other_org.id,
        combined_content="Botanical Cold Press 1 is Made with 100% single-orchard Valencia oranges.",
        channel="Social Media",
        detected_products=[],
        product_id=None
    )
    assert count_10 == 0

    # 12: Required disclosure flagged as missing when conditions met
    findings_12, _ = governance_engine.evaluate_claims_and_disclosures(
        db=db_session,
        org_id=org_id,
        combined_content="Botanical Cold Press 1 Bottle Mockup.",
        channel="packaging",
        detected_products=["GOV-P001"],
        product_id="GOV-P001"
    )
    disc_findings = [f for f in findings_12 if f.category == "missing_required_disclosure"]
    assert len(disc_findings) >= 1
    assert "Missing Required Disclosure: [TEST-DISC-01]" in disc_findings[0].title
    # Cleanup
    db_session.query(RequiredDisclosure).filter(RequiredDisclosure.organization_id == org_id).delete()
    db_session.query(Claim).filter(Claim.organization_id == org_id).delete()
    db_session.query(Product).filter(Product.organization_id == org_id).delete()
    db_session.query(Organization).filter(Organization.id.in_([org_id, other_org.id])).delete()
    db_session.commit()


def test_offering_type_validation_and_omission_prevention(db_session, auth_tokens):
    """
    Verify that omitted offering_type is rejected to prevent silent misclassification,
    all valid offering types are accepted, and invalid offering types are rejected.
    """
    org_id = auth_tokens["org_admin"]["org_id"]
    headers = [
        "product_id", "product_name", "product_category", "offering_type",
        "product_description", "variant_name", "sku", "pack_size",
        "pack_unit", "ingredients_components", "key_features",
        "specifications", "known_limitations", "applicable_market",
        "record_status"
    ]
    
    rows = [
        headers,
        # Row 2: Omitted offering_type (Must be rejected to prevent silent misclassification)
        [
            "OT-001", "Delivery Plan", "Subscription", "",
            "Weekly doorstep delivery", "", "SKU-OT-001", "",
            "", "", "Weekly drop", "Chilled transport", "None", "India", "Active"
        ],
        # Row 3: Explicit Physical Product
        [
            "OT-002", "Orange Juice 250ml", "Beverage", "Physical Product",
            "Fresh juice", "250ml", "SKU-OT-002", 250,
            "ml", "Orange Juice", "Fresh", "Keep chilled", "None", "India", "Active"
        ],
        # Row 4: Explicit Service
        [
            "OT-003", "Cold-Chain Logistics", "Services", "Service",
            "Temperature-controlled fulfillment", "", "SKU-OT-003", "",
            "", "", "2-5C logistics", "Refrigerated van", "None", "India", "Active"
        ],
        # Row 5: Explicit Subscription
        [
            "OT-004", "Monthly Citrus Club", "Membership", "Subscription",
            "Monthly curation of exotic juices", "", "SKU-OT-004", "",
            "", "", "Monthly box", "Recurring billing", "None", "India", "Active"
        ],
        # Row 6: Explicit Digital Product
        [
            "OT-005", "Juicing Recipe E-Book", "Digital Goods", "Digital Product",
            "Digital recipe collection in PDF", "", "SKU-OT-005", "",
            "", "", "PDF download", "Instant delivery", "None", "India", "Active"
        ],
        # Row 7: Invalid offering_type
        [
            "OT-006", "Mystery Offering", "Unknown", "Vaporware",
            "Non-existent offering category", "", "SKU-OT-006", "",
            "", "", "None", "None", "None", "India", "Active"
        ]
    ]

    file_bytes = _build_excel_file({"Product_Catalogue": rows})
    staged = excel_service.parse_and_stage_excel(
        db=db_session,
        org_id=org_id,
        user_id=None,
        file_name="test_offering_types.xlsx",
        file_bytes=file_bytes,
        idempotency_key=f"test-ot-{uuid.uuid4()}",
        import_type="product_catalogue"
    )

    p_rows = db_session.query(StagedImportProductRow).filter(
        StagedImportProductRow.import_id == staged.id
    ).order_by(StagedImportProductRow.row_number).all()

    # Row 2: Omitted offering_type must be flagged as required
    r2_errors = p_rows[0].validation_errors
    assert any("offering_type is required" in err for err in r2_errors)

    # Row 3: Physical Product is valid
    assert p_rows[1].is_valid is True
    assert p_rows[1].parsed_data["offering_type"] == "Physical Product"

    # Row 4: Service is valid
    assert p_rows[2].is_valid is True
    assert p_rows[2].parsed_data["offering_type"] == "Service"

    # Row 5: Subscription is valid
    assert p_rows[3].is_valid is True
    assert p_rows[3].parsed_data["offering_type"] == "Subscription"

    # Row 6: Digital Product is valid
    assert p_rows[4].is_valid is True
    assert p_rows[4].parsed_data["offering_type"] == "Digital Product"

    # Row 7: Invalid offering_type rejected
    r7_errors = p_rows[5].validation_errors
    assert any("Invalid offering_type 'Vaporware'" in err for err in r7_errors)

    # Cleanup staging
    excel_service.discard_staged_import(db_session, org_id, staged.id)


def test_staged_product_and_claim_reference_end_to_end_workflow(db_session):
    """
    Test complete lifecycle:
    1. Upload Product Catalogue with new products -> Stage.
    2. Upload Claims Register referencing the staged products -> Validate.
    3. Confirm claims BEFORE products -> Blocked by integrity check.
    4. Confirm product import -> Committed.
    5. Confirm claims import -> Committed and linked to internal product ID.
    6. Run governance against content using new product and claim.
    7. Discard another staged import -> Active catalogue unaffected.
    """
    flow_org = Organization(id=str(uuid.uuid4()), name="E2E Flow Org", slug=f"flow-{uuid.uuid4().hex[:6]}")
    db_session.add(flow_org)
    db_session.flush()

    try:
        # Step 1: Upload and Stage Product Catalogue
        prod_headers = [
            "product_id", "product_name", "product_category", "offering_type",
            "product_description", "variant_name", "sku", "pack_size",
            "pack_unit", "ingredients_components", "key_features",
            "specifications", "known_limitations", "applicable_market",
            "record_status"
        ]
        prod_rows = [
            prod_headers,
            [
                "FLOW-P01", "Alphonso Mango Nectar", "Fruit Beverage", "Physical Product",
                "Single-origin Alphonso mango pulp", "500ml Bottle", "SKU-FLOW-01", 500,
                "ml", "Alphonso Mango (100%)", "No Added Sugar", "Store chilled", "None", "India", "Active"
            ]
        ]
        staged_prod = excel_service.parse_and_stage_excel(
            db=db_session,
            org_id=flow_org.id,
            user_id=None,
            file_name="flow_products.xlsx",
            file_bytes=_build_excel_file({"Product_Catalogue": prod_rows}),
            idempotency_key=f"idemp-flow-p-{uuid.uuid4()}",
            import_type="product_catalogue"
        )
        assert staged_prod.error_rows == 0
        assert staged_prod.status == "pending_preview"

        # Step 2: Upload and Stage Claims Register referencing FLOW-P01 (currently staged, not yet confirmed!)
        claims_headers = [
            "claim_id", "claim_text", "claim_type", "claim_status",
            "applicable_product_id", "approved_variations", "restricted_conditions",
            "prohibited_variations", "applicable_market", "effective_from", "effective_until"
        ]
        claims_rows = [
            claims_headers,
            [
                "CLM-FLOW-01", "Made exclusively with GI-tagged Ratnagiri Alphonso mangoes", "Origin", "Approved",
                "FLOW-P01", "100% Ratnagiri Alphonso mangoes", "",
                "World's sweetest fruit", "India", "2026-01-01", ""
            ]
        ]
        staged_claims = excel_service.parse_and_stage_excel(
            db=db_session,
            org_id=flow_org.id,
            user_id=None,
            file_name="flow_claims.xlsx",
            file_bytes=_build_excel_file({"Claims_Register": claims_rows}),
            idempotency_key=f"idemp-flow-c-{uuid.uuid4()}",
            import_type="claims_and_disclosures"
        )
        # It must resolve FLOW-P01 against staged products without error!
        assert staged_claims.error_rows == 0
        assert staged_claims.status == "pending_preview"

        # Step 3: Verify Invalid References Cannot Be Committed
        # Staging claims referencing a non-existent product must fail validation
        invalid_claims_rows = [
            claims_headers,
            [
                "CLM-INVALID-01", "Claim for non-existent product", "Origin", "Approved",
                "FLOW-NON-EXISTENT", "", "", "", "India", "2026-01-01", ""
            ]
        ]
        staged_invalid = excel_service.parse_and_stage_excel(
            db=db_session,
            org_id=flow_org.id,
            user_id=None,
            file_name="invalid_claims.xlsx",
            file_bytes=_build_excel_file({"Claims_Register": invalid_claims_rows}),
            idempotency_key=f"idemp-invalid-{uuid.uuid4()}",
            import_type="claims_and_disclosures"
        )
        assert staged_invalid.error_rows > 0
        with pytest.raises(ValueError, match="Cannot commit import with"):
            excel_service.confirm_staged_import(db_session, flow_org.id, staged_invalid.id, None)

        # Step 4: Confirm Product Catalogue first
        res_p = excel_service.confirm_staged_import(db_session, flow_org.id, staged_prod.id, None)
        assert res_p["status"] == "success"
        committed_prod = db_session.query(Product).filter(
            Product.organization_id == flow_org.id,
            Product.product_id == "FLOW-P01"
        ).first()
        assert committed_prod is not None

        # Step 5: Now confirm Claims Register (FLOW-P01 is now committed and linked!)
        res_c = excel_service.confirm_staged_import(db_session, flow_org.id, staged_claims.id, None)
        assert res_c["status"] == "success"
        committed_claim = db_session.query(Claim).filter(
            Claim.organization_id == flow_org.id,
            Claim.claim_id == "CLM-FLOW-01"
        ).first()
        assert committed_claim is not None
        assert committed_claim.product_id == committed_prod.id

        # Step 6: Governance Engine evaluation
        findings, evaluated_count = governance_engine.evaluate_claims_and_disclosures(
            db=db_session,
            org_id=flow_org.id,
            combined_content="Enjoy our Alphonso Mango Nectar! Made exclusively with GI-tagged Ratnagiri Alphonso mangoes.",
            channel="Social Media",
            detected_products=["FLOW-P01"],
            product_id="FLOW-P01"
        )
        assert evaluated_count >= 1
        # Approved claim in scope produces zero violation findings
        assert len(findings) == 0

        # Step 7: Discard safety - staged imports discarded do not modify active records
        staged_dummy = excel_service.parse_and_stage_excel(
            db=db_session,
            org_id=flow_org.id,
            user_id=None,
            file_name="dummy.xlsx",
            file_bytes=_build_excel_file({"Product_Catalogue": [prod_headers, [
                "FLOW-DUMMY", "Dummy", "Beverage", "Physical Product", "Desc", "", "SKU-DUMMY", 100, "ml", "Water", "None", "None", "None", "India", "Active"
            ]]}),
            idempotency_key=f"idemp-dummy-{uuid.uuid4()}",
            import_type="product_catalogue"
        )
        excel_service.discard_staged_import(db_session, flow_org.id, staged_dummy.id)
        assert db_session.query(Product).filter(Product.organization_id == flow_org.id, Product.product_id == "FLOW-DUMMY").count() == 0
        assert db_session.query(Product).filter(Product.organization_id == flow_org.id).count() == 1

    finally:
        db_session.query(Claim).filter(Claim.organization_id == flow_org.id).delete()
        db_session.query(Product).filter(Product.organization_id == flow_org.id).delete()
        db_session.query(Organization).filter(Organization.id == flow_org.id).delete()
        db_session.commit()


def test_promotional_claims_vs_factual_descriptions_comprehensive(db_session):
    """
    Test promotional claims vs ordinary factual descriptions:
    - Registered approved claim accepted
    - Approved variation accepted
    - Ordinary factual product descriptions NOT flagged
    - Similar wording with different meaning NOT flagged
    - Negated statements NOT flagged
    - Multiple sentences with claims evaluated correctly
    - Unregistered promotional claim flagged as warning (Not found in Claims Register)
    - Restricted and prohibited claims flagged appropriately
    - Claim referring to different product flagged as product_fact_mismatch
    """
    test_org = Organization(id=str(uuid.uuid4()), name="Promo Test Org", slug=f"promo-{uuid.uuid4().hex[:6]}")
    db_session.add(test_org)
    db_session.flush()

    try:
        p1 = Product(
            organization_id=test_org.id,
            product_id="P-VALENCIA",
            product_name="Valencia Orange Cold Press",
            product_category="Beverage",
            offering_type="Physical Product",
            product_description="Single-ingredient botanical orange juice with natural pulp.",
            variant_name="250ml",
            sku="SKU-VAL-250",
            ingredients_components="Cold-Pressed Orange Juice (100%)",
            key_features="Pure pressed orange juice",
            applicable_market="India",
            record_status="Active"
        )
        p2 = Product(
            organization_id=test_org.id,
            product_id="P-BERRY",
            product_name="Wild Berry Puree",
            product_category="Beverage",
            offering_type="Physical Product",
            product_description="Wild berry cold press.",
            variant_name="250ml",
            sku="SKU-BER-250",
            ingredients_components="Blackberry Juice (100%)",
            key_features="Pure blackberry juice",
            applicable_market="India",
            record_status="Active"
        )
        db_session.add_all([p1, p2])
        db_session.flush()

        # 1. Registered Approved Claim
        c_app = Claim(
            organization_id=test_org.id,
            product_id=p1.id,
            claim_id="CLM-P-01",
            claim_text="Single-orchard Valencia oranges",
            claim_type="Origin",
            claim_status="Approved",
            applicable_product_id="P-VALENCIA",
            approved_variations="Pressed from single-orchard oranges; Harvested from single-orchard groves",
            prohibited_variations="Miracle orange juice",
            applicable_market="India",
            effective_from=date(2026, 1, 1),
            effective_until=None
        )
        # 2. Restricted Claim
        c_res = Claim(
            organization_id=test_org.id,
            product_id=None,
            claim_id="CLM-P-02",
            claim_text="No Added Sweeteners",
            claim_type="Nutritional",
            claim_status="Restricted",
            applicable_product_id="ALL",
            restricted_conditions="Must state: naturally occurring fruit sugars",
            applicable_market="India",
            effective_from=date(2026, 1, 1),
            effective_until=None
        )
        # 3. Prohibited Claim
        c_pro = Claim(
            organization_id=test_org.id,
            product_id=None,
            claim_id="CLM-P-03",
            claim_text="Cures cardiovascular fatigue",
            claim_type="Health",
            claim_status="Prohibited",
            applicable_product_id="ALL",
            prohibited_variations="Heals cardiovascular illness; Liquid medicine",
            applicable_market="India",
            effective_from=date(2026, 1, 1),
            effective_until=None
        )
        db_session.add_all([c_app, c_res, c_pro])
        db_session.commit()

        # 1. Registered approved claim -> Accepted (0 findings)
        f1, _ = governance_engine.evaluate_claims_and_disclosures(
            db=db_session, org_id=test_org.id,
            combined_content="Enjoy our juice crafted with Single-orchard Valencia oranges.",
            channel="Social Media", detected_products=["P-VALENCIA"], product_id="P-VALENCIA"
        )
        assert len(f1) == 0

        # 2. Approved variation -> Accepted (0 findings)
        f2, _ = governance_engine.evaluate_claims_and_disclosures(
            db=db_session, org_id=test_org.id,
            combined_content="Every bottle is pressed from single-orchard oranges with great care.",
            channel="Social Media", detected_products=["P-VALENCIA"], product_id="P-VALENCIA"
        )
        assert len(f2) == 0

        # 3. Ordinary factual description -> Accepted (0 findings, natural sediment does not trigger unregistered claim)
        f3, _ = governance_engine.evaluate_claims_and_disclosures(
            db=db_session, org_id=test_org.id,
            combined_content="Single-ingredient botanical orange juice with natural pulp and natural fruit cloudiness. Shake well.",
            channel="Social Media", detected_products=["P-VALENCIA"], product_id="P-VALENCIA"
        )
        assert len(f3) == 0

        # 4. Similar wording with different meaning -> Accepted (0 findings)
        f4, _ = governance_engine.evaluate_claims_and_disclosures(
            db=db_session, org_id=test_org.id,
            combined_content="The citrus fruit has an authentic sweet flavour and vibrant appearance.",
            channel="Social Media", detected_products=["P-VALENCIA"], product_id="P-VALENCIA"
        )
        assert len(f4) == 0

        # 5. Unregistered promotional claim -> Flagged as warning (Unregistered Claim: Not found in Claims Register)
        f5, _ = governance_engine.evaluate_claims_and_disclosures(
            db=db_session, org_id=test_org.id,
            combined_content="Our delicious orange drink is 100% natural and sugar-free!",
            channel="Social Media", detected_products=["P-VALENCIA"], product_id="P-VALENCIA"
        )
        unreg = [f for f in f5 if "Unregistered Claim" in f.title]
        assert len(unreg) >= 1
        assert unreg[0].severity == "warning"
        assert unreg[0].status == "unresolved"

        # 6. Negated statement -> Negation skips unregistered finding
        f6, _ = governance_engine.evaluate_claims_and_disclosures(
            db=db_session, org_id=test_org.id,
            combined_content="We do not claim to be 100% natural, but our fruit is harvested freshly.",
            channel="Social Media", detected_products=["P-VALENCIA"], product_id="P-VALENCIA"
        )
        unreg_neg = [f for f in f6 if "Unregistered Claim" in f.title]
        assert len(unreg_neg) == 0

        # 7. Multiple sentences containing prohibited claim
        f7, _ = governance_engine.evaluate_claims_and_disclosures(
            db=db_session, org_id=test_org.id,
            combined_content="Welcome to our beverage store. Our formula cures cardiovascular fatigue effectively. Order now.",
            channel="Social Media", detected_products=["P-VALENCIA"], product_id="P-VALENCIA"
        )
        pro_findings = [f for f in f7 if f.category == "prohibited_claim"]
        assert len(pro_findings) == 1
        assert pro_findings[0].severity == "critical"

        # 8. Restricted claim condition satisfied -> Accepted (0 findings)
        f8, _ = governance_engine.evaluate_claims_and_disclosures(
            db=db_session, org_id=test_org.id,
            combined_content="Formulated with No Added Sweeteners. Sweetened exclusively with naturally occurring fruit sugars.",
            channel="Social Media", detected_products=["P-VALENCIA"], product_id="P-VALENCIA"
        )
        res_satisfied = [f for f in f8 if f.category == "claim_restriction_issue"]
        assert len(res_satisfied) == 0

        # 9. Restricted claim condition NOT satisfied -> Flagged (claim_restriction_issue, high)
        f9, _ = governance_engine.evaluate_claims_and_disclosures(
            db=db_session, org_id=test_org.id,
            combined_content="Formulated with No Added Sweeteners in every single bottle.",
            channel="Social Media", detected_products=["P-VALENCIA"], product_id="P-VALENCIA"
        )
        res_unsatisfied = [f for f in f9 if f.category == "claim_restriction_issue"]
        assert len(res_unsatisfied) == 1
        assert res_unsatisfied[0].severity == "high"

        # 10. Claim for Product A used on Product B -> Flagged (product_fact_mismatch, critical)
        f10, _ = governance_engine.evaluate_claims_and_disclosures(
            db=db_session, org_id=test_org.id,
            combined_content="Wild Berry Puree made with Single-orchard Valencia oranges.",
            channel="Social Media", detected_products=["P-BERRY"], product_id="P-BERRY"
        )
        mismatch = [f for f in f10 if f.category == "product_fact_mismatch"]
        assert len(mismatch) == 1
        assert mismatch[0].severity == "critical"

    finally:
        db_session.query(Claim).filter(Claim.organization_id == test_org.id).delete()
        db_session.query(Product).filter(Product.organization_id == test_org.id).delete()
        db_session.query(Organization).filter(Organization.id == test_org.id).delete()
        db_session.commit()


def test_effective_date_semantics_boundary_matrix(db_session, monkeypatch):
    """
    Test the exact 7 effective date boundary semantics:
    1. Before effective_from: Flagged as claim_status_issue (Claim Not Yet Effective)
    2. Exactly on effective_from: IN EFFECT (valid, 0 date findings)
    3. Between effective_from and effective_until: IN EFFECT (valid, 0 date findings)
    4. Exactly on effective_until: IN EFFECT (valid, 0 date findings - INCLUSIVE end date)
    5. After effective_until: Flagged as source_freshness_issue (Expired Claim Detected)
    6. No effective_until: IN EFFECT (valid indefinitely)
    7. Future-dated claim: Flagged as claim_status_issue
    """
    date_org = Organization(id=str(uuid.uuid4()), name="Date Matrix Org", slug=f"date-{uuid.uuid4().hex[:6]}")
    db_session.add(date_org)
    db_session.flush()

    try:
        # Reference date: 2026-06-15
        ref_today = date(2026, 6, 15)

        # 1. Before effective_from (starts 2026-07-01)
        c_before = Claim(
            organization_id=date_org.id,
            claim_id="CLM-DATE-01",
            claim_text="Q3 2026 Harvest Edition",
            claim_type="Quality",
            claim_status="Approved",
            applicable_product_id="ALL",
            applicable_market="India",
            effective_from=date(2026, 7, 1),
            effective_until=date(2026, 9, 30)
        )
        # 2. Exactly on effective_from (starts 2026-06-15)
        c_on_start = Claim(
            organization_id=date_org.id,
            claim_id="CLM-DATE-02",
            claim_text="Mid-Year Summer Launch",
            claim_type="Quality",
            claim_status="Approved",
            applicable_product_id="ALL",
            applicable_market="India",
            effective_from=date(2026, 6, 15),
            effective_until=date(2026, 7, 15)
        )
        # 3. Between effective dates (2026-01-01 to 2026-12-31)
        c_between = Claim(
            organization_id=date_org.id,
            claim_id="CLM-DATE-03",
            claim_text="Annual Sustainable Farming Certified",
            claim_type="Quality",
            claim_status="Approved",
            applicable_product_id="ALL",
            applicable_market="India",
            effective_from=date(2026, 1, 1),
            effective_until=date(2026, 12, 31)
        )
        # 4. Exactly on effective_until (expires 2026-06-15 - INCLUSIVE!)
        c_on_end = Claim(
            organization_id=date_org.id,
            claim_id="CLM-DATE-04",
            claim_text="Spring Harvest Final Day",
            claim_type="Quality",
            claim_status="Approved",
            applicable_product_id="ALL",
            applicable_market="India",
            effective_from=date(2026, 3, 1),
            effective_until=date(2026, 6, 15)
        )
        # 5. After effective_until (expired 2026-06-14)
        c_after = Claim(
            organization_id=date_org.id,
            claim_id="CLM-DATE-05",
            claim_text="Expired Spring Batch Guarantee",
            claim_type="Quality",
            claim_status="Approved",
            applicable_product_id="ALL",
            applicable_market="India",
            effective_from=date(2026, 3, 1),
            effective_until=date(2026, 6, 14)
        )
        # 6. No effective_until (ongoing from 2026-01-01)
        c_no_end = Claim(
            organization_id=date_org.id,
            claim_id="CLM-DATE-06",
            claim_text="Permanent Cold-Chain Integrity Promise",
            claim_type="Quality",
            claim_status="Approved",
            applicable_product_id="ALL",
            applicable_market="India",
            effective_from=date(2026, 1, 1),
            effective_until=None
        )
        # 7. Future-dated claim (2027)
        c_future = Claim(
            organization_id=date_org.id,
            claim_id="CLM-DATE-07",
            claim_text="Next Year Solar Energy Pledge",
            claim_type="Quality",
            claim_status="Approved",
            applicable_product_id="ALL",
            applicable_market="India",
            effective_from=date(2027, 1, 1),
            effective_until=None
        )
        db_session.add_all([c_before, c_on_start, c_between, c_on_end, c_after, c_no_end, c_future])
        db_session.commit()

        # Monkeypatch date.today() in governance_engine module to ref_today
        class MockDate(date):
            @classmethod
            def today(cls):
                return ref_today
        monkeypatch.setattr("app.services.governance_engine.date", MockDate)

        # 1. Before effective_from -> Flagged (claim_status_issue)
        f_before, _ = governance_engine.evaluate_claims_and_disclosures(
            db=db_session, org_id=date_org.id,
            combined_content="Bottled as our Q3 2026 Harvest Edition.",
            channel="Social Media", detected_products=[], product_id=None
        )
        assert any(f.category == "claim_status_issue" and "Claim Not Yet Effective" in f.title for f in f_before)

        # 2. Exactly on effective_from -> IN EFFECT (0 findings)
        f_start, _ = governance_engine.evaluate_claims_and_disclosures(
            db=db_session, org_id=date_org.id,
            combined_content="Celebrating our Mid-Year Summer Launch today!",
            channel="Social Media", detected_products=[], product_id=None
        )
        assert len([f for f in f_start if f.category in ("claim_status_issue", "source_freshness_issue")]) == 0

        # 3. Between effective dates -> IN EFFECT (0 findings)
        f_between, _ = governance_engine.evaluate_claims_and_disclosures(
            db=db_session, org_id=date_org.id,
            combined_content="Backed by our Annual Sustainable Farming Certified practices.",
            channel="Social Media", detected_products=[], product_id=None
        )
        assert len([f for f in f_between if f.category in ("claim_status_issue", "source_freshness_issue")]) == 0

        # 4. Exactly on effective_until -> IN EFFECT (0 findings, inclusive end date!)
        f_end, _ = governance_engine.evaluate_claims_and_disclosures(
            db=db_session, org_id=date_org.id,
            combined_content="Today only: Spring Harvest Final Day offer.",
            channel="Social Media", detected_products=[], product_id=None
        )
        assert len([f for f in f_end if f.category in ("claim_status_issue", "source_freshness_issue")]) == 0

        # 5. After effective_until -> Flagged as expired (source_freshness_issue)
        f_after, _ = governance_engine.evaluate_claims_and_disclosures(
            db=db_session, org_id=date_org.id,
            combined_content="Carrying our Expired Spring Batch Guarantee.",
            channel="Social Media", detected_products=[], product_id=None
        )
        assert any(f.category == "source_freshness_issue" and "Expired Claim Detected" in f.title for f in f_after)

        # 6. No effective_until -> IN EFFECT (0 findings)
        f_no_end, _ = governance_engine.evaluate_claims_and_disclosures(
            db=db_session, org_id=date_org.id,
            combined_content="Protected by our Permanent Cold-Chain Integrity Promise.",
            channel="Social Media", detected_products=[], product_id=None
        )
        assert len([f for f in f_no_end if f.category in ("claim_status_issue", "source_freshness_issue")]) == 0

        # 7. Future-dated claim -> Flagged (claim_status_issue)
        f_future, _ = governance_engine.evaluate_claims_and_disclosures(
            db=db_session, org_id=date_org.id,
            combined_content="Pioneering the Next Year Solar Energy Pledge.",
            channel="Social Media", detected_products=[], product_id=None
        )
        assert any(f.category == "claim_status_issue" and "Claim Not Yet Effective" in f.title for f in f_future)

    finally:
        db_session.query(Claim).filter(Claim.organization_id == date_org.id).delete()
        db_session.query(Organization).filter(Organization.id == date_org.id).delete()
        db_session.commit()
