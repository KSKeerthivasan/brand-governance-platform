# Inkloom AI — Organisation Input Specification

**Document purpose:** Define the minimum information an organisation must provide to configure Inkloom AI for brand-governance reviews of advertisements.

**Scope:** Organisation onboarding and knowledge-base setup only. This document specifies the four agreed input categories, their collection methods, exact fields, sample values, upload requirements, validation rules, and how the information is used during advertisement review.

**Status:** Finalised MVP specification

---

## 1. Objective and design principles

Inkloom AI is an organisation-controlled brand-governance platform. It reviews advertisements submitted by an organisation's employees, agencies, or authorised content creators against the organisation's approved brand information.

The organisation should provide only the information that Inkloom needs to evaluate its advertisements. Onboarding should not become a full business-information collection exercise.

The system will use **four organisation input categories**:

1. Brand Guidelines
2. Product / Service Information
3. Approved / Restricted Claims
4. Approved Brand Assets

### 1.1 Agreed collection methods

| Organisation input | Collection method | Onboarding requirement |
|---|---|---|
| Brand Guidelines | Structured website form | Required |
| Product / Service Information | Excel workbook (`.xlsx`) | Required for the products/services being reviewed |
| Approved / Restricted Claims | Excel workbook (`.xlsx`) | Required for claim-governance checks |
| Approved Brand Assets | Centralised asset library with file uploads | At least one primary logo is required; other assets are conditional on the checks the organisation wants to perform |

### 1.2 Core principles

- **Structured information over unstructured documents:** Store brand rules and registers in machine-readable fields wherever practical.
- **Bulk entry where appropriate:** Use Excel for product catalogues and claim registers so organisations can manage many records efficiently.
- **Company-controlled knowledge:** The organisation supplies and maintains its own approved brand information.
- **No unnecessary evidence burden:** Inkloom does not require an organisation to upload laboratory reports, FSSAI certificates, or other external certificates for every claim merely to register that claim in its internal governance register.
- **Approval before activation:** Imported or edited information must be reviewed and confirmed by an authorised organisation representative before it becomes active.
- **Versioning:** Changes to products, claims, guidelines, and assets must be traceable so a review can be associated with the knowledge-base version used at that time.
- **Unknown is not the same as prohibited:** Missing reference information should be reported as unavailable or requiring review, not automatically treated as a violation.

---

# 2. Input 1 — Brand Guidelines

**Collection method:** Structured website form
**Primary record:** One Brand Profile per brand
**Who completes it:** Organisation Knowledge Manager or authorised brand representative

## 2.1 Why a structured form is used

The organisation's existing brand manual may be a PDF or presentation, but Inkloom needs consistent, machine-readable values for items such as approved colours, fonts, tone, terminology, and visual preferences.

For the MVP, the structured form is the source of truth. Do not make a PDF upload mandatory. If the organisation has an existing brand manual, it may use it as an internal reference while completing the form, but the required fields must be entered into the form.

An organisation with multiple brands should create a separate Brand Profile for each brand.

## 2.2 Section A — Brand identity

| Field | Input type | Required | Sample value | Notes |
|---|---|---:|---|---|
| `brand_name` | Text input | Yes | Freshsip | Official public-facing brand name. |
| `brand_description` | Textarea | Yes | A fruit beverage brand focused on refreshing fruit drinks. | Brief description of what the brand offers. |
| `approved_taglines` | Repeatable text input | No | Drink Fresh. Live Bold. | Add each approved tagline separately. |

## 2.3 Section B — Brand voice and communication

| Field | Input type | Required | Sample value | Notes |
|---|---|---:|---|---|
| `brand_personality` | Multi-select with custom values | Yes | Friendly; Energetic; Trustworthy | How the brand should be perceived. |
| `preferred_tone` | Multi-select with custom values | Yes | Positive; Conversational; Enthusiastic | Tone expected in advertising copy. |
| `tones_to_avoid` | Multi-select with custom values | No | Aggressive; Arrogant; Fear-inducing | Tones the brand does not want. |
| `preferred_terminology` | Repeatable text input | No | Fresh; Refreshing; Fruit-based | Each term can optionally have a usage context. |
| `prohibited_terminology` | Repeatable text input | No | Miracle drink; Guaranteed cure | Terms the brand does not permit. |
| `writing_style` | Dropdown with custom value | Yes | Simple and conversational | Example choices: concise, formal, conversational, technical, playful. |
| `approved_languages` | Multi-select | Yes | English; Tamil | Languages in which the brand permits advertising content. |

