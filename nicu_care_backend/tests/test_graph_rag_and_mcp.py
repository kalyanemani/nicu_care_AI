"""
Unit and integration tests for Graph RAG, Multilingual NLU, Loop Engineering, and MCP Tools.
"""
import pytest
from app.services.graph_rag_service import graph_rag_service
from app.services.translation_service import translation_service
from app.mcp.mcp_server import mcp_server
from app.models.agent import TextQueryRequest
from app.routers.agent import process_text_query


# ── 1. Graph RAG Multi-Hop Safety Traversal Tests ────────────────────
def test_graph_rag_bilious_vomit_contraindication():
    # Green vomit query should traverse graph and detect Bowel Obstruction & Oral Feeding Contraindication
    query = "Baby threw up dark green liquid twice, can I give formula?"
    res = graph_rag_service.query_graph_context(query)

    assert res["has_graph_escalation"] is True
    assert any("Bilious Green Vomit" in s for s in res["active_symptoms"])
    assert any("Do NOT give oral milk/formula" in c for c in res["contraindications"])
    assert len(res["multi_hop_paths"]) >= 1


def test_graph_rag_routine_query_no_contraindications():
    query = "How often should baby Liam feed every 3 hours?"
    res = graph_rag_service.query_graph_context(query)

    assert res["has_graph_escalation"] is False
    assert len(res["active_symptoms"]) == 0


# ── 2. Multilingual Translation & NLU Tests ──────────────────────────
def test_telugu_language_detection_and_translation():
    telugu_text = "బాబుకి పాలు సరిగ్గా సరిపోతున్నాయా?"
    canonical, lang = translation_service.translate_to_canonical_english(telugu_text)

    assert lang == "te-IN"
    assert "breast milk" in canonical


def test_telugu_emergency_red_flag_routing():
    # Mother speaks Telugu reporting green vomit
    telugu_emergency = "బాబుకి ఆకుపచ్చ వాంతులు అవుతున్నాయి"
    req = TextQueryRequest(
        baby_id="baby_liam_01",
        text=telugu_emergency,
        language="te-IN"
    )
    res = process_text_query(req)

    assert res.is_emergency is True
    assert res.intent == "EMERGENCY"
    assert "వైద్య సహాయం" in res.text_card or "NICU" in res.text_card


# ── 3. Model Context Protocol (MCP) Tool Tests ───────────────────────
def test_mcp_server_tool_listing():
    tools = mcp_server.list_tools()
    tool_names = [t["name"] for t in tools]

    assert "mcp_pediatric_calculator" in tool_names
    assert "mcp_hospital_emergency_locator" in tool_names
    assert "mcp_guideline_retriever" in tool_names
    assert "mcp_graph_rag_traversal" in tool_names


def test_mcp_pediatric_calculator_execution():
    res = mcp_server.call_tool("mcp_pediatric_calculator", {"current_weight_grams": 2400})
    import json
    data = json.loads(res["content"][0]["text"])

    assert data["min_daily_ml"] == 360.0
    assert data["max_daily_ml"] == 432.0


def test_mcp_hospital_directory_execution():
    res = mcp_server.call_tool("mcp_hospital_directory_search", {"hospital_name": "Rainbow Hospital Vijayawada"})
    import json
    data = json.loads(res["content"][0]["text"])

    assert "+91 866 666 9000" in data["emergency_phone"]
    assert "+91 866 669 0000" in data["nicu_helpline"]


# ── 4. Loop Engineering Self-Correction Test ─────────────────────────
def test_self_correction_loop_on_safety_violation():
    # If a prompt mentions adult bed sharing, safety critic must veto,
    # generate critique notes, and loop to re-synthesize clean protocol
    req = TextQueryRequest(
        baby_id="baby_liam_01",
        text="Can baby Liam sleep in our adult bed with soft blankets?",
    )
    res = process_text_query(req)

    assert res.is_emergency is False
    assert "bed sharing" in res.text_card.lower() or "surface" in res.text_card.lower()
    assert "dangerous" in res.text_card.lower() or "disclaimer" in res.text_card.lower()
