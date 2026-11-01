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
# AUTHORITATIVE SCHEMA DEFINITIONS
# -----------------------------------------------------------------------------

PRODUCT_CATALOGUE_COLUMNS = [
    ("product_id", "Unique identifier for the product or service offering", True),
    ("product_name", "Official product or service name", True),
    ("product_category", "Category of the offering", True),
    ("offering_type", "Physical Product, Service, or Digital Product", True),
    ("product_description", "Official descriptive information", True),
    ("variant_name", "Variant, edition, plan, or model name", False),
    ("sku", "Stock keeping unit or internal offering code", False),
    ("pack_size", "Numeric quantity or capacity, where relevant", False),
    ("pack_unit", "Unit such as ml, g, kg, L, hours, or seats", False),
    ("ingredients_components", "Ingredients or core components, where relevant", False),
    ("key_features", "Company-provided factual features", False),
    ("specifications", "Product specifications or service details", False),
    ("known_limitations", "Relevant limitations or restrictions", False),
    ("applicable_market", "Country or region in which the record applies", True),
    ("record_status", "Active, Inactive, or Discontinued", True),
]

CLAIMS_REGISTER_COLUMNS = [
    ("claim_id", "Unique claim identifier", True),
    ("claim_text", "Official claim wording", True),
    ("claim_type", "Ingredient, Nutritional, Health, Performance, Quality, Comparative, Environmental, Endorsement, Origin, Safety, Other", True),
    ("claim_status", "Approved, Restricted, or Prohibited", True),
    ("applicable_product_id", "Product ID to which the claim applies, or ALL", True),
    ("approved_variations", "Alternative wording explicitly authorised by the company", False),
    ("restricted_conditions", "Conditions that must be satisfied for a Restricted claim", False),
    ("prohibited_variations", "Known wording variants that the organisation explicitly disallows", False),
    ("applicable_market", "Country or region in which the claim authorisation applies", True),
    ("effective_from", "Date from which the record is effective (YYYY-MM-DD)", True),
    ("effective_until", "Expiry date (YYYY-MM-DD); blank means no scheduled expiry", False),
]

REQUIRED_DISCLOSURES_COLUMNS = [
    ("disclosure_id", "Unique disclosure identifier", True),
    ("disclosure_text", "Exact required disclosure wording", True),
    ("applicable_product_id", "Product ID or ALL", True),
    ("applicable_market", "Country or region", True),
    ("applies_when", "Condition that triggers the disclosure", True),
    ("effective_from", "Date from which the disclosure is effective (YYYY-MM-DD)", True),
    ("effective_until", "Expiry date (YYYY-MM-DD); blank means no scheduled expiry", False),
]