### Terminology examples

| Type | Term | Optional context |
|---|---|---|
| Preferred | Fruit beverage | Product description |
| Preferred | Refreshing | Promotional messaging |
| Preferred | Freshsip | Brand name; preserve exact spelling |
| Prohibited | Miracle drink | Misleading promotional expression |
| Prohibited | Guaranteed cure | Unapproved medical implication |

The form should allow users to add multiple terms rather than storing all terms in one long text field.

## 2.4 Section C — Brand colour palette

The colour editor must support multiple colours. A single colour field is insufficient for a brand palette.

### Fields for each colour entry

| Field | Input type | Required per colour | Sample value | Notes |
|---|---|---:|---|---|
| `colour_name` | Text input | Yes | Forest Green | Organisation-defined colour name. |
| `colour_family` | Dropdown | Yes | Green | Example families: Red, Orange, Yellow, Green, Blue, Purple, Pink, Brown, Black, White, Grey, Neutral, Other. |
| `colour_value` | Colour picker | Yes | Selected visually | User can select from a colour picker. |
| `hex_value` | Text input / auto-generated | Yes | `#186B42` | HEX value. Validate format. |
| `rgb_value` | Auto-generated from colour selection | Yes | `24, 107, 66` | Store as three integer channels from 0–255. |
| `colour_role` | Dropdown | Yes | Primary | Values: Primary, Secondary, Accent, Background, Text, Neutral. |

### Sample palette

| Colour name | Family | Role | HEX | RGB |
|---|---|---|---|---|
| Forest Green | Green | Primary | `#186B42` | 24, 107, 66 |
| Mango Yellow | Yellow | Secondary | `#FFC928` | 255, 201, 40 |
| White | White / Neutral | Background | `#FFFFFF` | 255, 255, 255 |
| Charcoal | Black / Neutral | Text | `#282828` | 40, 40, 40 |
| Light Green | Green | Accent | `#A8D5B5` | 168, 213, 181 |

### Colour-picker behaviour

- Allow the Knowledge Manager to add multiple colour entries.
- Allow colour selection using a visual colour picker.
- Allow direct HEX entry; RGB should be calculated automatically.
- Allow direct RGB entry; HEX should be calculated automatically.
- Allow filtering or browsing by colour family.
- Require a role for each saved colour.
- Allow entries to be edited or removed.
- Do not interpret selection of a broad colour family (for example, Green) as approval to use every possible shade of that family. Store exact approved colour values.

## 2.5 Section D — Typography

| Field | Input type | Required | Sample value | Notes |
|---|---|---:|---|---|
| `primary_heading_font` | Text input | Yes | Montserrat | Main heading font. |
| `secondary_body_font` | Text input | Yes | Open Sans | Body text font. |
| `additional_approved_fonts` | Repeatable text input | No | Lato | Any further approved font families. |
| `typography_instructions` | Textarea | No | Use bold heading styles and regular body text. | Optional usage guidance. |

The font names are brand preferences. Actual font-file upload is not part of the minimum required onboarding unless a future feature needs font matching against files.

## 2.6 Section E — Visual identity rules

| Field | Input type | Required | Sample value | Notes |
|---|---|---:|---|---|
| `visual_style` | Multi-select with custom values | Yes | Minimalist; Fresh; Modern | Overall look and feel. |
| `preferred_imagery_style` | Multi-select with custom values | Yes | Natural lighting; Real product photography | Preferred image treatment. |
| `preferred_backgrounds` | Multi-select with custom values | No | Clean; Light; Nature-inspired | Optional background preferences. |
| `visual_styles_to_avoid` | Multi-select with custom values | No | Cluttered layouts; Excessive effects | Visual treatments the brand wants to avoid. |
| `logo_usage_instructions` | Textarea | No | Do not stretch, rotate or recolour the official logo. | Additional logo-use guidance. |

