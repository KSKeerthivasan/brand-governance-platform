import io
import re
import hashlib
from datetime import datetime, date, timedelta
from typing import List, Dict, Any, Optional, Tuple
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.models.product import Product
from app.models.claim import Claim, RequiredDisclosure
from app.models.knowledge import (
    StagedImport,
    StagedImportProductRow,
    StagedImportClaimRow,
    StagedImportDisclosureRow,
)

# -----------------------------------------------------------------------------
# AUTHORITATIVE SCHEMA DEFINITIONS (Preserve exact columns and order)
# -----------------------------------------------------------------------------

PRODUCT_CATALOGUE_COLUMNS = [
    ("product_id", "Unique identifier for the product within organisation", True),
    ("product_name", "Official product or service name", True),
    ("product_category", "Category to which the offering belongs", True),
    ("offering_type", "Physical Product, Service, Digital Product, or Subscription", True),
    ("product_description", "Clear factual description of the product", True),
    ("variant_name", "Flavours, sizes, models or packaging variations", False),
    ("sku", "Stock keeping unit. Required when variant_name is specified", False),
    ("pack_size", "Positive numeric quantity or capacity, where relevant", False),
    ("pack_unit", "Unit such as ml, L, g, kg, pieces, or seats", False),
    ("ingredients_components", "Ingredients or core components (factual only; does not authorise claims)", False),
    ("key_features", "Factual product features (not unapproved promotional claims)", False),
    ("specifications", "Measurable technical details or storage requirements", False),
    ("known_limitations", "Known restrictions, exclusions or mandatory warnings", False),
    ("applicable_market", "Country or region in which record applies, or ALL", True),
    ("record_status", "Active, Inactive, or Discontinued", True),
]

CLAIMS_REGISTER_COLUMNS = [
    ("claim_id", "Unique claim identifier within organisation", True),
    ("claim_text", "Official promotional claim statement being governed", True),
    ("claim_type", "Ingredient, Nutritional, Health, Performance, Quality, Comparative, Environmental, Endorsement, Origin, Safety, Other", True),
    ("claim_status", "Approved, Restricted, or Prohibited", True),
    ("applicable_product_id", "Specific product_id or ALL (ALL scopes strictly within this organisation)", True),
    ("approved_variations", "Alternative authorised wording (semicolon or newline delimited). Prohibited claims cannot contain variations", False),
    ("restricted_conditions", "Mandatory conditions for Restricted claims (must be satisfied for use)", False),
    ("prohibited_variations", "Known wording variants explicitly disallowed by organisation", False),
    ("applicable_market", "Country or region in which claim authorisation applies, or ALL", True),
    ("effective_from", "Date authorisation begins (YYYY-MM-DD)", True),
    ("effective_until", "Expiry date (YYYY-MM-DD); blank means no scheduled expiry", False),
]

REQUIRED_DISCLOSURES_COLUMNS = [
    ("disclosure_id", "Unique disclosure identifier (e.g. DISC001)", True),
    ("disclosure_text", "Exact mandatory required disclosure wording", True),
    ("applicable_product_id", "Specific product_id or ALL (ALL scopes strictly within this organisation)", True),
    ("applicable_market", "Country or region, or ALL", True),
    ("applies_when", "Documented condition or scenario triggering mandatory inclusion", True),
    ("effective_from", "Date requirement takes effect (YYYY-MM-DD)", True),
    ("effective_until", "Expiry date (YYYY-MM-DD); blank means no scheduled expiry", False),
]

VALID_OFFERING_TYPES = {"Physical Product", "Service", "Digital Product", "Subscription"}
VALID_PRODUCT_RECORD_STATUSES = {"Active", "Inactive", "Discontinued"}
VALID_CLAIM_TYPES = {
    "Ingredient", "Nutritional", "Health", "Performance",
    "Quality", "Comparative", "Environmental", "Endorsement",
    "Origin", "Safety", "Other"
}
VALID_CLAIM_STATUSES = {"Approved", "Restricted", "Prohibited"}
VALID_DISCLOSURE_SEVERITIES = {"Low", "Medium", "High", "Critical"}
VALID_DISCLOSURE_RECORD_STATUSES = {"Active", "Inactive"}


