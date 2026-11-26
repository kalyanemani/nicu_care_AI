"""
Unit tests for all 4 Guardrail Layers:
Layer 1 (Input), Layer 2 (Retrieval), Layer 3 (Tool), Layer 4 (Output).
"""

from app.agent.guardrails.input_guardrails import InputGuardrails
from app.agent.guardrails.retrieval_guardrails import RetrievalGuardrails
from app.agent.guardrails.tool_guardrails import ToolGuardrails
from app.agent.guardrails.output_guardrails import OutputGuardrails


# ── Layer 1: Input Guardrails ─────────────────────────────────────────

def test_input_emergency_apnea_detection():
    res = InputGuardrails.scan_for_emergency("Baby stopped breathing for 25 seconds")
    assert res["is_emergency"] is True
    assert any("breathing" in f or "apnea" in f for f in res["matched_indicators"])


def test_input_emergency_cyanosis_retraction():
    res = InputGuardrails.scan_for_emergency("Lips look blue and chest retracting under ribs")
    assert res["is_emergency"] is True
    assert "blue" in res["matched_indicators"] or "retraction" in res["matched_indicators"]


def test_input_emergency_routine_feed_false():
    res = InputGuardrails.scan_for_emergency("Liam had 50 ml breast milk at 10 AM")
    assert res["is_emergency"] is False


def test_input_phi_masking():
    raw = "My phone is 9876543210 and Aadhaar is 1234 5678 9012, email me at mother@example.com"
    masked = InputGuardrails.mask_phi(raw)

    assert "9876543210" not in masked
    assert "1234 5678 9012" not in masked
    assert "mother@example.com" not in masked
    assert "[REDACTED_PHONE]" in masked
    assert "[REDACTED_ID]" in masked
    assert "[REDACTED_EMAIL]" in masked


# ── Layer 2: Retrieval Guardrails ─────────────────────────────────────

def test_retrieval_gestational_age_filter():
    mock_chunks = [
        {"chunk_id": "c1", "metadata": {"min_corrected_weeks": 0, "max_corrected_weeks": 12}},
        {"chunk_id": "c2", "metadata": {"min_corrected_weeks": 24, "max_corrected_weeks": 52}}, # older infants
    ]
    # For a 4-week corrected baby, only c1 applies
    filtered = RetrievalGuardrails.filter_by_gestational_age(mock_chunks, baby_corrected_weeks=4)
    assert len(filtered) == 1
    assert filtered[0]["chunk_id"] == "c1"


def test_retrieval_relevance_floor():
    mock_scored = [
        {"chunk_id": "high", "score": 0.85},
        {"chunk_id": "low", "score": 0.30},
    ]
    res = RetrievalGuardrails.apply_relevance_floor(mock_scored, floor=0.65)
    assert len(res) == 1
    assert res[0]["chunk_id"] == "high"


# ── Layer 4: Output Guardrails ────────────────────────────────────────

def test_output_banned_honey_blocked():
    unsafe_text = "You can add a small drop of honey to soothe the baby's throat."
    res = OutputGuardrails.verify_and_sanitize(unsafe_text)

    assert res["passed"] is False
    assert any("honey" in v for v in res["violations"])
    assert "guidelines advise against it" in res["sanitized_text"]


def test_output_banned_water_blocked():
    unsafe_text = "Give the 2-week-old infant some plain water between feeds for hiccups."
    res = OutputGuardrails.verify_and_sanitize(unsafe_text)

    assert res["passed"] is False
    assert any("water" in v for v in res["violations"])


def test_output_mandatory_disclaimer_appended():
    safe_text = "Continue keeping baby upright for 20 minutes after feeding to reduce spit-up."
    res = OutputGuardrails.verify_and_sanitize(safe_text)

    assert res["passed"] is True
    assert "disclaimer" in res["sanitized_text"].lower()
    assert "supportive" in res["sanitized_text"].lower()