## 2.7 Brand Guidelines form — completion requirements

The following are the minimum fields required before the Brand Profile can be activated:

- Brand name and description.
- At least one brand personality value.
- At least one preferred tone.
- Writing style.
- At least one approved language.
- At least one primary brand colour with an exact HEX/RGB value.
- Primary heading font and secondary body font.
- At least one visual style.
- At least one preferred imagery style.

The following may be completed later:

- Taglines.
- Tones to avoid.
- Preferred and prohibited terminology.
- Additional colours.
- Additional fonts.
- Background preferences.
- Visual styles to avoid.
- Additional logo instructions.

The system should distinguish a missing optional value from a rule violation. For example, if no prohibited terminology has been configured, Inkloom must not invent a prohibited-terms list.

---

# 3. Input 2 — Product / Service Information

**Collection method:** Excel workbook (`.xlsx`)
**Worksheet:** `Product_Catalogue`
**Who prepares it:** Organisation Knowledge Manager or product-information owner

## 3.1 Workbook structure

Use one row for each product variant or service offering.

For example, if Sunrise Mango is sold in 250 ml and 500 ml variants, create two rows with different product/variant identifiers. This allows Inkloom to check an advertisement against the exact variant being promoted.

For services or digital products, physical-product fields such as pack size and ingredients can be left blank where they do not apply.

## 3.2 Exact column specification

| Column name | Description | Required? | Sample value |
|---|---|---:|---|
| `product_id` | Unique identifier for the product or service offering | Yes | FS-P001 |
| `product_name` | Official product or service name | Yes | Sunrise Mango |
| `product_category` | Category of the offering | Yes | Fruit Beverage |
| `offering_type` | Physical Product, Service, or Digital Product | Yes | Physical Product |
| `product_description` | Official descriptive information | Yes | Mango-flavoured fruit drink |
| `variant_name` | Variant, edition, plan, or model name | No | Original |
| `sku` | Stock keeping unit or internal offering code | No | SM-250 |
| `pack_size` | Numeric quantity or capacity, where relevant | Conditional | 250 |
| `pack_unit` | Unit such as ml, g, kg, L, hours, or seats | Conditional | ml |
| `ingredients_components` | Ingredients or core components, where relevant | Conditional | Water; Mango pulp; Sugar |
| `key_features` | Company-provided factual features | No | Mango pulp; Ready to drink |
| `specifications` | Product specifications or service details | No | 250 ml bottle |
| `known_limitations` | Relevant limitations or restrictions | No | Store as instructed on packaging |
| `applicable_market` | Country or region in which the record applies | Yes | India |
| `record_status` | Active, Inactive, or Discontinued | Yes | Active |

### Conditional-field guidance

- `pack_size` and `pack_unit` are applicable to offerings with a measurable quantity or capacity.
- `ingredients_components` is applicable to products for which ingredients or components matter. It may not apply to every service or digital product.
- `known_limitations` should be supplied where the organisation has limitations that affect how the product/service may be represented.
- The system should not reject a service record simply because physical-product fields are blank.

## 3.3 Sample row — Freshsip Sunrise Mango

| Column | Sample value |
|---|---|
| `product_id` | FS-P001 |
| `product_name` | Sunrise Mango |
| `product_category` | Fruit Beverage |
| `offering_type` | Physical Product |
| `product_description` | Mango-flavoured fruit drink |
| `variant_name` | Original |
| `sku` | SM-250 |
| `pack_size` | 250 |
| `pack_unit` | ml |
| `ingredients_components` | Water; Mango pulp; Sugar |
| `key_features` | Mango pulp; Ready to drink |
| `specifications` | 250 ml bottle |
| `known_limitations` | Store as instructed on packaging |
| `applicable_market` | India |
| `record_status` | Active |

**All sample values are fictional demonstration data. They do not represent a real Freshsip product.**

