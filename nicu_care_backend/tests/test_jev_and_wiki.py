"""
Unit tests for Jev Decision Engine and LLM Wiki Curator.
"""

import pytest
from app.agent.jev_service import JevDecisionEngine, JevNoulResult, JevChoiceResult
from app.agent.llm_wiki_curator import LLMWikiCurator
from app.services.wiki_service import WikiService


@pytest.fixture
def jev():
    return JevDecisionEngine()


@pytest.fixture
def curator():
    return LLMWikiCurator()


# ── Jev Decision Engine Tests ─────────────────────────────────────────

def test_jev_emergency_noul_true(jev):
    query = "Baby has chest retractions and is grunting"
    res = jev.evaluate_emergency_noul(query)

    assert isinstance(res, JevNoulResult)
    assert res.value is True
    assert res.probability >= 0.70
    assert "retraction" in res.reasoning.lower() or "grunting" in res.reasoning.lower()


def test_jev_emergency_noul_false(jev):
    query = "Liam drank 55 mL of milk and slept well"
    res = jev.evaluate_emergency_noul(query)

    assert isinstance(res, JevNoulResult)
    assert res.value is False
    assert res.probability < 0.10


def test_jev_routing_choice_feed(jev):
    query = "Logged 50 ml breast milk with fortifier"
    res = jev.route_intent_choice(query)

    assert isinstance(res, JevChoiceResult)
    assert res.choice == "LOG_FEED"
    assert res.confidence >= 0.90


def test_jev_routing_choice_emergency(jev):
    query = "Baby's lips look blue and breathing stopped"
    res = jev.route_intent_choice(query)

    assert isinstance(res, JevChoiceResult)
    assert res.choice == "EMERGENCY"


def test_jev_routing_choice_hospital(jev):
    query = "What is the emergency helpline number for Rainbow Hospital?"
    res = jev.route_intent_choice(query)

    assert isinstance(res, JevChoiceResult)
    assert res.choice == "HOSPITAL_LOOKUP"


def test_jev_safety_score_unsafe(jev):
    unsafe_text = "You can give the newborn baby some honey or water for colic."
    res = jev.score_safety_level(unsafe_text)

    assert res.level == "UNSAFE"
    assert res.numeric_score >= 0.90


# ── LLM Wiki Curator Tests ────────────────────────────────────────────

def test_wiki_curator_extract_regimen_change(curator):
    conversation = "The pediatrician increased his iron dose to 1.2 mL daily."
    res = curator.extract_and_patch_wiki("baby_liam_01", conversation)

    assert res["success"] is True
    assert "active_regimen" in res["patches_applied"]

    # Verify wiki section contains the update
    content = curator.wiki_service.read_section("baby_liam_01", "active_regimen")
    assert "1.2 mL" in content


def test_wiki_curator_extract_clinical_alert(curator):
    conversation = "Baby had an episode of reflux and choking after feeding."
    res = curator.extract_and_patch_wiki("baby_liam_01", conversation)

    assert res["success"] is True
    assert "clinical_alerts" in res["patches_applied"]

    content = curator.wiki_service.read_section("baby_liam_01", "clinical_alerts")
    assert "reflux" in content.lower()


def test_wiki_curator_compilation(curator):
    compiled = curator.compile_full_context_for_llm("baby_liam_01")

    assert "BABY HEALTH LIVING WIKI MEMORY" in compiled
    assert "[BABY PROFILE]" in compiled
    assert "[ACTIVE REGIMEN]" in compiled
    assert "[CLINICAL ALERTS]" in compiled
