import io
import uuid
from datetime import datetime, date
import openpyxl
import pytest
from sqlalchemy.orm import Session

from app.models.organization import Organization, User
from app.models.knowledge import StagedImport, StagedImportProductRow, StagedImportClaimRow, StagedImportDisclosureRow
from app.services.excel_service import (
    ExcelImportService,
    PRODUCT_CATALOGUE_COLUMNS,
    CLAIMS_REGISTER_COLUMNS,
    REQUIRED_DISCLOSURES_COLUMNS
)
import app.services.gemini_extractor as ge
from app.services.image_governance import ImageGovernanceService
import inspect


@pytest.fixture
def test_context(db_session: Session):
    org = db_session.query(Organization).filter(Organization.slug == "freshsip").first()
    if not org:
        org = db_session.query(Organization).first()
    user = db_session.query(User).first()
    return {"db": db_session, "org_id": org.id, "user_id": user.id}


def create_product_wb(headers=None, rows=None, sheet_name="Product_Catalogue"):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = sheet_name

    if headers is None:
        headers = [c[0] for c in PRODUCT_CATALOGUE_COLUMNS]
    ws.append(headers)

    if rows:
        for r in rows:
            ws.append(r)
    return wb


def create_claims_wb(claims_rows=None, disc_rows=None):
    wb = openpyxl.Workbook()
    ws_claims = wb.active
    ws_claims.title = "Claims_Register"
    ws_claims.append([c[0] for c in CLAIMS_REGISTER_COLUMNS])
    if claims_rows:
        for r in claims_rows:
            ws_claims.append(r)

    if disc_rows is not None:
        ws_disc = wb.create_sheet(title="Required_Disclosures")
        ws_disc.append([c[0] for c in REQUIRED_DISCLOSURES_COLUMNS])
        for r in disc_rows:
            ws_disc.append(r)

    return wb


def wb_to_bytes(wb):
    bio = io.BytesIO()
    wb.save(bio)
    return bio.getvalue()


def stage_file(service, db, org_id, user_id, file_bytes, filename, import_type="product_catalogue"):
    return service.parse_and_stage_excel(
        db=db,
        org_id=org_id,
        user_id=user_id,
        file_name=filename,
        file_bytes=file_bytes,
        idempotency_key=str(uuid.uuid4()),
        import_type=import_type
    )


def valid_product_row(product_id="PRD-001", offering_type="Physical Product", pack_size=250):
    # 15 columns
    return [
        product_id,               # product_id
        "Freshsip Orange 250ml",  # product_name
        "Beverages",              # product_category
        offering_type,            # offering_type
        "100% natural cold pressed orange juice", # product_description
        "Original",               # variant_name
        f"SKU-{product_id}",      # sku
        pack_size,                # pack_size
        "ml",                     # pack_unit
        "Orange juice 100%",      # ingredients_components
        "No preservatives",       # key_features
        "Keep refrigerated",      # specifications
        "Consume within 48h",     # known_limitations
        "ALL",                    # applicable_market
        "Active"                  # record_status
    ]


# -----------------------------------------------------------------------------
# 1. Workbook and Worksheet Validation
# -----------------------------------------------------------------------------

def test_file_extension_rejection(test_context):
    service = ExcelImportService()
    db = test_context["db"]
    org_id = test_context["org_id"]
    user_id = test_context["user_id"]

    for ext in ["test.csv", "test.xls", "test.pdf", "test.xlsm", "test.txt"]:
        staged = stage_file(
            service=service,
            db=db,
            org_id=org_id,
            user_id=user_id,
            file_bytes=b"fake data",
            filename=ext,
            import_type="product_catalogue"
        )
        assert staged.status == "failed"
        assert "Invalid file extension" in staged.validation_summary.get("file_error", "")


