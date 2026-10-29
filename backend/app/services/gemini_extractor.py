import os
import time
import random
import logging
from typing import Tuple, List, Dict, Any, Optional
from google import genai
from google.genai import types
from pydantic import ValidationError

from app.config import settings
from app.services.extraction_schemas import (
    StrictKnowledgeDocumentExtraction,
    get_gemini_extraction_response_schema
)

logger = logging.getLogger(__name__)


class GeminiConfigurationError(Exception):
    """Raised when Gemini API key or model configuration is missing or invalid."""
    pass


class GeminiExtractionError(Exception):
    """Raised when the Gemini extraction request or validation fails."""
    pass


EXTRACTION_SYSTEM_PROMPT = """You are an expert brand governance and regulatory compliance knowledge extraction engine for Inkloom AI.
Your job is to read internal brand manuals, specifications, and guidelines (in PDF format) and extract all normative rules, specifications, claims, asset policies, and document metadata into structured JSON adhering to the specified schema.

Extraction Principles:
1. Strict Grounding: Every rule, fact, and claim must be grounded in explicit passages from the document. Do not invent specifications or assume facts not present.
2. Concise Normative Output:
   - For brand rules, extract the concise requirement statement (1-2 sentences), relevant conditions, exceptions, and preferred alternatives.
   - Do NOT generate synthetic or verbose bad/good examples; only include them if explicitly listed in the document. Otherwise leave examples_bad and examples_good as empty arrays [].
   - Keep rationales concise (1 sentence). Do not repeat entire page paragraphs.
3. Differentiate Document Status from Review Lifecycle:
   - source_status represents the status assigned by the author in the document (approved, pending_review, expired, or rejected).
4. Product Facts vs Data Gaps:
   - When a specification explicitly states a value, value_status is "explicitly_stated".
   - When the document explicitly marks an attribute as missing, missing_not_provided, or pending lab tests, record value_status="missing_not_provided" and value="not_provided".
   - When information is noted as existing in an external unsupplied file (e.g. freshsip_products.csv, FS-SPEC-001..006), record external_reference_needed. Do not extrapolate or guess values.
5. Non-Governance Exclusions:
   - Separate informational audience demographics, market regulatory context, illustrative campaign footnotes, and platform disclaimers into document_metadata.non_governance_elements. Do NOT turn them into active governance rules.
6. Contextual Rules:
   - When a rule distinguishes educational disclaimers from promotional product attributions, record that in exceptions and context_condition.
"""

EXTRACTION_USER_PROMPT = """Please inspect the uploaded brand guidelines PDF thoroughly, across all pages, tables, callout boxes, and figures.
Extract all:
1. Brand Rules (canonical rule code, title, concise requirement statement, context conditions, exceptions, recommended alternatives, supporting quotation passage, and 1-indexed page number).
2. Product Facts (product code/name, attribute key, value, unit, value_status, and supporting quotation).
3. Claims (claim text, category including allergen_food_safety, permitted/rejected/pending/expired decision, and supporting evidence).
4. Asset Policies (parent rule code e.g. FR-RULE-017, asset target, policy statement, clearance/margins, and supporting quotation).
5. Document Metadata and non-governance exclusions.

Output must strictly conform to the response JSON schema."""


def _classify_gemini_error(exc: Exception) -> Tuple[str, Optional[int], str]:
    """
    Classifies Gemini API exceptions into distinct operational categories:
    - 'transient_503': Temporary server unavailability (retryable once with backoff+jitter)
    - 'quota_429': Daily or persistent resource quota exhausted (non-retryable, abort immediately)
    - 'rate_limit_429': Short-term per-minute rate limit (non-retryable unless configured, report immediately)
    - 'non_transient': Authentication, invalid payload, model not found, schema, etc. (abort immediately)
    """
    err_str = str(exc)
    err_lower = err_str.lower()
    code = getattr(exc, "code", None)

    # 1. Check for 503 Service Unavailable
    if code == 503 or "503" in err_str or "unavailable" in err_lower:
        return "transient_503", 503, err_str

    # 2. Check for 429 Resource Exhausted / Rate Limit
    if code == 429 or "429" in err_str or "resource_exhausted" in err_lower:
        if any(term in err_lower for term in ("daily", "quota", "per-day", "per_day", "exhausted")):
            return "quota_429", 429, err_str
        return "rate_limit_429", 429, err_str

    return "non_transient", code, err_str