class ExcelImportService:
    """
    Authoritative service for generating standardized Excel templates, staging imports safely
    without mutating active records, validating rows with exact sheet/row/column error reporting,
    and atomically committing verified data.
    """

    # -------------------------------------------------------------------------
    # 1. TEMPLATE GENERATION WITH INSTRUCTIONS WORKSHEET
    # -------------------------------------------------------------------------

    def generate_template(self, template_type: str) -> bytes:
        wb = openpyxl.Workbook()
        wb.remove(wb.active)  # Remove default blank sheet

        # Styles
        title_font = Font(name="Calibri", size=13, bold=True, color="186B42")
        section_font = Font(name="Calibri", size=11, bold=True, color="1E293B")
        header_font = Font(name="Calibri", size=10, bold=True, color="FFFFFF")
        header_fill = PatternFill(start_color="186B42", end_color="186B42", fill_type="solid")
        sub_header_fill = PatternFill(start_color="334155", end_color="334155", fill_type="solid")
        sample_font = Font(name="Calibri", size=10, italic=True, color="475569")
        regular_font = Font(name="Calibri", size=10, color="1E293B")
        note_fill = PatternFill(start_color="F1F5F9", end_color="F1F5F9", fill_type="solid")
        thin_border = Border(
            left=Side(style='thin', color='CBD5E1'),
            right=Side(style='thin', color='CBD5E1'),
            top=Side(style='thin', color='CBD5E1'),
            bottom=Side(style='thin', color='CBD5E1')
        )

        if template_type == "product_catalogue":
            # Sheet 1: Instructions
            ws_inst = wb.create_sheet(title="Instructions")
            ws_inst.append(["Inkloom AI — Product Catalogue Workbook Instructions"])
            ws_inst.cell(row=1, column=1).font = title_font

            ws_inst.append([])
            ws_inst.append(["IMPORTANT USAGE & GOVERNANCE PRINCIPLES:"])
            ws_inst.cell(row=3, column=1).font = section_font
            ws_inst.append([
                "1. Product vs SKU Rule: A product and its SKU are distinct. Distinct sellable variants (e.g. 250ml vs 1L) must be separate rows with their own SKU, sharing product_name."
            ])
            ws_inst.append([
                "2. Product Facts vs Marketing Claims: Factual features or ingredients listed here do NOT authorise promotional marketing claims (e.g., '100% natural', 'sugar-free'). Claims must be authorised in the Claims Register."
            ])
            ws_inst.append([
                "3. Applicable Market: Specify the country/region (e.g. 'India') or enter 'ALL' if universal across all target markets."
            ])
            ws_inst.append([
                "4. Date Format: Where dates are used, use YYYY-MM-DD format (e.g. 2026-01-01)."
            ])
            ws_inst.append([
                "5. Sample Data: Rows in the 'Product_Catalogue' sheet prefixed with [SAMPLE] demonstrate valid syntax and should be replaced with real organisation data."
            ])
            for r in range(4, 9):
                ws_inst.cell(row=r, column=1).font = regular_font

            ws_inst.append([])
            ws_inst.append(["COLUMN SPECIFICATION & FIELD GUIDANCE:"])
            ws_inst.cell(row=10, column=1).font = section_font

            guide_headers = ["Column #", "Field Name", "Required?", "Accepted Values / Format", "Description & Field Guidance"]
            ws_inst.append(guide_headers)
            for col_idx in range(1, len(guide_headers) + 1):
                c = ws_inst.cell(row=11, column=col_idx)
                c.font = header_font
                c.fill = sub_header_fill
                c.alignment = Alignment(horizontal="center", vertical="center")

            column_guidelines = [
                ("1", "product_id", "Required", "Unique alphanumeric string", "Unique identifier for product within organisation (e.g. FS-P001). Foreign key for claims."),
                ("2", "product_name", "Required", "Official product title", "Official commercial product name."),
                ("3", "product_category", "Required", "Category name", "Category to which offering belongs (e.g. Fruit Beverage, Personal Care)."),
                ("4", "offering_type", "Required", "Physical Product, Service, Digital Product, Subscription", "Must be explicitly specified to prevent silent misclassification of non-physical offerings (services, subscriptions, digital goods)."),
                ("5", "product_description", "Required", "Clear factual text", "Official factual description of offering."),
                ("6", "variant_name", "Optional", "Variant title", "Flavours, sizes, models, or packaging variations (e.g. 250 mL Glass Bottle)."),
                ("7", "sku", "Required if variant", "Unique SKU code", "Stock keeping unit. Required when variant_name is provided. Must be unique within file."),
                ("8", "pack_size", "Optional/Conditional", "Positive number (> 0)", "Net quantity or volume (e.g. 250, 1000). Must be positive."),
                ("9", "pack_unit", "Optional/Conditional", "ml, L, g, kg, pieces, etc.", "Standard unit of measure for pack_size."),
                ("10", "ingredients_components", "Optional/Conditional", "Semicolon/comma text", "Core ingredients or components. Factual statement only; does not authorise promotional claims."),
                ("11", "key_features", "Optional", "Semicolon-delimited features", "Factual product features. Promotional marketing claims must be authorised separately in Claims Register."),
                ("12", "specifications", "Optional", "Technical specs text", "Measurable technical details (e.g. storage temperature 2-5C, shelf life)."),
                ("13", "known_limitations", "Optional", "Known restrictions/allergens", "Mandatory warnings, known exclusions, or allergen presence."),
                ("14", "applicable_market", "Required", "Market name or ALL", "Jurisdiction where record applies (e.g. India, EU, ALL)."),
                ("15", "record_status", "Required", "Active, Inactive, Discontinued", "Only 'Active' records are evaluated by the governance engine."),
            ]
            for row in column_guidelines:
                ws_inst.append(list(row))
                for col_idx in range(1, len(row) + 1):
                    c = ws_inst.cell(row=ws_inst.max_row, column=col_idx)
                    c.font = regular_font
                    c.border = thin_border

            for col in ws_inst.columns:
                max_len = max(len(str(cell.value or '')) for cell in col)
                col_letter = get_column_letter(col[0].column)
                ws_inst.column_dimensions[col_letter].width = max(min(max_len + 3, 50), 12)

            # Sheet 2: Product_Catalogue
            ws = wb.create_sheet(title="Product_Catalogue")
            headers = [col[0] for col in PRODUCT_CATALOGUE_COLUMNS]
            ws.append(headers)
            for col_num in range(1, len(headers) + 1):
                cell = ws.cell(row=1, column=col_num)
                cell.font = header_font
                cell.fill = header_fill
                cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

            sample_rows = [
                [
                    "FS-P001", "Valencia Orange Cold-Pressed Juice", "Fruit Beverage",
                    "Physical Product", "Single-ingredient juice pressed from ripe Valencia oranges (100%), HPP processed.",
                    "250 mL Glass Bottle", "VO-250-HPP", 250, "ml",
                    "Valencia Orange Juice (100%)", "Cold-Pressed; No Added Sugar; 100% Juice",
                    "250 mL bottle; keep refrigerated 2-5C", "Store chilled; consume within 24 hours of opening",
                    "India", "Active"
                ],
                [
                    "FS-P002", "Pink Guava Pomegranate Nectar", "Fruit Beverage",
                    "Physical Product", "Artisanal blend of pink guava puree and pomegranate juice, flash pasteurized.",
                    "250 mL Glass Bottle", "PG-250-FP", 250, "ml",
                    "Pink Guava Puree (60%), Pomegranate Juice (40%)", "No Added Preservatives; Flash Pasteurized",
                    "250 mL glass bottle", "Contains fruit sediment; shake well before opening",
                    "India", "Active"
                ],
                [
                    "FS-P003", "Garden Tomato Celery Blend", "Vegetable Beverage",
                    "Physical Product", "Savory cold-pressed tomato juice infused with organic celery stalk extract.",
                    "250 mL Glass Bottle", "TC-250-CP", 250, "ml",
                    "Tomato Juice (86%), Celery Extract (14%)", "Organic Celery; Rich in Lycopene",
                    "250 mL glass bottle; keep refrigerated 2-5C", "Contains Celery allergen; store chilled",
                    "India", "Active"
                ]
            ]
            for row in sample_rows:
                ws.append(row)
                for col_idx in range(1, len(row) + 1):
                    c = ws.cell(row=ws.max_row, column=col_idx)
                    c.font = sample_font
                    c.border = thin_border

            for col in ws.columns:
                max_len = max(len(str(cell.value or '')) for cell in col)
                col_letter = get_column_letter(col[0].column)
                ws.column_dimensions[col_letter].width = max(max_len + 4, 15)
            wb.active = ws

        elif template_type == "claims_and_disclosures":
            # Sheet 1: Instructions
            ws_inst = wb.create_sheet(title="Instructions")
            ws_inst.append(["Inkloom AI — Claims Register & Required Disclosures Workbook Instructions"])
            ws_inst.cell(row=1, column=1).font = title_font

            ws_inst.append([])
            ws_inst.append(["CORE GOVERNANCE PRINCIPLES & CONDITIONAL VALIDATION:"])
            ws_inst.cell(row=3, column=1).font = section_font
            ws_inst.append([
                "1. Claims Register vs Required Disclosures: Claims determine whether promotional statements are Approved, Restricted, or Prohibited. Required Disclosures are mandatory statements that MUST appear when specific triggers apply. They are separate concepts."
            ])
            ws_inst.append([
                "2. Scope of 'ALL': Using 'ALL' in applicable_product_id scopes strictly to offerings within YOUR organisation. It never crosses tenant boundaries."
            ])
            ws_inst.append([
                "3. Staged References & Import Sequence: Claims can reference newly staged products in the same session. Confirm your Product Catalogue before confirming Claims to ensure relational integrity."
            ])
            ws_inst.append([
                "4. Date Semantics: Dates must use YYYY-MM-DD format. The effective_until end date is INCLUSIVE (effective_from <= current_date <= effective_until). Leaving effective_until blank indicates an ongoing claim with no scheduled expiration."
            ])
            ws_inst.append([
                "3. Conditional Validation for Claims:"
            ])
            ws_inst.append([
                "   - Approved: claim_text required; cannot contradict with prohibited variations; restricted_conditions optional."
            ])
            ws_inst.append([
                "   - Restricted: restricted_conditions MUST be provided. Governance engine verifies conditions before authorising."
            ])
            ws_inst.append([
                "   - Prohibited: Strictly disallowed. approved_variations MUST NOT be provided (contradiction error)."
            ])
            ws_inst.append([
                "4. Date Format: Use YYYY-MM-DD (e.g. 2026-01-01). effective_until must be on or after effective_from."
            ])
            ws_inst.append([
                "5. Unregistered Claims: Promotional claims not found in this register will be flagged as 'Not found in Claims Register' (not falsely marked as false)."
            ])
            for r in range(4, 12):
                ws_inst.cell(row=r, column=1).font = regular_font

            ws_inst.append([])
            ws_inst.append(["CLAIMS REGISTER (SHEET 2) COLUMN GUIDANCE:"])
            ws_inst.cell(row=13, column=1).font = section_font

            guide_headers = ["Column #", "Field Name", "Required?", "Accepted Values / Format", "Description & Field Guidance"]
            ws_inst.append(guide_headers)
            for col_idx in range(1, len(guide_headers) + 1):
                c = ws_inst.cell(row=14, column=col_idx)
                c.font = header_font
                c.fill = sub_header_fill

            claims_guide = [
                ("1", "claim_id", "Required", "Unique alphanumeric string", "Unique claim ID within organisation (e.g. CLM001)."),
                ("2", "claim_text", "Required", "Exact official claim statement", "The core promotional statement being governed."),
                ("3", "claim_type", "Required", "Ingredient, Nutritional, Health, Performance, Quality, Comparative, Environmental, Endorsement, Origin, Safety, Other", "Formal classification of claim."),
                ("4", "claim_status", "Required", "Approved, Restricted, Prohibited", "Status determining authorisation enforcement."),
                ("5", "applicable_product_id", "Required", "Valid product_id or ALL", "Product SKU or 'ALL' (tenant-scoped). Must exist in active catalogue."),
                ("6", "approved_variations", "Optional (Forbidden for Prohibited)", "Semicolon or newline text", "Authorised alternative phrases. Must not extend claim meaning."),
                ("7", "restricted_conditions", "Mandatory for Restricted claims", "Condition text", "Preconditions, qualifying statements, or disclaimers required for use."),
                ("8", "prohibited_variations", "Optional", "Semicolon or newline text", "Known wording variants that organisation explicitly disallows."),
                ("9", "applicable_market", "Required", "Market name or ALL", "Jurisdiction where claim authorisation applies."),
                ("10", "effective_from", "Required", "Date YYYY-MM-DD", "Date authorisation begins. Future dates cannot be authorised yet."),
                ("11", "effective_until", "Optional", "Date YYYY-MM-DD", "Expiry date (>= effective_from). Expired claims cannot be authorised."),
            ]
            for row in claims_guide:
                ws_inst.append(list(row))
                for col_idx in range(1, len(row) + 1):
                    c = ws_inst.cell(row=ws_inst.max_row, column=col_idx)
                    c.font = regular_font
                    c.border = thin_border

            ws_inst.append([])
            ws_inst.append(["REQUIRED DISCLOSURES (SHEET 3) COLUMN GUIDANCE:"])
            ws_inst.cell(row=ws_inst.max_row, column=1).font = section_font
            ws_inst.append(guide_headers)
            for col_idx in range(1, len(guide_headers) + 1):
                c = ws_inst.cell(row=ws_inst.max_row, column=col_idx)
                c.font = header_font
                c.fill = sub_header_fill

            disc_guide = [
                ("1", "disclosure_id", "Required", "Unique alphanumeric string", "Unique disclosure ID (e.g. DISC001)."),
                ("2", "disclosure_text", "Required", "Exact mandatory wording", "Exact statement required to appear on packaging/collateral."),
                ("3", "applicable_product_id", "Required", "Valid product_id or ALL", "Target product or ALL within organisation."),
                ("4", "applicable_market", "Required", "Market name or ALL", "Jurisdiction where disclosure applies."),
                ("5", "applies_when", "Required", "Condition text", "Documented scenario triggering mandatory inclusion."),
                ("6", "effective_from", "Required", "Date YYYY-MM-DD", "Date disclosure takes effect."),
                ("7", "effective_until", "Optional", "Date YYYY-MM-DD", "Expiry date (>= effective_from)."),
            ]
            for row in disc_guide:
                ws_inst.append(list(row))
                for col_idx in range(1, len(row) + 1):
                    c = ws_inst.cell(row=ws_inst.max_row, column=col_idx)
                    c.font = regular_font
                    c.border = thin_border

            for col in ws_inst.columns:
                max_len = max(len(str(cell.value or '')) for cell in col)
                col_letter = get_column_letter(col[0].column)
                ws_inst.column_dimensions[col_letter].width = max(min(max_len + 3, 50), 12)

            # Sheet 2: Claims_Register
            ws_claims = wb.create_sheet(title="Claims_Register")
            claims_headers = [col[0] for col in CLAIMS_REGISTER_COLUMNS]
            ws_claims.append(claims_headers)
            for col_num in range(1, len(claims_headers) + 1):
                c = ws_claims.cell(row=1, column=col_num)
                c.font = header_font
                c.fill = header_fill
                c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

            sample_claims = [
                [
                    "CLM001", "Made with 100% cold-pressed Valencia oranges", "Ingredient",
                    "Approved", "FS-P001", "Contains 100% cold-pressed Valencia orange juice",
                    "", "Made with 100% raw unpasteurized juice", "India", "2026-01-01", "2026-12-31"
                ],
                [
                    "CLM002", "No Added Sugar", "Nutritional",
                    "Restricted", "FS-P001", "",
                    "Only for formulations without added sucrose or syrups", "Sugar Free", "India", "2026-01-01", ""
                ],
                [
                    "CLM003", "Cures digestive disorders and flushes toxins", "Health",
                    "Prohibited", "ALL", "", "", "Treats gut ailments", "India", "2026-01-01", ""
                ]
            ]
            for row in sample_claims:
                ws_claims.append(row)
                for col_idx in range(1, len(row) + 1):
                    c = ws_claims.cell(row=ws_claims.max_row, column=col_idx)
                    c.font = sample_font
                    c.border = thin_border

            for col in ws_claims.columns:
                max_len = max(len(str(cell.value or '')) for cell in col)
                col_letter = get_column_letter(col[0].column)
                ws_claims.column_dimensions[col_letter].width = max(max_len + 4, 15)

            # Sheet 3: Required_Disclosures
            ws_disc = wb.create_sheet(title="Required_Disclosures")
            disc_headers = [col[0] for col in REQUIRED_DISCLOSURES_COLUMNS]
            ws_disc.append(disc_headers)
            disc_fill = PatternFill(start_color="1E293B", end_color="1E293B", fill_type="solid")
            for col_num in range(1, len(disc_headers) + 1):
                c = ws_disc.cell(row=1, column=col_num)
                c.font = header_font
                c.fill = disc_fill
                c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

            sample_disclosures = [
                [
                    "DISC001",
                    "Keep refrigerated at 2°C to 5°C. Shake well before drinking. Consume within 24 hours of opening.",
                    "ALL", "India", "Applies to all perishable beverage packaging and PDPs", "2026-01-01", ""
                ],
                [
                    "DISC002",
                    "Contains Celery (14%). Keep refrigerated at 2°C to 5°C; consume within 24 hours of opening.",
                    "FS-P003", "India", "Mandatory on all customer-facing collateral for Garden Tomato Celery SKU", "2026-01-01", ""
                ]
            ]
            for row in sample_disclosures:
                ws_disc.append(row)
                for col_idx in range(1, len(row) + 1):
                    c = ws_disc.cell(row=ws_disc.max_row, column=col_idx)
                    c.font = sample_font
                    c.border = thin_border

            for col in ws_disc.columns:
                max_len = max(len(str(cell.value or '')) for cell in col)
                col_letter = get_column_letter(col[0].column)
                ws_disc.column_dimensions[col_letter].width = max(max_len + 4, 15)
            wb.active = ws_claims

        buf = io.BytesIO()
        wb.save(buf)
        return buf.getvalue()

    # -------------------------------------------------------------------------
    # 2. STAGING & VALIDATION (PREVIEW ONLY - ZERO ACTIVE RECORD MUTATION)
    # -------------------------------------------------------------------------

    def parse_and_stage_excel(
        self,
        db: Session,
        org_id: str,
        user_id: Optional[str],
        file_name: str,
        file_bytes: bytes,
        idempotency_key: str,
        import_type: str
    ) -> StagedImport:
        file_hash = hashlib.sha256(file_bytes).hexdigest()

        existing_import = db.query(StagedImport).filter(
            StagedImport.organization_id == org_id,
            StagedImport.idempotency_key == idempotency_key
        ).first()

        if existing_import:
            return existing_import

        staged_import = StagedImport(
            organization_id=org_id,
            import_type=import_type,
            idempotency_key=idempotency_key,
            file_name=file_name,
            file_sha256=file_hash,
            status="pending_preview",
            created_by=user_id,
            total_rows=0,
            valid_rows=0,
            error_rows=0,
            has_disclosures=False,
            validation_summary={}
        )
        db.add(staged_import)
        db.flush()

        try:
            wb = openpyxl.load_workbook(io.BytesIO(file_bytes), data_only=True)
        except Exception as e:
            staged_import.status = "failed"
            staged_import.validation_summary = {"file_error": f"Invalid Excel (.xlsx) file: {str(e)}"}
            db.commit()
            return staged_import

        if import_type == "product_catalogue":
            self._stage_product_catalogue(db, org_id, staged_import, wb)
        elif import_type == "claims_and_disclosures":
            self._stage_claims_and_disclosures(db, org_id, staged_import, wb)
        else:
            staged_import.status = "failed"
            staged_import.validation_summary = {"file_error": f"Unsupported import type: {import_type}"}
            db.commit()
            return staged_import

        db.commit()
        db.refresh(staged_import)
        return staged_import

    def _stage_product_catalogue(
        self,
        db: Session,
        org_id: str,
        staged_import: StagedImport,
        wb: openpyxl.Workbook
    ):
        target_sheet_name = None
        for name in wb.sheetnames:
            norm_name = name.strip().lower().replace(" ", "_")
            if norm_name in ("product_catalogue", "products", "sheet1"):
                target_sheet_name = name
                break

        if not target_sheet_name:
            staged_import.status = "failed"
            staged_import.validation_summary = {
                "file_error": f"Required worksheet 'Product_Catalogue' not found. Sheets present: {wb.sheetnames}"
            }
            return

        ws = wb[target_sheet_name]
        rows = list(ws.iter_rows(values_only=True))
        if not rows or len(rows) < 1:
            staged_import.status = "failed"
            staged_import.validation_summary = {"file_error": "Worksheet is empty"}
            return

        header_row = [str(c or '').strip() for c in rows[0]]
        expected_cols = [c[0] for c in PRODUCT_CATALOGUE_COLUMNS]
        col_index_map = {col.lower(): idx for idx, col in enumerate(header_row)}

        missing_headers = [c for c in expected_cols if c.lower() not in col_index_map]
        if missing_headers:
            staged_import.status = "failed"
            staged_import.validation_summary = {
                "file_error": f"Missing required columns in header: {', '.join(missing_headers)}"
            }
            return

        seen_product_ids = set()
        seen_skus = set()
        total_rows = 0
        valid_rows = 0
        error_rows = 0

        for row_idx, row_values in enumerate(rows[1:], start=2):
            if not any(v is not None and str(v).strip() != '' for v in row_values):
                continue

            total_rows += 1
            raw_dict = {}
            for col_name in expected_cols:
                idx = col_index_map[col_name.lower()]
                raw_dict[col_name] = row_values[idx] if idx < len(row_values) else None

            row_errors: List[str] = []
            parsed_data: Dict[str, Any] = {}

            # 1. product_id
            p_id = str(raw_dict.get("product_id") or '').strip()
            if not p_id:
                row_errors.append(f"[Product_Catalogue] Row {row_idx}, Column 'product_id': Unique identifier is required")
            elif p_id in seen_product_ids:
                row_errors.append(f"[Product_Catalogue] Row {row_idx}, Column 'product_id': Duplicate product_id '{p_id}' within this import file")
            else:
                seen_product_ids.add(p_id)
            parsed_data["product_id"] = p_id

            # 2. product_name
            p_name = str(raw_dict.get("product_name") or '').strip()
            if not p_name:
                row_errors.append(f"[Product_Catalogue] Row {row_idx}, Column 'product_name': Product name is required")
            parsed_data["product_name"] = p_name

            # 3. product_category
            p_cat = str(raw_dict.get("product_category") or '').strip()
            if not p_cat:
                row_errors.append(f"[Product_Catalogue] Row {row_idx}, Column 'product_category': Category is required")
            parsed_data["product_category"] = p_cat

            # 4. offering_type (Required: Physical Product, Service, Digital Product, Subscription)
            off_type_raw = str(raw_dict.get("offering_type") or '').strip()
            if not off_type_raw:
                row_errors.append(f"[Product_Catalogue] Row {row_idx}, Column 'offering_type': offering_type is required. Permitted values: {', '.join(sorted(VALID_OFFERING_TYPES))}")
                off_type = "Physical Product"
            else:
                off_type = next((v for v in VALID_OFFERING_TYPES if v.lower() == off_type_raw.lower()), off_type_raw)
                if off_type not in VALID_OFFERING_TYPES:
                    row_errors.append(f"[Product_Catalogue] Row {row_idx}, Column 'offering_type': Invalid offering_type '{off_type_raw}'. Permitted: {', '.join(sorted(VALID_OFFERING_TYPES))}")
            parsed_data["offering_type"] = off_type

            # 5. product_description
            p_desc = str(raw_dict.get("product_description") or '').strip()
            if not p_desc:
                row_errors.append(f"[Product_Catalogue] Row {row_idx}, Column 'product_description': Description is required")
            parsed_data["product_description"] = p_desc

            # 6. variant_name & sku (Product-variant rule: if variant_name provided, sku is required)
            v_name = str(raw_dict.get("variant_name") or '').strip() or None
            sku_val = str(raw_dict.get("sku") or '').strip() or None

            if v_name and not sku_val:
                row_errors.append(f"[Product_Catalogue] Row {row_idx}, Column 'sku': SKU is required when variant_name is specified")

            if sku_val:
                if sku_val in seen_skus:
                    row_errors.append(f"[Product_Catalogue] Row {row_idx}, Column 'sku': Duplicate SKU '{sku_val}' within this import file")
                else:
                    seen_skus.add(sku_val)

            parsed_data["variant_name"] = v_name
            parsed_data["sku"] = sku_val

            # 7. pack_size & pack_unit
            pack_size_val = raw_dict.get("pack_size")
            if pack_size_val is not None and str(pack_size_val).strip() != '':
                try:
                    ps_float = float(pack_size_val)
                    if ps_float <= 0:
                        row_errors.append(f"[Product_Catalogue] Row {row_idx}, Column 'pack_size': pack_size must be a positive number (> 0), got: '{pack_size_val}'")
                        parsed_data["pack_size"] = None
                    else:
                        parsed_data["pack_size"] = ps_float
                except (ValueError, TypeError):
                    row_errors.append(f"[Product_Catalogue] Row {row_idx}, Column 'pack_size': Invalid numeric pack_size: '{pack_size_val}'")
                    parsed_data["pack_size"] = None
            else:
                parsed_data["pack_size"] = None

            parsed_data["pack_unit"] = str(raw_dict.get("pack_unit") or '').strip() or None
            parsed_data["ingredients_components"] = str(raw_dict.get("ingredients_components") or '').strip() or None
            parsed_data["key_features"] = str(raw_dict.get("key_features") or '').strip() or None
            parsed_data["specifications"] = str(raw_dict.get("specifications") or '').strip() or None
            parsed_data["known_limitations"] = str(raw_dict.get("known_limitations") or '').strip() or None

            # 8. applicable_market
            market = str(raw_dict.get("applicable_market") or '').strip()
            if not market:
                row_errors.append(f"[Product_Catalogue] Row {row_idx}, Column 'applicable_market': Market is required (specify market or 'ALL')")
            parsed_data["applicable_market"] = market

            # 9. record_status
            status_val_raw = str(raw_dict.get("record_status") or 'Active').strip()
            status_val = next((v for v in VALID_PRODUCT_RECORD_STATUSES if v.lower() == status_val_raw.lower()), status_val_raw)
            if status_val not in VALID_PRODUCT_RECORD_STATUSES:
                row_errors.append(f"[Product_Catalogue] Row {row_idx}, Column 'record_status': Invalid record_status '{status_val_raw}'. Permitted: {', '.join(sorted(VALID_PRODUCT_RECORD_STATUSES))}")
            parsed_data["record_status"] = status_val

            is_valid = len(row_errors) == 0
            if is_valid:
                valid_rows += 1
            else:
                error_rows += 1

            staged_row = StagedImportProductRow(
                organization_id=org_id,
                import_id=staged_import.id,
                row_number=row_idx,
                raw_data=raw_dict,
                parsed_data=parsed_data,
                validation_errors=row_errors,
                is_valid=is_valid
            )
            db.add(staged_row)

        staged_import.total_rows = total_rows
        staged_import.valid_rows = valid_rows
        staged_import.error_rows = error_rows
        staged_import.validation_summary = {
            "total_rows": total_rows,
            "valid_rows": valid_rows,
            "error_rows": error_rows,
            "can_commit": error_rows == 0 and total_rows > 0
        }

    def _stage_claims_and_disclosures(
        self,
        db: Session,
        org_id: str,
        staged_import: StagedImport,
        wb: openpyxl.Workbook
    ):
        # 1. Sheet 1: Claims_Register
        claims_sheet_name = None
        for name in wb.sheetnames:
            norm_name = name.strip().lower().replace(" ", "_")
            if norm_name in ("claims_register", "claims", "sheet1"):
                claims_sheet_name = name
                break

        if not claims_sheet_name:
            staged_import.status = "failed"
            staged_import.validation_summary = {
                "file_error": f"Required worksheet 'Claims_Register' not found. Sheets present: {wb.sheetnames}"
            }
            return

        ws_claims = wb[claims_sheet_name]
        claims_rows = list(ws_claims.iter_rows(values_only=True))
        if not claims_rows or len(claims_rows) < 1:
            staged_import.status = "failed"
            staged_import.validation_summary = {"file_error": "Claims_Register worksheet is empty"}
            return

        header_row = [str(c or '').strip() for c in claims_rows[0]]
        expected_claims_cols = [c[0] for c in CLAIMS_REGISTER_COLUMNS]
        col_index_map = {col.lower(): idx for idx, col in enumerate(header_row)}

        missing_headers = [c for c in expected_claims_cols if c.lower() not in col_index_map]
        if missing_headers:
            staged_import.status = "failed"
            staged_import.validation_summary = {
                "file_error": f"Missing required columns in Claims_Register: {', '.join(missing_headers)}"
            }
            return

        # Fetch active products in this organization to validate applicable_product_id
        active_products = db.query(Product).filter(Product.organization_id == org_id).all()
        known_product_ids = {p.product_id for p in active_products}

        # Also include products staged in pending, valid Product Catalogue imports for this organization
        staged_product_rows = db.query(StagedImportProductRow).join(
            StagedImport, StagedImportProductRow.import_id == StagedImport.id
        ).filter(
            StagedImport.organization_id == org_id,
            StagedImport.status == "pending_preview",
            StagedImport.import_type == "product_catalogue",
            StagedImportProductRow.is_valid == True
        ).all()
        for spr in staged_product_rows:
            p_id = spr.parsed_data.get("product_id") if spr.parsed_data else None
            if p_id:
                known_product_ids.add(p_id)

        seen_claim_ids = set()
        total_rows = 0
        valid_rows = 0
        error_rows = 0

        for row_idx, row_values in enumerate(claims_rows[1:], start=2):
            if not any(v is not None and str(v).strip() != '' for v in row_values):
                continue

            total_rows += 1
            raw_dict = {}
            for col_name in expected_claims_cols:
                idx = col_index_map[col_name.lower()]
                raw_dict[col_name] = row_values[idx] if idx < len(row_values) else None

            row_errors: List[str] = []
            parsed_data: Dict[str, Any] = {}

            # claim_id
            c_id = str(raw_dict.get("claim_id") or '').strip()
            if not c_id:
                row_errors.append(f"[Claims_Register] Row {row_idx}, Column 'claim_id': Claim ID is required")
            elif c_id in seen_claim_ids:
                row_errors.append(f"[Claims_Register] Row {row_idx}, Column 'claim_id': Duplicate claim_id '{c_id}' within this import file")
            else:
                seen_claim_ids.add(c_id)
            parsed_data["claim_id"] = c_id

            # claim_text
            c_text = str(raw_dict.get("claim_text") or '').strip()
            if not c_text:
                row_errors.append(f"[Claims_Register] Row {row_idx}, Column 'claim_text': Claim text is required")
            parsed_data["claim_text"] = c_text

            # claim_type
            c_type_raw = str(raw_dict.get("claim_type") or '').strip()
            normalized_type = next((v for v in VALID_CLAIM_TYPES if v.lower() == c_type_raw.lower()), c_type_raw)
            if normalized_type not in VALID_CLAIM_TYPES:
                row_errors.append(f"[Claims_Register] Row {row_idx}, Column 'claim_type': Invalid claim_type '{c_type_raw}'. Permitted: {', '.join(sorted(VALID_CLAIM_TYPES))}")
            parsed_data["claim_type"] = normalized_type

            # claim_status
            c_status_raw = str(raw_dict.get("claim_status") or '').strip()
            c_status = next((v for v in VALID_CLAIM_STATUSES if v.lower() == c_status_raw.lower()), c_status_raw)
            if c_status not in VALID_CLAIM_STATUSES:
                row_errors.append(f"[Claims_Register] Row {row_idx}, Column 'claim_status': Invalid claim_status '{c_status_raw}'. Permitted: {', '.join(sorted(VALID_CLAIM_STATUSES))}")
            parsed_data["claim_status"] = c_status

            # applicable_product_id (Validate against active organisation catalogue or 'ALL')
            app_prod = str(raw_dict.get("applicable_product_id") or '').strip()
            if not app_prod:
                row_errors.append(f"[Claims_Register] Row {row_idx}, Column 'applicable_product_id': Product reference is required (enter product_id or 'ALL')")
            elif app_prod != "ALL" and app_prod not in known_product_ids:
                row_errors.append(f"[Claims_Register] Row {row_idx}, Column 'applicable_product_id': Referenced product_id '{app_prod}' not found in active organisation catalogue")
            parsed_data["applicable_product_id"] = app_prod

            # approved_variations & prohibited_variations
            app_var = str(raw_dict.get("approved_variations") or '').strip() or None
            proh_var = str(raw_dict.get("prohibited_variations") or '').strip() or None

            # Conditional Validation:
            # - Restricted claims MUST specify restricted_conditions
            restr_cond = str(raw_dict.get("restricted_conditions") or '').strip() or None
            if c_status == "Restricted" and not restr_cond:
                row_errors.append(f"[Claims_Register] Row {row_idx}, Column 'restricted_conditions': Restricted claims must specify 'restricted_conditions'")

            # - Prohibited claims CANNOT contain approved_variations (contradiction)
            if c_status == "Prohibited" and app_var:
                row_errors.append(f"[Claims_Register] Row {row_idx}, Column 'approved_variations': Prohibited claims cannot contain approved_variations (contradiction)")

            parsed_data["approved_variations"] = app_var
            parsed_data["restricted_conditions"] = restr_cond
            parsed_data["prohibited_variations"] = proh_var

            # applicable_market
            market = str(raw_dict.get("applicable_market") or '').strip()
            if not market:
                row_errors.append(f"[Claims_Register] Row {row_idx}, Column 'applicable_market': Market is required")
            parsed_data["applicable_market"] = market

            # effective_from
            eff_from_val = raw_dict.get("effective_from")
            parsed_eff_from = self._parse_date(eff_from_val)
            if not parsed_eff_from:
                row_errors.append(f"[Claims_Register] Row {row_idx}, Column 'effective_from': Must be a valid date (YYYY-MM-DD), got: '{eff_from_val}'")
            parsed_data["effective_from"] = parsed_eff_from.isoformat() if parsed_eff_from else None

            # effective_until (Optional; if present, must be >= effective_from)
            eff_until_val = raw_dict.get("effective_until")
            parsed_eff_until = self._parse_date(eff_until_val) if eff_until_val else None
            if eff_until_val and not parsed_eff_until:
                row_errors.append(f"[Claims_Register] Row {row_idx}, Column 'effective_until': Must be a valid date (YYYY-MM-DD), got: '{eff_until_val}'")
            elif parsed_eff_from and parsed_eff_until and parsed_eff_until < parsed_eff_from:
                row_errors.append(f"[Claims_Register] Row {row_idx}, Column 'effective_until': effective_until ({parsed_eff_until}) cannot be earlier than effective_from ({parsed_eff_from})")
            parsed_data["effective_until"] = parsed_eff_until.isoformat() if parsed_eff_until else None

            is_valid = len(row_errors) == 0
            if is_valid:
                valid_rows += 1
            else:
                error_rows += 1

            staged_claim = StagedImportClaimRow(
                organization_id=org_id,
                import_id=staged_import.id,
                row_number=row_idx,
                raw_data=raw_dict,
                parsed_data=parsed_data,
                validation_errors=row_errors,
                is_valid=is_valid
            )
            db.add(staged_claim)

        # 2. Sheet 2: Required_Disclosures (OPTIONAL WORKSHEET)
        has_disclosures = False
        disc_sheet_name = None
        for name in wb.sheetnames:
            norm_name = name.strip().lower().replace(" ", "_")
            if norm_name in ("required_disclosures", "disclosures"):
                disc_sheet_name = name
                break

        if disc_sheet_name:
            ws_disc = wb[disc_sheet_name]
            disc_rows = list(ws_disc.iter_rows(values_only=True))
            if disc_rows and len(disc_rows) > 1:
                has_disclosures = True
                disc_header_row = [str(c or '').strip() for c in disc_rows[0]]
                disc_col_map = {col.lower(): idx for idx, col in enumerate(disc_header_row)}
                seen_disc_ids = set()

                for row_idx, row_values in enumerate(disc_rows[1:], start=2):
                    if not any(v is not None and str(v).strip() != '' for v in row_values):
                        continue

                    total_rows += 1
                    raw_dict = {}
                    for col_name, _, _ in REQUIRED_DISCLOSURES_COLUMNS:
                        idx = disc_col_map.get(col_name.lower())
                        raw_dict[col_name] = row_values[idx] if idx is not None and idx < len(row_values) else None

                    row_errors: List[str] = []
                    parsed_data: Dict[str, Any] = {}

                    # disclosure_id
                    d_id = str(raw_dict.get("disclosure_id") or '').strip()
                    if not d_id:
                        row_errors.append(f"[Required_Disclosures] Row {row_idx}, Column 'disclosure_id': Disclosure ID is required")
                    elif d_id in seen_disc_ids:
                        row_errors.append(f"[Required_Disclosures] Row {row_idx}, Column 'disclosure_id': Duplicate disclosure_id '{d_id}' within this import file")
                    else:
                        seen_disc_ids.add(d_id)
                    parsed_data["disclosure_id"] = d_id

                    # disclosure_text
                    d_text = str(raw_dict.get("disclosure_text") or '').strip()
                    if not d_text:
                        row_errors.append(f"[Required_Disclosures] Row {row_idx}, Column 'disclosure_text': Disclosure text is required")
                    parsed_data["disclosure_text"] = d_text

                    # applicable_product_id
                    app_prod = str(raw_dict.get("applicable_product_id") or '').strip()
                    if not app_prod:
                        row_errors.append(f"[Required_Disclosures] Row {row_idx}, Column 'applicable_product_id': Product reference is required (enter product_id or 'ALL')")
                    elif app_prod != "ALL" and app_prod not in known_product_ids:
                        row_errors.append(f"[Required_Disclosures] Row {row_idx}, Column 'applicable_product_id': Referenced product_id '{app_prod}' not found in active organisation catalogue")
                    parsed_data["applicable_product_id"] = app_prod

                    # applicable_market
                    market = str(raw_dict.get("applicable_market") or '').strip()
                    if not market:
                        row_errors.append(f"[Required_Disclosures] Row {row_idx}, Column 'applicable_market': Market is required")
                    parsed_data["applicable_market"] = market

                    # applies_when
                    app_when = str(raw_dict.get("applies_when") or '').strip()
                    if not app_when:
                        row_errors.append(f"[Required_Disclosures] Row {row_idx}, Column 'applies_when': Trigger condition is required")
                    parsed_data["applies_when"] = app_when

                    # effective_from
                    eff_from_val = raw_dict.get("effective_from")
                    parsed_eff_from = self._parse_date(eff_from_val)
                    if not parsed_eff_from:
                        row_errors.append(f"[Required_Disclosures] Row {row_idx}, Column 'effective_from': Must be a valid date (YYYY-MM-DD), got: '{eff_from_val}'")
                    parsed_data["effective_from"] = parsed_eff_from.isoformat() if parsed_eff_from else None

                    # effective_until
                    eff_until_val = raw_dict.get("effective_until")
                    parsed_eff_until = self._parse_date(eff_until_val) if eff_until_val else None
                    if eff_until_val and not parsed_eff_until:
                        row_errors.append(f"[Required_Disclosures] Row {row_idx}, Column 'effective_until': Must be a valid date (YYYY-MM-DD), got: '{eff_until_val}'")
                    elif parsed_eff_from and parsed_eff_until and parsed_eff_until < parsed_eff_from:
                        row_errors.append(f"[Required_Disclosures] Row {row_idx}, Column 'effective_until': effective_until ({parsed_eff_until}) cannot be earlier than effective_from ({parsed_eff_from})")
                    parsed_data["effective_until"] = parsed_eff_until.isoformat() if parsed_eff_until else None

                    is_valid = len(row_errors) == 0
                    if is_valid:
                        valid_rows += 1
                    else:
                        error_rows += 1

                    staged_disc = StagedImportDisclosureRow(
                        organization_id=org_id,
                        import_id=staged_import.id,
                        row_number=row_idx,
                        raw_data=raw_dict,
                        parsed_data=parsed_data,
                        validation_errors=row_errors,
                        is_valid=is_valid
                    )
                    db.add(staged_disc)

        staged_import.has_disclosures = has_disclosures
        staged_import.total_rows = total_rows
        staged_import.valid_rows = valid_rows
        staged_import.error_rows = error_rows
        staged_import.validation_summary = {
            "total_rows": total_rows,
            "valid_rows": valid_rows,
            "error_rows": error_rows,
            "has_disclosures": has_disclosures,
            "can_commit": error_rows == 0 and total_rows > 0
        }

    # -------------------------------------------------------------------------
    # 3. ATOMIC CONFIRMATION COMMIT (OPERATES ON EXACT VALIDATED PREVIEW)
    # -------------------------------------------------------------------------

    def confirm_staged_import(
        self,
        db: Session,
        org_id: str,
        import_id: str,
        user_id: Optional[str]
    ) -> Dict[str, Any]:
        staged_import = db.query(StagedImport).filter(
            StagedImport.organization_id == org_id,
            StagedImport.id == import_id
        ).first()

        if not staged_import:
            raise ValueError("Staged import session not found")

        if staged_import.status == "committed":
            return {
                "status": "already_committed",
                "import_id": staged_import.id,
                "message": "This import has already been committed."
            }

        if staged_import.status != "pending_preview":
            raise ValueError(f"Cannot commit import in status '{staged_import.status}'")

        if staged_import.error_rows > 0:
            raise ValueError(f"Cannot commit import with {staged_import.error_rows} validation errors. Fix errors and re-upload.")

        if staged_import.total_rows == 0:
            raise ValueError("Cannot commit an empty import.")

        # ATOMIC TRANSACTION COMMIT
        try:
            if staged_import.import_type == "product_catalogue":
                staged_products = db.query(StagedImportProductRow).filter(
                    StagedImportProductRow.organization_id == org_id,
                    StagedImportProductRow.import_id == import_id,
                    StagedImportProductRow.is_valid == True
                ).order_by(StagedImportProductRow.row_number).all()

                committed_count = 0
                for row in staged_products:
                    data = row.parsed_data
                    p_id = data["product_id"]

                    existing_prod = db.query(Product).filter(
                        Product.organization_id == org_id,
                        Product.product_id == p_id
                    ).first()

                    if existing_prod:
                        existing_prod.product_name = data["product_name"]
                        existing_prod.product_category = data["product_category"]
                        existing_prod.offering_type = data["offering_type"]
                        existing_prod.product_description = data["product_description"]
                        existing_prod.variant_name = data.get("variant_name")
                        existing_prod.sku = data.get("sku")
                        existing_prod.pack_size = data.get("pack_size")
                        existing_prod.pack_unit = data.get("pack_unit")
                        existing_prod.ingredients_components = data.get("ingredients_components")
                        existing_prod.key_features = data.get("key_features")
                        existing_prod.specifications = data.get("specifications")
                        existing_prod.known_limitations = data.get("known_limitations")
                        existing_prod.applicable_market = data["applicable_market"]
                        existing_prod.record_status = data["record_status"]
                        existing_prod.updated_at = datetime.utcnow()
                    else:
                        new_prod = Product(
                            organization_id=org_id,
                            product_id=p_id,
                            product_name=data["product_name"],
                            product_category=data["product_category"],
                            offering_type=data["offering_type"],
                            product_description=data["product_description"],
                            variant_name=data.get("variant_name"),
                            sku=data.get("sku"),
                            pack_size=data.get("pack_size"),
                            pack_unit=data.get("pack_unit"),
                            ingredients_components=data.get("ingredients_components"),
                            key_features=data.get("key_features"),
                            specifications=data.get("specifications"),
                            known_limitations=data.get("known_limitations"),
                            applicable_market=data["applicable_market"],
                            record_status=data["record_status"]
                        )
                        db.add(new_prod)
                    committed_count += 1

                staged_import.status = "committed"
                db.commit()
                return {
                    "status": "success",
                    "import_id": import_id,
                    "import_type": "product_catalogue",
                    "committed_products": committed_count
                }

            elif staged_import.import_type == "claims_and_disclosures":
                staged_claims = db.query(StagedImportClaimRow).filter(
                    StagedImportClaimRow.organization_id == org_id,
                    StagedImportClaimRow.import_id == import_id,
                    StagedImportClaimRow.is_valid == True
                ).order_by(StagedImportClaimRow.row_number).all()

                committed_claims = 0
                for row in staged_claims:
                    data = row.parsed_data
                    c_id = data["claim_id"]
                    app_prod = data["applicable_product_id"]

                    internal_prod_id = None
                    if app_prod != "ALL":
                        prod_match = db.query(Product).filter(
                            Product.organization_id == org_id,
                            Product.product_id == app_prod
                        ).first()
                        if not prod_match:
                            raise ValueError(f"Integrity violation: referenced product '{app_prod}' no longer exists.")
                        internal_prod_id = prod_match.id

                    eff_from = datetime.strptime(data["effective_from"], "%Y-%m-%d").date()
                    eff_until = datetime.strptime(data["effective_until"], "%Y-%m-%d").date() if data.get("effective_until") else None

                    existing_claim = db.query(Claim).filter(
                        Claim.organization_id == org_id,
                        Claim.claim_id == c_id
                    ).first()

                    if existing_claim:
                        existing_claim.claim_text = data["claim_text"]
                        existing_claim.claim_type = data["claim_type"]
                        existing_claim.claim_status = data["claim_status"]
                        existing_claim.applicable_product_id = app_prod
                        existing_claim.product_id = internal_prod_id
                        existing_claim.approved_variations = data.get("approved_variations")
                        existing_claim.restricted_conditions = data.get("restricted_conditions")
                        existing_claim.prohibited_variations = data.get("prohibited_variations")
                        existing_claim.applicable_market = data["applicable_market"]
                        existing_claim.effective_from = eff_from
                        existing_claim.effective_until = eff_until
                    else:
                        new_claim = Claim(
                            organization_id=org_id,
                            claim_id=c_id,
                            claim_text=data["claim_text"],
                            claim_type=data["claim_type"],
                            claim_status=data["claim_status"],
                            applicable_product_id=app_prod,
                            product_id=internal_prod_id,
                            approved_variations=data.get("approved_variations"),
                            restricted_conditions=data.get("restricted_conditions"),
                            prohibited_variations=data.get("prohibited_variations"),
                            applicable_market=data["applicable_market"],
                            effective_from=eff_from,
                            effective_until=eff_until
                        )
                        db.add(new_claim)
                    committed_claims += 1

                committed_disclosures = 0
                if staged_import.has_disclosures:
                    staged_disclosures = db.query(StagedImportDisclosureRow).filter(
                        StagedImportDisclosureRow.organization_id == org_id,
                        StagedImportDisclosureRow.import_id == import_id,
                        StagedImportDisclosureRow.is_valid == True
                    ).order_by(StagedImportDisclosureRow.row_number).all()

                    for row in staged_disclosures:
                        data = row.parsed_data
                        d_id = data["disclosure_id"]
                        app_prod = data["applicable_product_id"]

                        internal_prod_id = None
                        if app_prod != "ALL":
                            prod_match = db.query(Product).filter(
                                Product.organization_id == org_id,
                                Product.product_id == app_prod
                            ).first()
                            if not prod_match:
                                raise ValueError(f"Integrity violation: disclosure product '{app_prod}' no longer exists.")
                            internal_prod_id = prod_match.id

                        existing_disc = db.query(RequiredDisclosure).filter(
                            RequiredDisclosure.organization_id == org_id,
                            RequiredDisclosure.disclosure_id == d_id
                        ).first()

                        eff_from = datetime.strptime(data["effective_from"], "%Y-%m-%d").date()
                        eff_until = datetime.strptime(data["effective_until"], "%Y-%m-%d").date() if data.get("effective_until") else None

                        if existing_disc:
                            existing_disc.disclosure_text = data["disclosure_text"]
                            existing_disc.applicable_product_id = app_prod
                            existing_disc.product_id = internal_prod_id
                            existing_disc.applicable_market = data["applicable_market"]
                            existing_disc.applies_when = data["applies_when"]
                            existing_disc.effective_from = eff_from
                            existing_disc.effective_until = eff_until
                        else:
                            new_disc = RequiredDisclosure(
                                organization_id=org_id,
                                disclosure_id=d_id,
                                disclosure_text=data["disclosure_text"],
                                applicable_product_id=app_prod,
                                product_id=internal_prod_id,
                                applicable_market=data["applicable_market"],
                                applies_when=data["applies_when"],
                                effective_from=eff_from,
                                effective_until=eff_until
                            )
                            db.add(new_disc)
                        committed_disclosures += 1

                staged_import.status = "committed"
                db.commit()
                return {
                    "status": "success",
                    "import_id": import_id,
                    "import_type": "claims_and_disclosures",
                    "committed_claims": committed_claims,
                    "committed_disclosures": committed_disclosures
                }

        except Exception as e:
            db.rollback()
            staged_import.status = "failed"
            staged_import.validation_summary = {
                **staged_import.validation_summary,
                "commit_error": str(e)
            }
            db.commit()
            raise RuntimeError(f"Atomic commit failed and rolled back cleanly: {str(e)}")

    def discard_staged_import(self, db: Session, org_id: str, import_id: str):
        staged_import = db.query(StagedImport).filter(
            StagedImport.organization_id == org_id,
            StagedImport.id == import_id
        ).first()
        if staged_import:
            staged_import.status = "discarded"
            db.commit()

    def _parse_date(self, val: Any) -> Optional[date]:
        if val is None:
            return None
        if isinstance(val, datetime):
            return val.date()
        if isinstance(val, date):
            return val
        s = str(val).strip()
        if not s:
            return None
        for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%Y/%m/%d"):
            try:
                return datetime.strptime(s, fmt).date()
            except ValueError:
                pass
        return None


excel_service = ExcelImportService()