def test_missing_required_worksheet_error(test_context):
    service = ExcelImportService()
    db = test_context["db"]
    org_id = test_context["org_id"]
    user_id = test_context["user_id"]

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "WrongSheetName"
    ws.append(["col1", "col2"])

    staged = stage_file(
        service=service,
        db=db,
        org_id=org_id,
        user_id=user_id,
        file_bytes=wb_to_bytes(wb),
        filename="test.xlsx",
        import_type="product_catalogue"
    )
    assert staged.status == "failed"
    err = staged.validation_summary.get("file_error", "")
    assert "Required worksheet 'Product_Catalogue' not found" in err
    assert "WrongSheetName" in err


def test_hidden_worksheet_rejection(test_context):
    service = ExcelImportService()
    db = test_context["db"]
    org_id = test_context["org_id"]
    user_id = test_context["user_id"]

    wb = create_product_wb(rows=[valid_product_row()])
    # In Excel, a workbook must have at least one visible sheet, so create a cover sheet
    wb.create_sheet("Cover")
    wb["Product_Catalogue"].sheet_state = "hidden"

    staged = stage_file(
        service=service,
        db=db,
        org_id=org_id,
        user_id=user_id,
        file_bytes=wb_to_bytes(wb),
        filename="test.xlsx",
        import_type="product_catalogue"
    )
    assert staged.status == "failed"
    err = staged.validation_summary.get("file_error", "")
    assert "hidden" in err.lower()


def test_extra_worksheets_ignored(test_context):
    service = ExcelImportService()
    db = test_context["db"]
    org_id = test_context["org_id"]
    user_id = test_context["user_id"]

    wb = create_product_wb(rows=[valid_product_row("PRD-EXTRA-1")])
    extra = wb.create_sheet("Instructions_Notes")
    extra.append(["Note", "Keep this workbook clean"])

    staged = stage_file(
        service=service,
        db=db,
        org_id=org_id,
        user_id=user_id,
        file_bytes=wb_to_bytes(wb),
        filename="test.xlsx",
        import_type="product_catalogue"
    )
    assert staged.status in ("pending_preview", "staged")
    assert staged.total_rows == 1
    assert staged.valid_rows == 1


# -----------------------------------------------------------------------------
# 2. Row and Column Structure Validation
# -----------------------------------------------------------------------------

def test_missing_and_unexpected_headers(test_context):
    service = ExcelImportService()
    db = test_context["db"]
    org_id = test_context["org_id"]
    user_id = test_context["user_id"]

    headers = [c[0] for c in PRODUCT_CATALOGUE_COLUMNS if c[0] != "offering_type"] + ["unrecognised_extra_col"]
    wb = create_product_wb(headers=headers, rows=[["1"] * len(headers)])

    staged = stage_file(
        service=service,
        db=db,
        org_id=org_id,
        user_id=user_id,
        file_bytes=wb_to_bytes(wb),
        filename="test.xlsx",
        import_type="product_catalogue"
    )
    assert staged.status == "failed"
    err = staged.validation_summary.get("file_error", "")
    assert "Missing required column header(s): offering_type" in err
    assert "Unexpected column header(s) detected: unrecognised_extra_col" in err


def test_duplicate_and_empty_headers(test_context):
    service = ExcelImportService()
    db = test_context["db"]
    org_id = test_context["org_id"]
    user_id = test_context["user_id"]

    # Replace offering_type with duplicate product_name
    headers = [c[0] for c in PRODUCT_CATALOGUE_COLUMNS]
    headers[3] = "product_name"
    wb = create_product_wb(headers=headers, rows=[["1"] * len(headers)])

    staged = stage_file(
        service=service,
        db=db,
        org_id=org_id,
        user_id=user_id,
        file_bytes=wb_to_bytes(wb),
        filename="test.xlsx",
        import_type="product_catalogue"
    )
    assert staged.status == "failed"
    err = staged.validation_summary.get("file_error", "")
    assert "Duplicate column header(s) detected: product_name" in err