## 3.4 Example CSV header

The Excel template should use these exact column names in the `Product_Catalogue` worksheet:

```csv
product_id,product_name,product_category,offering_type,product_description,variant_name,sku,pack_size,pack_unit,ingredients_components,key_features,specifications,known_limitations,applicable_market,record_status
```

## 3.5 Product workbook validation

On upload, Inkloom should:

1. Check that the required columns exist.
2. Check that required cells are populated.
3. Validate `offering_type` against the permitted values.
4. Validate `record_status` against Active, Inactive, and Discontinued.
5. Check that `product_id` values are unique within the organisation's applicable product catalogue.
6. Identify duplicate or conflicting product/variant entries.
7. Validate numeric values such as `pack_size` where populated.
8. Check that conditional fields are appropriate for the selected offering type.
9. Display a row-by-row preview and validation errors before import.
10. Ask an authorised Knowledge Manager to confirm the import.

## 3.6 Separation from claims

The product catalogue should contain company-maintained product/service facts and specifications. Do not use it as the place to register promotional authorisations.

For example:

- `ingredients_components`: Mango pulp — factual product information supplied by the organisation.
- Claims Register: Made with real mango pulp — the organisation's approved advertising claim wording.

Keeping these separate avoids having two competing sources for advertising authorisation.

---

# 4. Input 3 — Approved / Restricted Claims

**Collection method:** Excel workbook (`.xlsx`)
**Worksheet:** `Claims_Register`
**Who prepares it:** Organisation Knowledge Manager or authorised claims owner

## 4.1 Purpose and operating boundary

The organisation supplies the claims that it has authorised, restricted, or prohibited for use in its advertisements.

Inkloom uses this register as the organisation's internal advertising-authorisation reference. Its primary responsibility is to determine whether wording in an advertisement matches a company-authorised claim and whether the claim is being used within its configured product, market, condition, and validity scope.

For this internal governance workflow:

- Organisations are not required to attach an FSSAI certificate, laboratory report, clinical report, or external research document to every claim simply to register it.
- An evidence/reference attachment may be supported as an optional future or supplementary field, but it is not a mandatory onboarding requirement for claim matching.
- Company approval in the register is not independent proof that a claim is objectively true or legally substantiated.
- Inkloom must not state that a claim is false merely because it is absent from the register. It should say that the claim is not registered as approved and requires authorised review.
- Applicable advertising laws may separately require the advertiser to possess substantiation. This product workflow does not replace that responsibility or constitute independent legal certification.

## 4.2 Exact column specification

| Column name | Description | Required? | Sample value |
|---|---|---:|---|
| `claim_id` | Unique claim identifier | Yes | CLM001 |
| `claim_text` | Official claim wording | Yes | Made with real mango pulp |
| `claim_type` | Type of promotional claim | Yes | Ingredient |
| `claim_status` | Approved, Restricted, or Prohibited | Yes | Approved |
| `applicable_product_id` | Product ID to which the claim applies, or `ALL` | Yes | FS-P001 |
| `approved_variations` | Alternative wording explicitly authorised by the company | No | Contains real mango pulp |
| `restricted_conditions` | Conditions that must be satisfied for a Restricted claim | Conditional | Only Sunrise Mango |
| `prohibited_variations` | Known wording variants that the organisation explicitly disallows | No | Made with 100% mango |
| `applicable_market` | Country or region in which the claim authorisation applies | Yes | India |
| `effective_from` | Date from which the record is effective | Yes | 2026-01-01 |
| `effective_until` | Expiry date; blank means no scheduled expiry | No | 2026-12-31 |

### Permitted `claim_type` values

- Ingredient
- Nutritional
- Health
- Performance
- Quality
- Comparative
- Environmental
- Endorsement
- Origin
- Safety
- Other

The workbook should use a controlled dropdown/list for these values where possible.

### Permitted `claim_status` values

- **Approved:** The company authorises the claim within the record's scope.
- **Restricted:** The company permits the claim only when the specified conditions are satisfied.
- **Prohibited:** The company does not permit the claim within the specified scope.

