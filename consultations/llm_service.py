"""
consultations/llm_service.py
LLM integration for pre-visit and post-visit AI summaries.

When ``settings.MOCK_LLM`` is True (the default for local dev), the service
returns realistic canned data without calling any external API.  In
production, it calls the Anthropic API via the ``anthropic`` Python SDK.

**Error contract:** Both public functions return a dict on success and raise
``LLMGenerationError`` on any failure (network, API error, malformed JSON).
Callers are expected to catch this and degrade gracefully — LLM failures
must *never* block the booking or visit flow.
"""

import json
import logging

from django.conf import settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Custom exception
# ---------------------------------------------------------------------------

class LLMGenerationError(Exception):
    """Raised when the LLM service cannot produce a valid result."""


# ---------------------------------------------------------------------------
# Mock responses (used when settings.MOCK_LLM is True)
# ---------------------------------------------------------------------------

_MOCK_PRE_VISIT = {
    "urgency_level": "Medium",
    "chief_complaint": "Recurring headaches with occasional dizziness",
    "suggested_questions": [
        "How often do the headaches occur and how long do they last?",
        "Are the headaches accompanied by visual disturbances or nausea?",
        "Have you noticed any triggers such as stress, certain foods, or lack of sleep?",
    ],
}

_MOCK_POST_VISIT = {
    "patient_summary": (
        "Your doctor has diagnosed tension-type headaches, likely related to "
        "stress and posture. The prescribed treatment includes a mild pain "
        "reliever and a muscle relaxant to be taken as directed. Staying "
        "hydrated, maintaining good posture, and managing stress through "
        "relaxation techniques are strongly recommended."
    ),
    "medications": [
        {
            "name": "Ibuprofen",
            "dosage": "400 mg",
            "frequency": "Twice daily after meals",
            "duration_days": 7,
        },
        {
            "name": "Cyclobenzaprine",
            "dosage": "5 mg",
            "frequency": "Once daily at bedtime",
            "duration_days": 5,
        },
    ],
    "follow_up_steps": (
        "1. Take medications as prescribed for the full duration.\n"
        "2. Apply a warm compress to the neck and shoulders for 15 minutes "
        "twice daily.\n"
        "3. Schedule a follow-up visit in 2 weeks if symptoms persist.\n"
        "4. Seek immediate medical attention if you experience sudden severe "
        "headaches, vision loss, or difficulty speaking."
    ),
}


# ---------------------------------------------------------------------------
# Anthropic API helpers (real LLM calls)
# ---------------------------------------------------------------------------

def _call_anthropic(system_prompt: str, user_prompt: str) -> dict:
    """
    Call the Anthropic API and parse the JSON response.

    Raises ``LLMGenerationError`` on any failure.
    """
    try:
        import anthropic  # noqa: F811 — imported lazily so mock mode works without the SDK
    except ImportError:
        raise LLMGenerationError(
            "The 'anthropic' package is not installed. "
            "Install it with: pip install anthropic"
        )

    api_key = getattr(settings, "LLM_API_KEY", "")
    model = getattr(settings, "LLM_MODEL", "claude-sonnet-4-6")

    if not api_key:
        raise LLMGenerationError("LLM_API_KEY is not configured.")

    try:
        client = anthropic.Anthropic(api_key=api_key)
        message = client.messages.create(
            model=model,
            max_tokens=1024,
            system=system_prompt,
            messages=[
                {"role": "user", "content": user_prompt},
            ],
        )
        raw_text = message.content[0].text
    except Exception as exc:
        logger.exception("Anthropic API call failed.")
        raise LLMGenerationError(f"API call failed: {exc}") from exc

    # Parse JSON defensively
    try:
        data = json.loads(raw_text)
    except (json.JSONDecodeError, TypeError) as exc:
        logger.error("Failed to parse LLM JSON response: %s", raw_text[:500])
        raise LLMGenerationError(
            f"LLM returned invalid JSON: {exc}"
        ) from exc

    return data


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_pre_visit_summary(symptoms_text: str) -> dict:
    """
    Analyse patient symptoms and return:
    ``{"urgency_level": str, "chief_complaint": str, "suggested_questions": [str, str, str]}``

    Raises ``LLMGenerationError`` on failure.
    """
    if getattr(settings, "MOCK_LLM", True):
        logger.info("MOCK_LLM is True — returning canned pre-visit summary.")
        return dict(_MOCK_PRE_VISIT)  # shallow copy

    system_prompt = (
        "You are a medical triage assistant. Respond with ONLY a valid JSON "
        "object — no markdown, no explanation. The JSON must have exactly "
        "these keys:\n"
        '  {"urgency_level": "<Low|Medium|High>", '
        '"chief_complaint": "<string>", '
        '"suggested_questions": ["<q1>", "<q2>", "<q3>"]}'
    )
    user_prompt = (
        "Analyse these symptoms and return: urgency level (Low / Medium / "
        "High), chief complaint, and three suggested questions for the "
        f"doctor. Symptoms: {symptoms_text}"
    )

    data = _call_anthropic(system_prompt, user_prompt)

    # Validate expected keys
    for key in ("urgency_level", "chief_complaint", "suggested_questions"):
        if key not in data:
            raise LLMGenerationError(f"LLM response missing key: '{key}'")

    return data


def generate_post_visit_summary(
    clinical_notes: str,
    prescription_text: str,
) -> dict:
    """
    Convert clinical notes + prescription into a patient-friendly summary:
    ``{"patient_summary": str, "medications": [{"name":..., "dosage":...,
    "frequency":..., "duration_days":...}], "follow_up_steps": str}``

    Raises ``LLMGenerationError`` on failure.
    """
    if getattr(settings, "MOCK_LLM", True):
        logger.info("MOCK_LLM is True — returning canned post-visit summary.")
        return dict(_MOCK_POST_VISIT)  # shallow copy

    combined_notes = (
        f"Clinical notes:\n{clinical_notes}\n\n"
        f"Prescription:\n{prescription_text}"
    )

    system_prompt = (
        "You are a medical documentation assistant. Respond with ONLY a "
        "valid JSON object — no markdown, no explanation. The JSON must "
        "have exactly these keys:\n"
        '  {"patient_summary": "<string>", '
        '"medications": [{"name": "<string>", "dosage": "<string>", '
        '"frequency": "<string>", "duration_days": <int>}], '
        '"follow_up_steps": "<string>"}'
    )
    user_prompt = (
        "Convert these clinical notes into a patient-friendly summary with "
        f"medication schedule and follow-up steps:\n{combined_notes}"
    )

    data = _call_anthropic(system_prompt, user_prompt)

    # Validate expected keys
    for key in ("patient_summary", "medications", "follow_up_steps"):
        if key not in data:
            raise LLMGenerationError(f"LLM response missing key: '{key}'")

    return data