def run_gemini_pdf_extraction(
    pdf_path: str,
    filename: str,
    known_matrix: Optional[Dict[str, Any]] = None
) -> Tuple[StrictKnowledgeDocumentExtraction, Dict[str, Any]]:
    """
    Performs live extraction of structured brand knowledge from a PDF using Gemini.
    Injects pre-extracted traceability matrix context if available to eliminate redundant AI generation.
    Enforces a bounded retry policy: at most 1 retry for transient 503 UNAVAILABLE with exponential backoff & jitter.
    Distinctly handles 429 quota exhaustion, 429 rate limit, and non-transient failures by immediately stopping.
    Validates the result against StrictKnowledgeDocumentExtraction with extra="forbid".
    Returns the parsed extraction document alongside structured timing and token metrics.
    Ensures temporary Gemini Files API resources are deleted in a finally block.
    """
    api_key = os.getenv("GEMINI_API_KEY", settings.GEMINI_API_KEY)
    if not api_key or not api_key.strip():
        raise GeminiConfigurationError(
            "GEMINI_API_KEY is not configured on the backend. "
            "Please configure GEMINI_API_KEY in backend/.env to enable Gemini knowledge extraction."
        )

    model_name = os.getenv("GEMINI_MODEL", getattr(settings, "GEMINI_MODEL", "gemini-3.8-flash"))
    if not os.path.exists(pdf_path):
        raise GeminiExtractionError(f"Target document not found at: {pdf_path}")

    # Build prompt with known matrix context if available
    user_prompt = EXTRACTION_USER_PROMPT
    if known_matrix:
        matrix_lines = []
        for code, meta in known_matrix.items():
            matrix_lines.append(
                f"- {code}: {meta.get('title')} | category={meta.get('category')}, "
                f"type={meta.get('rule_type')}, severity={meta.get('severity')}, "
                f"action={meta.get('enforcement_action')}, status={meta.get('source_status')}"
            )
        matrix_context = (
            "\n\nPre-Extracted Document Traceability Matrix:\n"
            + "\n".join(matrix_lines)
            + "\nUse the canonical rule codes and titles above. You do NOT need to regenerate verbose metadata tables or guess different severities."
        )
        user_prompt += matrix_context

    timing_metrics: Dict[str, Any] = {
        "upload_duration_ms": 0.0,
        "generation_duration_ms": 0.0,
        "parse_duration_ms": 0.0,
        "input_tokens": None,
        "output_tokens": None,
        "retry_count": 0,
        "attempts": [],
        "model": model_name
    }

    client = genai.Client(api_key=api_key, http_options=types.HttpOptions(timeout=25000))
    uploaded_file = None

    try:
        logger.info(f"Uploading '{filename}' to Gemini Files API...")
        t_up0 = time.perf_counter()
        uploaded_file = client.files.upload(file=pdf_path)
        timing_metrics["upload_duration_ms"] = round((time.perf_counter() - t_up0) * 1000, 2)
        logger.info(f"File uploaded in {timing_metrics['upload_duration_ms']}ms: {uploaded_file.name}")

        response_schema = get_gemini_extraction_response_schema()
        config = types.GenerateContentConfig(
            system_instruction=EXTRACTION_SYSTEM_PROMPT,
            response_mime_type="application/json",
            response_schema=response_schema,
            temperature=0.1,
        )

        MAX_GENERATION_ATTEMPTS = 2  # 1 initial attempt + maximum 1 retry for transient 503
        response = None
        gen_start_total = time.perf_counter()

        for attempt in range(1, MAX_GENERATION_ATTEMPTS + 1):
            logger.info(f"Gemini generation attempt {attempt}/{MAX_GENERATION_ATTEMPTS} using model '{model_name}'...")
            t_attempt_start = time.perf_counter()

            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=[uploaded_file, user_prompt],
                    config=config,
                )
                attempt_ms = round((time.perf_counter() - t_attempt_start) * 1000, 2)
                timing_metrics["attempts"].append({
                    "attempt": attempt,
                    "duration_ms": attempt_ms,
                    "outcome": "success"
                })
                logger.info(f"Gemini generation attempt {attempt} succeeded in {attempt_ms}ms")
                break
            except Exception as e:
                attempt_ms = round((time.perf_counter() - t_attempt_start) * 1000, 2)
                clean_err = str(e).replace(api_key, "[REDACTED_API_KEY]") if api_key else str(e)
                err_category, err_code, _ = _classify_gemini_error(e)

                timing_metrics["attempts"].append({
                    "attempt": attempt,
                    "duration_ms": attempt_ms,
                    "outcome": err_category,
                    "error_code": err_code
                })

                # Bounded retry: ONLY for transient 503 UNAVAILABLE on the first attempt
                if err_category == "transient_503" and attempt < MAX_GENERATION_ATTEMPTS:
                    timing_metrics["retry_count"] += 1
                    # Bounded backoff with jitter (2.0s base + 0.5 to 1.5s jitter)
                    backoff_sec = 2.0 + random.uniform(0.5, 1.5)
                    logger.warning(
                        f"Gemini generation attempt {attempt} encountered 503 UNAVAILABLE after {attempt_ms}ms. "
                        f"Backing off with jitter for {backoff_sec:.2f}s before bounded retry 1/1..."
                    )
                    time.sleep(backoff_sec)
                    continue

                if err_category == "quota_429":
                    logger.error(f"Gemini daily quota exhausted (HTTP 429) on attempt {attempt} after {attempt_ms}ms: {clean_err}")
                    raise GeminiExtractionError(f"Gemini daily quota exhausted (HTTP 429): {clean_err}. Stopping.")

                if err_category == "rate_limit_429":
                    logger.error(f"Gemini short-term rate limit reached (HTTP 429) on attempt {attempt} after {attempt_ms}ms: {clean_err}")
                    raise GeminiExtractionError(f"Gemini rate limit reached (HTTP 429): {clean_err}. Stopping.")

                if err_category == "transient_503":
                    logger.error(f"Gemini generation attempt {attempt} failed after {attempt_ms}ms. All {MAX_GENERATION_ATTEMPTS} attempts exhausted: {clean_err}")
                    raise GeminiExtractionError(f"Gemini 503 UNAVAILABLE persists after {MAX_GENERATION_ATTEMPTS} attempts: {clean_err}")

                # Non-transient errors (auth, bad request, model not found, etc.)
                logger.error(f"Gemini generation attempt {attempt} failed with non-transient error after {attempt_ms}ms: {clean_err}")
                raise GeminiExtractionError(f"Gemini non-transient error: {clean_err}")

        timing_metrics["generation_duration_ms"] = round((time.perf_counter() - gen_start_total) * 1000, 2)

        # Extract token counts if available
        if response and hasattr(response, "usage_metadata") and response.usage_metadata:
            timing_metrics["input_tokens"] = getattr(response.usage_metadata, "prompt_token_count", None)
            timing_metrics["output_tokens"] = getattr(response.usage_metadata, "candidates_token_count", None)

        if not response or not response.text:
            raise GeminiExtractionError("Gemini returned an empty response.")

        logger.info("Parsing and performing strict local Pydantic validation (extra='forbid')...")
        t_parse0 = time.perf_counter()
        try:
            extracted_doc = StrictKnowledgeDocumentExtraction.model_validate_json(response.text)
        except ValidationError as ve:
            logger.error(f"Strict local validation failed on Gemini response: {ve}")
            raise GeminiExtractionError(
                f"Model response violated strict local schema constraints: {ve.errors()[:3]}"
            )
        timing_metrics["parse_duration_ms"] = round((time.perf_counter() - t_parse0) * 1000, 2)

        return extracted_doc, timing_metrics

    except GeminiConfigurationError:
        raise
    except GeminiExtractionError:
        raise
    except Exception as e:
        clean_err = str(e).replace(api_key, "[REDACTED_API_KEY]") if api_key else str(e)
        logger.error(f"Gemini extraction failed: {clean_err}")
        raise GeminiExtractionError(f"Gemini extraction failed: {clean_err}")

    finally:
        if uploaded_file and hasattr(uploaded_file, "name"):
            try:
                client.files.delete(name=uploaded_file.name)
                logger.info(f"Cleaned up temporary Gemini file: {uploaded_file.name}")
            except Exception as del_err:
                logger.warning(f"Could not delete temporary Gemini file {uploaded_file.name}: {del_err}")