## 4.3 Sample Claims Register — Freshsip

| claim_id | claim_text | claim_type | claim_status | applicable_product_id | approved_variations | restricted_conditions | prohibited_variations | applicable_market | effective_from | effective_until |
|---|---|---|---|---|---|---|---|---|---|---|
| CLM001 | Made with real mango pulp | Ingredient | Approved | FS-P001 | Contains real mango pulp | | Made with 100% mango | India | 2026-01-01 | |
| CLM002 | No Added Sugar | Nutritional | Restricted | FS-P001 | | Only for the specified approved formulation | Sugar Free | India | 2026-01-01 | 2026-12-31 |
| CLM003 | Refreshing mango drink | Quality | Approved | FS-P001 | A refreshing mango beverage | | | India | 2026-01-01 | |
| CLM004 | Cures digestive problems | Health | Prohibited | ALL | | | Treats digestive disorders | India | 2026-01-01 | |

**All sample records are fictional demonstration data. They do not represent real product approvals or legal determinations.**

## 4.4 Example CSV header

```csv
claim_id,claim_text,claim_type,claim_status,applicable_product_id,approved_variations,restricted_conditions,prohibited_variations,applicable_market,effective_from,effective_until
```

## 4.5 How Inkloom should evaluate claim status

| Register status / match | Expected governance behaviour |
|---|---|
| Approved claim matches the advertisement and is within scope | Treat as company-authorised. |
| Approved alternative wording matches | Treat as company-authorised, provided the variation is explicitly listed and is within scope. |
| Restricted claim appears and all configured conditions are satisfied | Treat as permitted under the recorded conditions; retain the conditions in the review result. |
| Restricted claim appears but conditions are not met or cannot be determined | Flag for review; explain which condition is missing or unresolved. |
| Prohibited claim appears | Flag as a company-policy violation. |
| Claim is not present in the register | Flag as unregistered / not confirmed as approved; request authorised reviewer assessment. Do not label it false. |
| Claim record is expired or outside its effective dates | Flag as expired/out of validity and request review. |
| Claim is registered for another product or market | Flag as scope mismatch. |

The system should not rely solely on exact string matching. It may identify paraphrases or semantic equivalents, but any uncertain match should be presented with its original extracted wording and the closest registered claim for human review.

## 4.6 Claims workbook validation

On upload, Inkloom should:

1. Verify all required columns.
2. Check that `claim_id` values are unique.
3. Validate `claim_status` and `claim_type` against permitted values.
4. Verify that referenced product IDs exist in the Product Catalogue, except for the reserved value `ALL`.
5. Require `restricted_conditions` for Restricted claims.
6. Validate effective dates and ensure the end date is not earlier than the start date.
7. Identify potentially conflicting Approved and Prohibited records for the same product, market, and wording.
8. Preview all rows and errors before import.
9. Require an authorised Knowledge Manager to confirm activation.

## 4.7 Optional worksheet — Required Disclosures

This is an optional additional worksheet within the same claims workbook. It is not a fifth onboarding category.

Use it when the organisation has specific disclosure wording that it wants Inkloom to check for in relevant advertisements.

**Worksheet name:** `Required_Disclosures`

| Column name | Description | Required? | Sample value |
|---|---|---:|---|
| `disclosure_id` | Unique disclosure identifier | Yes | DISC001 |
| `disclosure_text` | Exact required disclosure wording | Yes | Terms and conditions apply. |
| `applicable_product_id` | Product ID or `ALL` | Yes | FS-P001 |
| `applicable_market` | Country or region | Yes | India |
| `applies_when` | Condition that triggers the disclosure | Yes | When a promotional offer is advertised |
| `effective_from` | Start date | Yes | 2026-01-01 |
| `effective_until` | Expiry date; blank means no scheduled expiry | No | |

**Sample CSV header:**

```csv
disclosure_id,disclosure_text,applicable_product_id,applicable_market,applies_when,effective_from,effective_until
```

This worksheet contains company-configured disclosure rules. It does not replace the platform's responsibility to identify applicable legal requirements or the organisation's responsibility to comply with them.