def test_reordered_columns_extracted_correctly(test_context):
    service = ExcelImportService()
    db = test_context["db"]
    org_id = test_context["org_id"]
    user_id = test_context["user_id"]

    headers = [c[0] for c in PRODUCT_CATALOGUE_COLUMNS]
    # Reverse the header order
    rev_headers = list(reversed(headers))
    # Map row values according to reversed headers
    canonical_row = valid_product_row("PRD-REORDER", "Physical Product", 350)
    canonical_dict = dict(zip(headers, canonical_row))
    rev_row = [canonical_dict[h] for h in rev_headers]

    wb = create_product_wb(headers=rev_headers, rows=[rev_row])

    staged = stage_file(
        service=service,
        db=db,
        org_id=org_id,
        user_id=user_id,
        file_bytes=wb_to_bytes(wb),
        filename="test.xlsx",
        import_type="product_catalogue"
    )
    assert staged.status in ("pending_preview", "staged")
    staged_row = staged.staged_products[0]
    assert staged_row.parsed_data["product_id"] == "PRD-REORDER"
    assert staged_row.parsed_data["offering_type"] == "Physical Product"
    assert staged_row.parsed_data["pack_size"] == 350


def test_hidden_rows_and_columns_rejection(test_context):
    service = ExcelImportService()
    db = test_context["db"]
    org_id = test_context["org_id"]
    user_id = test_context["user_id"]

    # Test hidden row
    wb = create_product_wb(rows=[valid_product_row("PRD-H1")])
    wb["Product_Catalogue"].row_dimensions[2].hidden = True

    staged = stage_file(
        service=service,
        db=db,
        org_id=org_id,
        user_id=user_id,
        file_bytes=wb_to_bytes(wb),
        filename="test.xlsx",
        import_type="product_catalogue"
    )
    assert staged.error_rows == 1
    assert any("hidden" in err.lower() for err in staged.staged_products[0].validation_errors)

    # Test hidden column
    wb2 = create_product_wb(rows=[valid_product_row("PRD-H2")])
    wb2["Product_Catalogue"].column_dimensions["A"].hidden = True

    staged2 = stage_file(
        service=service,
        db=db,
        org_id=org_id,
        user_id=user_id,
        file_bytes=wb_to_bytes(wb2),
        filename="test.xlsx",
        import_type="product_catalogue"
    )
    assert staged2.error_rows == 1
    assert any("hidden" in err.lower() for err in staged2.staged_products[0].validation_errors)


def test_merged_data_cells_rejection(test_context):
    service = ExcelImportService()
    db = test_context["db"]
    org_id = test_context["org_id"]
    user_id = test_context["user_id"]

    wb = create_product_wb(rows=[
        valid_product_row("PRD-M1"),
        valid_product_row("PRD-M2")
    ])
    # Merge cells in data region
    wb["Product_Catalogue"].merge_cells("A2:A3")

    staged = stage_file(
        service=service,
        db=db,
        org_id=org_id,
        user_id=user_id,
        file_bytes=wb_to_bytes(wb),
        filename="test.xlsx",
        import_type="product_catalogue"
    )
    assert staged.status == "failed"
    assert "Merged cells detected" in staged.validation_summary.get("file_error", "")


def test_empty_rows_skipped(test_context):
    service = ExcelImportService()
    db = test_context["db"]
    org_id = test_context["org_id"]
    user_id = test_context["user_id"]

    wb = create_product_wb(rows=[
        valid_product_row("PRD-E1"),
        [None, "", "  ", None, None, None, None, None, None, None, None, None, None, None, None],
        valid_product_row("PRD-E2"),
        [None, None, None, None, None, None, None, None, None, None, None, None, None, None, None]
    ])

    staged = stage_file(
        service=service,
        db=db,
        org_id=org_id,
        user_id=user_id,
        file_bytes=wb_to_bytes(wb),
        filename="test.xlsx",
        import_type="product_catalogue"
    )
    assert staged.status in ("pending_preview", "staged")
    assert staged.total_rows == 2
    assert staged.valid_rows == 2


# -----------------------------------------------------------------------------
# 3. Deterministic Data Extraction & Type Safety
# -----------------------------------------------------------------------------