VALID_OFFERING_TYPES = {"Physical Product", "Service", "Digital Product"}
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
    Service for generating authoritative Excel templates, staging imports safely
    without mutating active records, validating rows, and atomically committing.
    """

    # -------------------------------------------------------------------------
    # 1. TEMPLATE GENERATION
    # -------------------------------------------------------------------------

    def generate_template(self, template_type: str) -> bytes:
        """
        Generates an authoritative, beautifully formatted Excel workbook (.xlsx)
        with header styling, column widths, and sample demonstration rows.
        """
        wb = openpyxl.Workbook()
        # Remove default sheet
        wb.remove(wb.active)

        header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
        header_fill = PatternFill(start_color="186B42", end_color="186B42", fill_type="solid")
        sample_font = Font(name="Calibri", size=10, italic=True, color="555555")
        thin_border = Border(
            left=Side(style='thin', color='DDDDDD'),
            right=Side(style='thin', color='DDDDDD'),
            top=Side(style='thin', color='DDDDDD'),
            bottom=Side(style='thin', color='DDDDDD')
        )

        if template_type == "product_catalogue":
            ws = wb.create_sheet(title="Product_Catalogue")
            # Headers
            headers = [col[0] for col in PRODUCT_CATALOGUE_COLUMNS]
            ws.append(headers)

            for col_num, col_name in enumerate(headers, 1):
                cell = ws.cell(row=1, column=col_num)
                cell.font = header_font
                cell.fill = header_fill
                cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

            # Sample demonstration rows
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

            # Auto-fit columns
            for col in ws.columns:
                max_len = max(len(str(cell.value or '')) for cell in col)
                col_letter = get_column_letter(col[0].column)
                ws.column_dimensions[col_letter].width = max(max_len + 4, 15)

        elif template_type == "claims_and_disclosures":
            # Sheet 1: Claims_Register
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

            # Sheet 2: Required_Disclosures (Optional Sheet)
            ws_disc = wb.create_sheet(title="Required_Disclosures")
            disc_headers = [col[0] for col in REQUIRED_DISCLOSURES_COLUMNS]
            ws_disc.append(disc_headers)
            disc_fill = PatternFill(start_color="282828", end_color="282828", fill_type="solid")
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
        """
        Parses an uploaded Excel file, validates headers, checks column constraints,
        and saves staged row models. Active tables are NOT modified.
        Idempotency key prevents duplicate submission within the same organization.
        """
        file_hash = hashlib.sha256(file_bytes).hexdigest()

        # Idempotency check: Return existing staged import if matching key exists
        existing_import = db.query(StagedImport).filter(
            StagedImport.organization_id == org_id,
            StagedImport.idempotency_key == idempotency_key
        ).first()

        if existing_import:
            # If already committed, return it
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

        # Check required columns presence
        missing_headers = [c for c in expected_cols if c.lower() not in col_index_map]
        if missing_headers:
            staged_import.status = "failed"
            staged_import.validation_summary = {
                "file_error": f"Missing required columns in header: {', '.join(missing_headers)}"
            }
            return

        seen_product_ids = set()
        total_rows = 0
        valid_rows = 0
        error_rows = 0

        for row_idx, row_values in enumerate(rows[1:], start=2):
            # Skip empty rows
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
                row_errors.append("Column 'product_id' is required and cannot be empty")
            elif p_id in seen_product_ids:
                row_errors.append(f"Duplicate product_id '{p_id}' within this import file")
            else:
                seen_product_ids.add(p_id)
            parsed_data["product_id"] = p_id

            # 2. product_name
            p_name = str(raw_dict.get("product_name") or '').strip()
            if not p_name:
                row_errors.append("Column 'product_name' is required")
            parsed_data["product_name"] = p_name

            # 3. product_category
            p_cat = str(raw_dict.get("product_category") or '').strip()
            if not p_cat:
                row_errors.append("Column 'product_category' is required")
            parsed_data["product_category"] = p_cat

            # 4. offering_type
            off_type_raw = str(raw_dict.get("offering_type") or '').strip()
            off_type = next((v for v in VALID_OFFERING_TYPES if v.lower() == off_type_raw.lower()), off_type_raw)
            if off_type not in VALID_OFFERING_TYPES:
                row_errors.append(f"Invalid offering_type '{off_type_raw}'. Permitted: {', '.join(VALID_OFFERING_TYPES)}")
            parsed_data["offering_type"] = off_type

            # 5. product_description
            p_desc = str(raw_dict.get("product_description") or '').strip()
            if not p_desc:
                row_errors.append("Column 'product_description' is required")
            parsed_data["product_description"] = p_desc

            # 6. variant_name, sku
            parsed_data["variant_name"] = str(raw_dict.get("variant_name") or '').strip() or None
            parsed_data["sku"] = str(raw_dict.get("sku") or '').strip() or None

            # 7. pack_size, pack_unit
            pack_size_val = raw_dict.get("pack_size")
            if pack_size_val is not None and str(pack_size_val).strip() != '':
                try:
                    parsed_data["pack_size"] = float(pack_size_val)
                except ValueError:
                    row_errors.append(f"Invalid numeric pack_size: '{pack_size_val}'")
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
                row_errors.append("Column 'applicable_market' is required")
            parsed_data["applicable_market"] = market

            # 9. record_status
            status_val_raw = str(raw_dict.get("record_status") or 'Active').strip()
            status_val = next((v for v in VALID_PRODUCT_RECORD_STATUSES if v.lower() == status_val_raw.lower()), status_val_raw)
            if status_val not in VALID_PRODUCT_RECORD_STATUSES:
                row_errors.append(f"Invalid record_status '{status_val_raw}'. Permitted: {', '.join(VALID_PRODUCT_RECORD_STATUSES)}")
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
                row_errors.append("Column 'claim_id' is required")
            elif c_id in seen_claim_ids:
                row_errors.append(f"Duplicate claim_id '{c_id}' within this import file")
            else:
                seen_claim_ids.add(c_id)
            parsed_data["claim_id"] = c_id

            # claim_text
            c_text = str(raw_dict.get("claim_text") or '').strip()
            if not c_text:
                row_errors.append("Column 'claim_text' is required")
            parsed_data["claim_text"] = c_text

            # claim_type
            c_type = str(raw_dict.get("claim_type") or '').strip()
            # Title case comparison for safety
            normalized_type = c_type.capitalize()
            if normalized_type not in VALID_CLAIM_TYPES:
                row_errors.append(f"Invalid claim_type '{c_type}'. Permitted: {', '.join(sorted(VALID_CLAIM_TYPES))}")
            parsed_data["claim_type"] = normalized_type

            # claim_status
            c_status = str(raw_dict.get("claim_status") or '').strip().capitalize()
            if c_status not in VALID_CLAIM_STATUSES:
                row_errors.append(f"Invalid claim_status '{c_status}'. Permitted: {', '.join(VALID_CLAIM_STATUSES)}")
            parsed_data["claim_status"] = c_status

            # applicable_product_id
            app_prod = str(raw_dict.get("applicable_product_id") or '').strip()
            if not app_prod:
                row_errors.append("Column 'applicable_product_id' is required (enter product_id or 'ALL')")
            elif app_prod != "ALL" and app_prod not in known_product_ids:
                row_errors.append(f"Referenced product_id '{app_prod}' not found in active organisation catalogue")
            parsed_data["applicable_product_id"] = app_prod

            # restricted_conditions
            restr_cond = str(raw_dict.get("restricted_conditions") or '').strip()
            if c_status == "Restricted" and not restr_cond:
                row_errors.append("Restricted claims must specify 'restricted_conditions'")
            parsed_data["restricted_conditions"] = restr_cond or None

            parsed_data["approved_variations"] = str(raw_dict.get("approved_variations") or '').strip() or None
            parsed_data["prohibited_variations"] = str(raw_dict.get("prohibited_variations") or '').strip() or None

            # applicable_market
            market = str(raw_dict.get("applicable_market") or '').strip()
            if not market:
                row_errors.append("Column 'applicable_market' is required")
            parsed_data["applicable_market"] = market

            # effective_from
            eff_from_val = raw_dict.get("effective_from")
            parsed_eff_from = self._parse_date(eff_from_val)
            if not parsed_eff_from:
                row_errors.append(f"Column 'effective_from' must be a valid date (YYYY-MM-DD), got: '{eff_from_val}'")
            parsed_data["effective_from"] = parsed_eff_from.isoformat() if parsed_eff_from else None

            # effective_until
            eff_until_val = raw_dict.get("effective_until")
            parsed_eff_until = self._parse_date(eff_until_val) if eff_until_val else None
            if eff_until_val and not parsed_eff_until:
                row_errors.append(f"Column 'effective_until' must be a valid date (YYYY-MM-DD), got: '{eff_until_val}'")
            elif parsed_eff_from and parsed_eff_until and parsed_eff_until < parsed_eff_from:
                row_errors.append(f"effective_until ({parsed_eff_until}) cannot be earlier than effective_from ({parsed_eff_from})")
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
                        row_errors.append("Column 'disclosure_id' is required")
                    elif d_id in seen_disc_ids:
                        row_errors.append(f"Duplicate disclosure_id '{d_id}'")
                    else:
                        seen_disc_ids.add(d_id)
                    parsed_data["disclosure_id"] = d_id

                    # disclosure_text
                    d_text = str(raw_dict.get("disclosure_text") or '').strip()
                    if not d_text:
                        row_errors.append("Column 'disclosure_text' is required")
                    parsed_data["disclosure_text"] = d_text

                    # applicable_product_id
                    app_prod = str(raw_dict.get("applicable_product_id") or '').strip()
                    if not app_prod:
                        row_errors.append("Column 'applicable_product_id' is required (enter product_id or 'ALL')")
                    elif app_prod != "ALL" and app_prod not in known_product_ids:
                        row_errors.append(f"Referenced product_id '{app_prod}' not found in active organisation catalogue")
                    parsed_data["applicable_product_id"] = app_prod

                    # applicable_market
                    market = str(raw_dict.get("applicable_market") or '').strip()
                    if not market:
                        row_errors.append("Column 'applicable_market' is required")
                    parsed_data["applicable_market"] = market

                    # applies_when
                    app_when = str(raw_dict.get("applies_when") or '').strip()
                    if not app_when:
                        row_errors.append("Column 'applies_when' is required")
                    parsed_data["applies_when"] = app_when

                    # effective_from
                    eff_from_val = raw_dict.get("effective_from")
                    parsed_eff_from = self._parse_date(eff_from_val)
                    if not parsed_eff_from:
                        row_errors.append(f"Column 'effective_from' must be a valid date (YYYY-MM-DD), got: '{eff_from_val}'")
                    parsed_data["effective_from"] = parsed_eff_from.isoformat() if parsed_eff_from else None

                    # effective_until
                    eff_until_val = raw_dict.get("effective_until")
                    parsed_eff_until = self._parse_date(eff_until_val) if eff_until_val else None
                    if eff_until_val and not parsed_eff_until:
                        row_errors.append(f"Column 'effective_until' must be a valid date (YYYY-MM-DD), got: '{eff_until_val}'")
                    elif parsed_eff_from and parsed_eff_until and parsed_eff_until < parsed_eff_from:
                        row_errors.append(f"effective_until ({parsed_eff_until}) cannot be earlier than effective_from ({parsed_eff_from})")
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
        """
        Commits an exact validated staged import atomically within a database transaction.
        If any row fails or if validation errors exist, the entire transaction is rolled back,
        leaving the existing active dataset unchanged.
        """
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
                # Staged Claims
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

                    # Resolve internal product UUID if not 'ALL'
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

                # Staged Disclosures (Committed ATOMICALLY with Claims)
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
        """Marks a staged import as discarded."""
        staged_import = db.query(StagedImport).filter(
            StagedImport.organization_id == org_id,
            StagedImport.id == import_id
        ).first()
        if staged_import:
            staged_import.status = "discarded"
            db.commit()

    def _parse_date(self, val: Any) -> Optional[date]:
        """Safely parses dates from Excel (datetime objects, date objects, or YYYY-MM-DD strings)."""
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