---

# 5. Input 4 — Approved Brand Assets

**Collection method:** Centralised asset library with file uploads
**Who manages it:** Organisation Knowledge Manager or authorised brand representative

## 5.1 Purpose

The asset library holds official visual references that Inkloom can compare with submitted advertisements. The organisation should upload the assets it wants the platform to recognise or verify; it should not be forced to upload an exhaustive archive of every image it owns.

## 5.2 Asset upload requirements

| Asset type | Requirement | Accepted formats | Purpose |
|---|---|---|---|
| Primary brand logo | Mandatory | SVG, PNG, JPG, WebP | Compare the advertisement's logo with the official brand logo. |
| Alternate logos | Optional | SVG, PNG, JPG, WebP | Support approved light, dark, monochrome, or alternate logo versions. |
| Product photographs | Conditional | JPG, PNG, WebP | Compare advertised product appearance with official product images. |
| Product packaging / labels | Conditional | JPG, PNG, PDF | Check visible packaging and label representation. |
| Approved brand photographs | Optional | JPG, PNG, WebP | Reference approved brand or campaign photography. |
| Approved illustrations | Optional | SVG, PNG, WebP | Reference official illustrations or graphic artwork. |
| Approved icons and symbols | Optional | SVG, PNG, WebP | Check approved brand-specific icons and symbols. |
| Social media templates | Optional | PNG, JPG, PDF | Compare advertisements with official campaign or social templates. |
| Approved badges / certification artwork | Conditional | SVG, PNG, JPG, PDF | Check use of official artwork supplied by the organisation. |

### Meaning of the requirement levels

- **Mandatory:** Required for initial asset-library activation. The primary logo is required because logo consistency is a core brand-governance check.
- **Conditional:** Required only if the organisation wants Inkloom to perform that particular comparison. For example, exact packaging comparison requires an official packaging reference.
- **Optional:** Can be uploaded when available; absence must not automatically create a violation.

If the organisation has no applicable product imagery or if a particular check is outside the scope of its advertisements, the corresponding asset type need not be uploaded.

## 5.3 How assets are collected in the governance website

Create one page named **Brand Asset Library**.

### Upload experience

1. The user selects an asset category.
2. The user uploads one or multiple files.
3. Inkloom creates a preview and extracts available technical metadata automatically.
4. The user supplies the asset details listed below.
5. The asset remains Pending until an authorised person approves it.
6. Once approved, it becomes available as a reference during advertisement reviews.

### Metadata fields for each asset

| Field | Input type | Required | Sample value |
|---|---|---:|---|
| `asset_name` | Text input | Yes | Freshsip Primary Logo |
| `asset_category` | Dropdown | Yes | Primary Logo |
| `associated_product_id` | Product selector or `ALL` | Yes | ALL |
| `approval_status` | System-controlled status / authorised approval action | Yes | Approved |
| `usage_notes` | Textarea | No | Use on light backgrounds. |

The organisation should not manually enter image dimensions, pixel count, file size, colour distribution, or other technical metadata. Inkloom should extract those automatically when needed.

### Sample asset records

| File name | Asset name | Category | Associated product | Status | Usage notes |
|---|---|---|---|---|---|
| `freshsip_logo.svg` | Freshsip Primary Logo | Primary Logo | ALL | Approved | Use on light backgrounds. |
| `sunrise_mango.png` | Sunrise Mango Product Image | Product Photograph | FS-P001 | Approved | Official 250 ml bottle image. |
| `mango_packaging.png` | Sunrise Mango Packaging | Packaging / Label | FS-P001 | Approved | Current approved packaging reference. |

These are illustrative records. The actual uploaded files must be supplied by the organisation.

## 5.4 Asset-library behaviour

The website should support:

- Multiple-file upload.
- Category selection.
- Product/brand association.
- Preview and download for authorised users.
- Pending, Approved, and Retired states.
- Replacing an asset while retaining its previous version.
- Duplicate file detection.
- Secure private storage and organisation-level access separation.
- Audit records showing who uploaded, approved, replaced, or retired an asset.

