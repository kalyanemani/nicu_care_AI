"""
Unit tests for Strict Out-of-Domain Guardrails, Quality-Gated Caching,
and Care Timeline Completion Disambiguation.
"""

import pytest
from app.agent.guardrails.input_guardrails import InputGuardrails
from app.routers.agent import process_text_query
from app.models.agent import TextQueryRequest
from app.services.timeline_service import TimelineService
from app.services.graph_rag_service import graph_rag_service


def test_out_of_domain_query_strictly_blocked():
    out_of_domain_queries = [
        "How do I buy bitcoin or ethereum crypto?",
        "Write a Python script to sort an array using quicksort",
        "Who won the cricket match yesterday?",
        "What is the best recipe for chocolate cake?",
        "Who is the current prime minister of the UK?",
    ]
    for q in out_of_domain_queries:
        res = InputGuardrails.validate_domain_scope(q)
        assert res["is_in_domain"] is False, f"Expected {q} to be recognized as OUT OF DOMAIN"
        assert res["boundary_prompt"] is not None

        # Verify through full agent pipeline
        req = TextQueryRequest(baby_id="baby_liam_01", text=q)
        resp = process_text_query(req)
        assert resp.intent == "OUT_OF_DOMAIN"
        assert "Clinical Scope Boundary" in resp.text_card or "strictly dedicated" in resp.text_card


def test_in_domain_clinical_queries_allowed():
    in_domain_queries = [
        "How much milk should baby Liam drink?",
        "When will be the next kmc session?",
        "Liam has cold hands and is shivering",
        "What are the signs of neonatal jaundice?",
        "How do I clean and sterilize feeding bottles?",
    ]
    for q in in_domain_queries:
        res = InputGuardrails.validate_domain_scope(q)
        assert res["is_in_domain"] is True, f"Expected {q} to be recognized as IN DOMAIN"


def test_kmc_timeline_completion_message():
    ts = TimelineService()
    res = ts.get_next_kmc_task("baby_liam_01")
    assert "headline" in res
    assert "actionable_guidance" in res
    # Should not report a past completed time as next session
    assert "(COMPLETED)" not in res["headline"]


def test_quality_gated_caching_blocks_out_of_domain():
    from app.services.cache_service import cache_service
    cache_service.clear()

    req = TextQueryRequest(baby_id="baby_liam_01", text="Write Python code for web scraping")
    resp = process_text_query(req)
    assert resp.intent == "OUT_OF_DOMAIN"

    # Verify out of domain query is NOT cached
    cached = cache_service.get("Write Python code for web scraping")
    assert cached is None, "Out-of-domain response must NEVER be stored in semantic cache"


def test_neo4j_connection_status_available():
    status = graph_rag_service.get_connection_status()
    assert "status" in status
    assert "provider" in status
    assert status["total_nodes"] > 0