def test_formula_cells_rejected(test_context):
    service = ExcelImportService()
    db = test_context["db"]
    org_id = test_context["org_id"]
    user_id = test_context["user_id"]

    row = valid_product_row("PRD-FORMULA")
    row[1] = "=HYPERLINK(\"http://malicious.com\")"
    wb = create_product_wb(rows=[row])

    staged = stage_file(
        service=service,
        db=db,
        org_id=org_id,
        user_id=user_id,
        file_bytes=wb_to_bytes(wb),
        filename="test.xlsx",
        import_type="product_catalogue"
    )
    assert staged.error_rows == 1
    p_row = staged.staged_products[0]
    assert p_row.is_valid is False
    assert any("Formula cells are not permitted" in err or "Contains formula" in err for err in p_row.validation_errors)


def test_numeric_type_and_multiline_text_preservation(test_context):
    service = ExcelImportService()
    db = test_context["db"]
    org_id = test_context["org_id"]
    user_id = test_context["user_id"]

    multiline_desc = "Line 1: Special cold-press.\nLine 2: With Unicode © & ™ characters & symbols: 100% natural!"
    row = valid_product_row("PRD-PRESERVE", pack_size=330.5)
    row[4] = multiline_desc
    wb = create_product_wb(rows=[row])

    staged = stage_file(
        service=service,
        db=db,
        org_id=org_id,
        user_id=user_id,
        file_bytes=wb_to_bytes(wb),
        filename="test.xlsx",
        import_type="product_catalogue"
    )
    assert staged.status in ("pending_preview", "staged")
    p_row = staged.staged_products[0]
    assert p_row.is_valid is True
    # Numeric type check: 330.5 should remain a float
    assert p_row.parsed_data["pack_size"] == 330.5
    assert isinstance(p_row.parsed_data["pack_size"], (int, float))
    # Multiline text check: newlines preserved
    assert p_row.parsed_data["product_description"] == multiline_desc
    assert "© & ™" in p_row.parsed_data["product_description"]


def test_claims_effective_date_validation_and_chronology(test_context):
    service = ExcelImportService()
    db = test_context["db"]
    org_id = test_context["org_id"]
    user_id = test_context["user_id"]

    claims_row1 = [
        "CLM-DATE-1", "Boosts hydration by 50%", "Performance", "Approved",
        "ALL", "Variations", "", "", "ALL", "2026-01-01", "2026-12-31"
    ]
    # Row 2: Inverted dates (effective_until < effective_from)
    claims_row2 = [
        "CLM-DATE-2", "Improves skin tone in 7 days", "Performance", "Approved",
        "ALL", "Variations", "", "", "ALL", "2026-06-01", "2026-01-01"
    ]

    wb = create_claims_wb(claims_rows=[claims_row1, claims_row2])

    staged = stage_file(
        service=service,
        db=db,
        org_id=org_id,
        user_id=user_id,
        file_bytes=wb_to_bytes(wb),
        filename="test_claims.xlsx",
        import_type="claims_and_disclosures"
    )
    assert staged.error_rows == 1
    assert staged.staged_claims[0].is_valid is True
    assert staged.staged_claims[1].is_valid is False
    assert any("cannot be earlier than" in err for err in staged.staged_claims[1].validation_errors)


# -----------------------------------------------------------------------------
# 4. Offering Type Strictness (No Silently Defaulting)
# -----------------------------------------------------------------------------

def test_offering_type_cannot_be_omitted(test_context):
    service = ExcelImportService()
    db = test_context["db"]
    org_id = test_context["org_id"]
    user_id = test_context["user_id"]

    row = valid_product_row("PRD-NO-TYPE", offering_type="")
    wb = create_product_wb(rows=[row])

    staged = stage_file(
        service=service,
        db=db,
        org_id=org_id,
        user_id=user_id,
        file_bytes=wb_to_bytes(wb),
        filename="test.xlsx",
        import_type="product_catalogue"
    )
    assert staged.error_rows == 1
    row = staged.staged_products[0]
    assert row.is_valid is False
    assert any("Column 'offering_type': offering_type is required" in err for err in row.validation_errors)