A Retired asset must not be treated as an active approved reference for new reviews. Historical reviews should retain the reference/version that was used at the time of review.

---

# 6. What is not a separate organisation input category

The earlier proposed category **Mandatory and Prohibited Rules** is removed as a standalone onboarding section.

Many checks in that category are platform-level governance checks or can be derived from the four agreed input categories.

| Governance check | Source used by Inkloom |
|---|---|
| Check for logo distortion or unauthorised logo variants | Built-in logo checks + Approved Brand Assets |
| Check use of brand colours | Brand Guidelines |
| Check typography preferences | Brand Guidelines |
| Check brand voice and tone | Brand Guidelines |
| Check preferred/prohibited terminology | Brand Guidelines |
| Check whether promotional claims are authorised | Claims Register |
| Check restrictions and claim conditions | Claims Register |
| Check product facts and specifications | Product Catalogue |
| Check whether a product is active or discontinued | Product Catalogue |
| Compare product imagery and packaging | Approved Brand Assets |
| Check text readability and contrast | Built-in accessibility checks, with any configured brand-specific preferences |
| Check company-specific required disclosures | Optional `Required_Disclosures` worksheet |

## 6.1 Built-in checks versus organisation-specific information

Inkloom should implement generic checks internally where they do not require organisation-specific knowledge. Examples include:

- OCR and visible-text extraction.
- Logo detection and comparison against uploaded approved logos.
- Basic image and object detection.
- Text readability and contrast analysis.
- Detection of potentially misleading or implied messaging for reviewer attention.
- Detection of claims that are not present in the organisation's register.
- Review history and repeated-issue analysis.

The organisation should not have to manually configure every technical check. It should supply its own brand-specific knowledge and approved references.

For accessibility, the platform may use established defaults such as WCAG contrast guidance. These are platform defaults, not mandatory brand-profile fields. A legal or accessibility assessment may require context-specific human review.

---

# 7. Organisation onboarding workflow

The Knowledge Manager should experience a short, guided setup process.

## Step 1 — Create the Brand Profile

- Enter the Brand Guidelines through the structured form.
- Add the mandatory brand identity, voice, colour, typography, and visual-identity information.
- Save as Draft until reviewed.

## Step 2 — Import the Product Catalogue

- Download the provided Excel template.
- Populate one row per product variant or service offering.
- Upload the workbook.
- Review validation errors and row previews.
- Confirm the import.

## Step 3 — Import the Claims Register

- Download the Claims Register template.
- Add Approved, Restricted, and Prohibited claims.
- Specify applicable product, market, conditions, and validity dates.
- Optionally complete the `Required_Disclosures` worksheet.
- Upload and validate the workbook.
- Confirm the import.

## Step 4 — Upload Approved Brand Assets

- Upload the primary logo.
- Upload product photographs and packaging references where those checks are required.
- Add optional approved photographs, illustrations, icons, templates, and badge artwork.
- Add asset metadata and submit for approval.

## Step 5 — Review and Activate

- Show a summary of all four categories.
- Identify missing mandatory information.
- Show product and claims import errors.
- Identify assets still Pending.
- Require an authorised Knowledge Manager to confirm the knowledge base.
- Activate the approved version for advertisement reviews.

### Suggested activation statuses

| Status | Meaning |
|---|---|
| Draft | Information is being entered or edited. |
| Validation Required | Errors or incomplete mandatory data need attention. |
| Pending Approval | Submitted for confirmation by an authorised person. |
| Active | Approved and available for advertisement governance reviews. |
| Superseded | Replaced by a newer approved version. |
| Archived | No longer active but retained for historical records. |

---

# 8. How the four inputs are used during an advertisement review

The organisation should provide its knowledge base once and maintain it. Creators should not need to re-enter this information for every advertisement.

## 8.1 Advertisement submission inputs

For each new advertisement, the creator should normally provide:

- The advertisement file (image, video, document, or supported content format).
- The product/service being advertised.
- The intended publication platform, where relevant.
- The target country/market, if it cannot be reliably inferred from the organisation's configuration or campaign.

