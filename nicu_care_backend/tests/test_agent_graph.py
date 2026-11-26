"""
Integration tests for the LangGraph Multi-Agent State Machine.
Verifies emergency bypass, structured care logging, clinical RAG, and cache hit.
"""

import pytest
from app.agent.graph import nicu_agent
from app.routers.agent import process_text_query, cache_service
from app.models.agent import TextQueryRequest
from app.services.wiki_service import WikiService


@pytest.fixture(autouse=True)
def setup_test_baby():
    cache_service.clear()
    wiki_svc = WikiService()
    if not wiki_svc.load_baby_profile_json("baby_liam_01"):
        import datetime
        from app.models.baby import BabyProfile
        baby = BabyProfile(
            baby_id="baby_liam_01",
            name="Liam",
            date_of_birth=datetime.date.today() - datetime.timedelta(days=56),
            gestational_age_weeks=29,
            gestational_age_days=2,
            sex="male",
            birth_weight_grams=1180,
            discharge_weight_grams=1820,
            discharge_date=datetime.date.today() - datetime.timedelta(days=21),
            discharge_hospital="BirthRight Rainbow Vijayawada",
        )
        wiki_svc.save_baby_profile_json(baby)
        wiki_svc.create_profile_from_baby(baby)


def test_agent_emergency_triage_flow():
    req = TextQueryRequest(
        baby_id="baby_liam_01",
        text="Baby's lips look blue and chest is retracting under the ribs",
    )
    res = process_text_query(req)

    assert res.is_emergency is True
    assert res.intent == "EMERGENCY"
    assert "URGENT CLINICAL ATTENTION" in res.text_card or "NICU emergency" in res.text_card


def test_agent_log_feed_flow():
    req = TextQueryRequest(
        baby_id="baby_liam_01",
        text="Logged 50 mL fortified breast milk at 10 AM, baby drank well",
    )
    res = process_text_query(req)

    assert res.is_emergency is False
    assert res.intent == "LOG_FEED"
    assert "50.0 mL" in res.text_card or "50 mL" in res.text_card
    assert res.next_reminder_minutes == 180


def test_agent_log_diaper_flow():
    req = TextQueryRequest(
        baby_id="baby_liam_01",
        text="Changed diaper: wet with yellow seedy poop",
    )
    res = process_text_query(req)

    assert res.is_emergency is False
    assert res.intent == "LOG_DIAPER"
    assert "Diaper" in res.text_card


def test_agent_hospital_lookup_flow():
    req = TextQueryRequest(
        baby_id="baby_liam_01",
        text="What is the Rainbow Hospital Vijayawada emergency phone number?",
    )
    res = process_text_query(req)

    assert res.intent == "HOSPITAL_LOOKUP"
    assert "+91 866 666 9000" in res.text_card
    assert "+91 866 669 0000" in res.text_card


def test_agent_clinical_guidance_flow():
    req = TextQueryRequest(
        baby_id="baby_liam_01",
        text="How to safely practice kangaroo mother care skin to skin?",
    )
    res = process_text_query(req)

    assert res.is_emergency is False
    assert "Clinical Guidance" in res.text_card
    assert "disclaimer" in res.text_card.lower()


def test_agent_semantic_cache_hit():
    req = TextQueryRequest(
        baby_id="baby_liam_01",
        text="What are safe sleep guidelines for preterm infant crib?",
    )
    # First call: computes and sets cache
    res1 = process_text_query(req)
    assert res1 is not None

    # Second call: fast-path cache hit
    res2 = process_text_query(req)
    assert res2.text_card == res1.text_card