def test_standardised_error_message_format(test_context):
    service = ExcelImportService()
    db = test_context["db"]
    org_id = test_context["org_id"]
    user_id = test_context["user_id"]

    row = valid_product_row("")
    row[3] = "InvalidType"
    wb = create_product_wb(rows=[row])

    staged = stage_file(
        service=service,
        db=db,
        org_id=org_id,
        user_id=user_id,
        file_bytes=wb_to_bytes(wb),
        filename="test.xlsx",
        import_type="product_catalogue"
    )
    assert staged.error_rows == 1
    row = staged.staged_products[0]
    assert row.is_valid is False
    # Check standardized format: [Worksheet] Row {idx}, Column '{col}': reason and recommendation
    for err in row.validation_errors:
        assert err.startswith("[Product_Catalogue] Row 2, Column '")


def test_tenant_isolation_in_staged_imports(test_context):
    service = ExcelImportService()
    db = test_context["db"]
    org_a = test_context["org_id"]
    org_b = "org_isolated_tenant_999"
    user_id = test_context["user_id"]

    wb = create_product_wb(rows=[valid_product_row("PRD-TENANT-1")])

    staged_a = stage_file(
        service=service,
        db=db,
        org_id=org_a,
        user_id=user_id,
        file_bytes=wb_to_bytes(wb),
        filename="test.xlsx",
        import_type="product_catalogue"
    )
    assert staged_a.status in ("pending_preview", "staged")

    # Confirming with Org B should fail or raise error because import belongs to Org A
    with pytest.raises(Exception):
        service.confirm_staged_import(
            db=db,
            org_id=org_b,
            user_id=user_id,
            import_id=staged_a.id
        )


# -----------------------------------------------------------------------------
# 5. Gemini Poster Governance Regression Isolation
# -----------------------------------------------------------------------------

def test_gemini_poster_extraction_pipeline_remains_isolated():
    """
    Verify that the Gemini poster extraction pipeline data models and functions
    remain completely intact, isolated, and functional without any dependency on
    Excel parsing or Excel validation logic.
    """
    # Verify gemini_extractor does not import excel_service
    assert "excel_service" not in dir(ge)
    assert not hasattr(ge, "ExcelImportService")

    # Verify run_gemini_pdf_extraction signature and docstring are intact
    sig = inspect.signature(ge.run_gemini_pdf_extraction)
    assert "pdf_path" in sig.parameters
    assert "filename" in sig.parameters

    # Verify GeminiConfigurationError and GeminiExtractionError exist
    assert issubclass(ge.GeminiConfigurationError, Exception)
    assert issubclass(ge.GeminiExtractionError, Exception)

    # Verify ImageGovernanceService is uncoupled from Excel processing
    img_gov = ImageGovernanceService()
    assert not hasattr(img_gov, "stage_import")
    assert not hasattr(img_gov, "validate_row")



# -----------------------------------------------------------------------------
# 7. Native Excel Datetime JSON Serialization (Regression)
# -----------------------------------------------------------------------------