Inkloom should retrieve the applicable brand guidelines, product record, claims, disclosures, and approved assets automatically.

## 8.2 Example — Freshsip advertisement

**Submitted advertisement contains:**

- Freshsip logo.
- Product name: Sunrise Mango.
- Claim: Made with real mango pulp.
- Claim: No Added Sugar.
- Bottle image showing 250 ml.
- Mango imagery.
- A 20% discount message.

**Inkloom retrieves and compares:**

| Advertisement element | Organisation source | Example check |
|---|---|---|
| Freshsip logo | Approved Brand Assets | Does it match an approved logo version? |
| Colours and typography | Brand Guidelines | Are they consistent with configured preferences? |
| Product name | Product Catalogue | Does the product exist and is it active? |
| Ingredient wording | Product Catalogue + Claims Register | Is the ingredient information consistent, and is the advertising wording authorised? |
| No Added Sugar | Claims Register | Is it Approved, Restricted, or Prohibited for this product and market? |
| 250 ml | Product Catalogue | Does the quantity match the selected variant? |
| Mango visual | Product information + Approved Brand Assets | Is the visual consistent with the product and available approved references? |
| 20% discount | Optional Required_Disclosures / configured conditions | Are any company-configured offer disclosures required? |

The platform must distinguish an observed mismatch from a claim that has not been independently verified. For example, a company-authorised claim may be matched against the register, but the system must not state that it independently tested or proved the product.

---

# 9. Data governance and system safeguards

These are platform implementation responsibilities rather than additional organisation onboarding categories.

## 9.1 Organisation separation and access

- Store each organisation's knowledge base separately using organisation-scoped access controls.
- Prevent users from one organisation from accessing another organisation's product records, claims, assets, or review history.
- Restrict editing and approval of the knowledge base to authorised roles.
- Use private storage for confidential uploaded assets and documents.

## 9.2 Version control

- Keep versions of Brand Guidelines, Product Catalogue records, Claims Register records, and Brand Assets.
- Record who created, edited, approved, retired, or imported each item.
- Retain the version used for each completed advertisement review.
- Do not silently apply a newly edited claim or logo to an old review record.

## 9.3 Import and approval controls

- Validate spreadsheets before writing data to the active knowledge base.
- Show a preview and actionable error report.
- Support correction and re-upload.
- Require authorised confirmation before activation.
- Preserve the last active version if a new import fails validation.

## 9.4 Missing or ambiguous information

- Missing reference information should be labelled as unavailable, not automatically non-compliant.
- A claim absent from the Claims Register should be labelled unregistered or not confirmed as approved.
- A missing product image should mean exact visual comparison is unavailable; it should not automatically mean the advertisement is wrong.
- Ambiguous semantic claim matches should be sent for human review rather than treated as definitive violations.
- If a product is inactive or discontinued, the review should flag that status and show the relevant catalogue record.

---

# 10. Final scope summary

| No. | Organisation input | Collection method | Mandatory minimum |
|---:|---|---|---|
| 1 | Brand Guidelines | Structured website form | Brand identity, voice/tone, language, colour palette, typography, visual style and imagery preferences |
| 2 | Product / Service Information | Excel workbook | Product/service identity, category, description, market, status and applicable factual specifications |
| 3 | Approved / Restricted Claims | Excel workbook | Claim wording, type, status, applicable product, market and effective date; conditions for Restricted claims |
| 4 | Approved Brand Assets | Central asset library | At least one primary logo; additional assets based on the visual checks required |

### Final product boundary

Inkloom AI is an internal brand-governance and review system. The organisation supplies its brand rules, product information, claim authorisations, and approved visual references. Inkloom extracts content from submitted advertisements, compares it against that information, explains detected issues, suggests corrections, and supports human review and approval.

Inkloom is not positioned as a public fact-checking service, product-testing service, laboratory verification platform, or substitute for legal/regulatory review. Company-provided approval is the internal governance reference; it is not a guarantee that a claim is independently true or legally substantiated.

**This four-category specification is the agreed minimum organisation onboarding scope for the Inkloom AI MVP.**