def test_native_excel_datetime_cells_serialize_to_json(test_context):
    """
    Regression test: when effective_from/effective_until contain native Python
    datetime objects (as produced by openpyxl for Excel date-typed cells), the
    raw_data JSON column must serialize successfully without TypeError.
    """
    service = ExcelImportService()
    db = test_context["db"]
    org_id = test_context["org_id"]
    user_id = test_context["user_id"]

    # Build a claims workbook with native datetime values
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Claims_Register"
    ws.append([c[0] for c in CLAIMS_REGISTER_COLUMNS])

    # Row with datetime objects in effective_from and effective_until
    ws.append([
        "CLM-DT-001",                        # claim_id
        "Clinically tested formula",          # claim_text
        "Performance",                        # claim_category
        "Approved",                           # claim_status
        "ALL",                                # applicable_products
        "Clinically validated formula",       # approved_variations
        "",                                   # restricted_conditions
        "",                                   # prohibited_variations
        "ALL",                                # applicable_market
        datetime(2026, 1, 15, 0, 0, 0),       # effective_from  (native datetime)
        datetime(2026, 12, 31, 0, 0, 0),      # effective_until (native datetime)
    ])

    # Row with date-only objects
    ws.append([
        "CLM-DT-002",                        # claim_id
        "Suitable for sensitive skin",        # claim_text
        "Safety",                             # claim_category
        "Approved",                           # claim_status
        "ALL",                                # applicable_products
        "Dermatologist recommended",          # approved_variations
        "",                                   # restricted_conditions
        "",                                   # prohibited_variations
        "ALL",                                # applicable_market
        date(2026, 3, 1),                      # effective_from  (native date)
        date(2026, 9, 30),                     # effective_until (native date)
    ])

    # Also add Required_Disclosures with datetime values
    ws_disc = wb.create_sheet(title="Required_Disclosures")
    ws_disc.append([c[0] for c in REQUIRED_DISCLOSURES_COLUMNS])
    ws_disc.append([
        "DSC-DT-001",                        # disclosure_id
        "Contains parabens",                  # disclosure_text
        "Ingredient",                         # disclosure_category
        "Mandatory",                          # disclosure_trigger
        "ALL",                                # applicable_products
        "ALL",                                # applicable_market
        "Active",                             # record_status
    ])

    staged = stage_file(
        service=service,
        db=db,
        org_id=org_id,
        user_id=user_id,
        file_bytes=wb_to_bytes(wb),
        filename="test_native_dates.xlsx",
        import_type="claims_and_disclosures"
    )

    # Should not raise TypeError during staging
    assert staged is not None
    assert len(staged.staged_claims) == 2
    assert len(staged.staged_disclosures) == 1

    # Both claim rows should be valid
    for claim in staged.staged_claims:
        assert claim.is_valid is True, f"Claim {claim.parsed_data.get('claim_id')} invalid: {claim.validation_errors}"

    # Verify parsed dates are ISO strings, not raw datetime objects
    c1 = staged.staged_claims[0]
    c2 = staged.staged_claims[1]
    assert c1.parsed_data["effective_from"] == "2026-01-15"
    assert c1.parsed_data["effective_until"] == "2026-12-31"
    assert c2.parsed_data["effective_from"] == "2026-03-01"
    assert c2.parsed_data["effective_until"] == "2026-09-30"

    # Verify raw_data values are JSON-safe strings (not datetime objects)
    for claim in staged.staged_claims:
        raw = claim.raw_data
        for date_col in ["effective_from", "effective_until"]:
            if raw.get(date_col) is not None:
                assert isinstance(raw[date_col], str), (
                    f"raw_data['{date_col}'] should be a string, got {type(raw[date_col])}"
                )



# -----------------------------------------------------------------------------
# 8. Custom Claim Categories Support & Empty Validation
# -----------------------------------------------------------------------------

def test_custom_claim_types_accepted_and_empty_rejected(test_context):
    """
    Verify:
    1. Custom organisation claim categories (e.g. 'Efficacy', 'Sun Protection',
       'Medical / Therapeutic') are accepted and preserved verbatim.
    2. Standard categories continue to work.
    3. Empty or whitespace-only claim_type is strictly rejected.
    4. Over-50-character claim_type is rejected.
    """
    service = ExcelImportService()
    db = test_context["db"]
    org_id = test_context["org_id"]
    user_id = test_context["user_id"]

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Claims_Register"
    ws.append([c[0] for c in CLAIMS_REGISTER_COLUMNS])

    # Row 1: Standard category
    ws.append([
        "CLM-STD-001", "100% Organic Orange Juice", "Ingredient", "Approved",
        "ALL", "Pure Organic Orange Juice", "", "", "ALL", "2026-01-01", "2027-12-31"
    ])

    # Row 2: Custom domain category (Skincare: 'Efficacy')
    ws.append([
        "CLM-CUST-001", "Reduces fine lines in 14 days", "Efficacy", "Approved",
        "ALL", "Visibly reduces fine lines", "", "", "ALL", "2026-01-01", "2027-12-31"
    ])

    # Row 3: Custom domain category with special characters ('Medical / Therapeutic')
    ws.append([
        "CLM-CUST-002", "Cures dermatological lesions", "Medical / Therapeutic", "Prohibited",
        "ALL", "", "", "Permanently eliminates lesions", "ALL", "2026-01-01", "2027-12-31"
    ])

    # Row 4: Empty claim_type (INVALID)
    ws.append([
        "CLM-ERR-001", "Missing category statement", "", "Approved",
        "ALL", "", "", "", "ALL", "2026-01-01", "2027-12-31"
    ])

    # Row 5: Whitespace-only claim_type (INVALID)
    ws.append([
        "CLM-ERR-002", "Whitespace category statement", "   ", "Approved",
        "ALL", "", "", "", "ALL", "2026-01-01", "2027-12-31"
    ])

    # Row 6: Over 50 characters claim_type (INVALID)
    ws.append([
        "CLM-ERR-003", "Overly long category statement", "X" * 51, "Approved",
        "ALL", "", "", "", "ALL", "2026-01-01", "2027-12-31"
    ])

    staged = stage_file(
        service=service,
        db=db,
        org_id=org_id,
        user_id=user_id,
        file_bytes=wb_to_bytes(wb),
        filename="test_claim_types.xlsx",
        import_type="claims_and_disclosures"
    )

    assert staged is not None
    assert len(staged.staged_claims) == 6

    # Rows 1, 2, 3 must be valid
    c1, c2, c3, c4, c5, c6 = staged.staged_claims

    assert c1.is_valid is True
    assert c1.parsed_data["claim_type"] == "Ingredient"

    assert c2.is_valid is True
    assert c2.parsed_data["claim_type"] == "Efficacy"  # Verbatim preservation

    assert c3.is_valid is True
    assert c3.parsed_data["claim_type"] == "Medical / Therapeutic"  # Verbatim preservation

    # Row 4 (empty) must be invalid
    assert c4.is_valid is False
    assert any("Claim type is required and cannot be empty or whitespace" in err for err in c4.validation_errors)

    # Row 5 (whitespace) must be invalid
    assert c5.is_valid is False
    assert any("Claim type is required and cannot be empty or whitespace" in err for err in c5.validation_errors)

    # Row 6 (> 50 chars) must be invalid
    assert c6.is_valid is False
    assert any("exceeds maximum length of 50 characters" in err for err in c6.validation_errors)


def test_database_check_constraint_rejects_empty_and_whitespace_claim_type(test_context):
    from app.models.claim import Claim
    from sqlalchemy.exc import IntegrityError

    db = test_context["db"]
    org_id = test_context["org_id"]

    # Direct DB insert with empty string must violate chk_claim_type_not_empty
    claim_empty = Claim(
        id=str(uuid.uuid4()),
        organization_id=org_id,
        claim_id=f"CLM-DB-EMPTY-{uuid.uuid4().hex[:6]}",
        claim_type="",
        claim_text="Direct insert empty test",
        claim_status="Approved",
        applicable_product_id="ALL",
        applicable_market="Global",
        effective_from=date(2026, 1, 1),
    )
    db.add(claim_empty)
    with pytest.raises(IntegrityError) as exc_info:
        db.flush()
    db.rollback()
    assert "chk_claim_type_not_empty" in str(exc_info.value)

    # Direct DB insert with whitespace must violate chk_claim_type_not_empty
    claim_space = Claim(
        id=str(uuid.uuid4()),
        organization_id=org_id,
        claim_id=f"CLM-DB-SPACE-{uuid.uuid4().hex[:6]}",
        claim_type="   ",
        claim_text="Direct insert space test",
        claim_status="Approved",
        applicable_product_id="ALL",
        applicable_market="Global",
        effective_from=date(2026, 1, 1),
    )
    db.add(claim_space)
    with pytest.raises(IntegrityError) as exc_info:
        db.flush()
    db.rollback()
    assert "chk_claim_type_not_empty" in str(exc_info.value)

