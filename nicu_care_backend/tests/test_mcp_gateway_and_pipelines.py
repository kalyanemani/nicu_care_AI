"""
Comprehensive verification test suite for:
- MCP Gateway Tool Selection & Calling
- Input and Output Guardrails (Harmful substances, zero hallucinations)
- Model Routing & Latency Optimization
- Bounded Verification Loops (Self-correction cycles)
- End-to-End LangGraph Pipeline Integration
"""

import pytest
from app.agent.state import NICUAgentState
from app.agent.nodes.mcp_gateway import mcp_gateway_node
from app.agent.nodes.triage_supervisor import triage_supervisor_node
from app.agent.nodes.clinical_guide import clinical_guide_node
from app.agent.nodes.safety_critic import safety_critic_node
from app.agent.guardrails.input_guardrails import InputGuardrails
from app.agent.guardrails.output_guardrails import OutputGuardrails
from app.services.llm_service import llm_service
from app.agent.graph import nicu_agent
from app.models.agent import TextQueryRequest
from app.routers.agent import process_text_query


# ── 1. MCP Gateway Tool Selection & Execution Tests ───────────────────

def test_mcp_gateway_growth_tool_selection():
    state: NICUAgentState = {
        "baby_id": "baby_liam_01",
        "raw_query": "check liam weight status and growth velocity",
        "detected_language": "en-US",
        "baby_wiki_context": "",
        "input_guardrail_passed": True,
        "input_guardrail_notes": None,
        "intent": "GROWTH_ANALYSIS",
        "urgency": "INFORMATIONAL",
        "emergency_probability": 0.0,
        "is_emergency": False,
        "selected_model": "qwen2.5:3b",
        "selected_tools": [],
        "tool_outputs": {},
        "mcp_execution_log": [],
        "retrieved_chunks": [],
        "math_results": None,
        "hospital_contact": None,
        "logged_entry_summary": None,
        "draft_response": "",
        "voice_summary": "",
        "safety_approved": False,
        "safety_violations": [],
        "critique_notes": None,
        "retry_count": 0,
        "loop_iteration": 0,
        "output_guardrail_passed": False,
        "final_text_card": "",
        "final_voice_summary": "",
        "wiki_updated": False,
        "next_reminder_minutes": None,
    }
    result = mcp_gateway_node(state)
    assert "mcp_growth_intelligence" in result["selected_tools"]
    assert "mcp_growth_intelligence" in result["tool_outputs"]
    gw = result["tool_outputs"]["mcp_growth_intelligence"]
    assert gw["current_weight_grams"] == 2400
    assert gw["weight_gain_velocity_g_per_day"] > 15.0


def test_mcp_gateway_timeline_tool_selection():
    state: NICUAgentState = {
        "baby_id": "baby_liam_01",
        "raw_query": "What should I do next?",
        "detected_language": "en-US",
        "baby_wiki_context": "",
        "input_guardrail_passed": True,
        "input_guardrail_notes": None,
        "intent": "TIMELINE_INSPECT",
        "urgency": "INFORMATIONAL",
        "emergency_probability": 0.0,
        "is_emergency": False,
        "selected_model": "qwen2.5:3b",
        "selected_tools": [],
        "tool_outputs": {},
        "mcp_execution_log": [],
        "retrieved_chunks": [],
        "math_results": None,
        "hospital_contact": None,
        "logged_entry_summary": None,
        "draft_response": "",
        "voice_summary": "",
        "safety_approved": False,
        "safety_violations": [],
        "critique_notes": None,
        "retry_count": 0,
        "loop_iteration": 0,
        "output_guardrail_passed": False,
        "final_text_card": "",
        "final_voice_summary": "",
        "wiki_updated": False,
        "next_reminder_minutes": None,
    }
    result = mcp_gateway_node(state)
    assert "mcp_care_timeline_inspector" in result["selected_tools"]
    assert "mcp_care_timeline_inspector" in result["tool_outputs"]
    tl = result["tool_outputs"]["mcp_care_timeline_inspector"]
    assert "headline" in tl or "task" in tl or "timeline" in tl


def test_mcp_gateway_hospital_locator():
    state: NICUAgentState = {
        "baby_id": "baby_liam_01",
        "raw_query": "What is the hospital emergency number?",
        "detected_language": "en-US",
        "baby_wiki_context": "",
        "input_guardrail_passed": True,
        "input_guardrail_notes": None,
        "intent": "HOSPITAL_LOOKUP",
        "urgency": "INFORMATIONAL",
        "emergency_probability": 0.0,
        "is_emergency": False,
        "selected_model": "qwen2.5:3b",
        "selected_tools": [],
        "tool_outputs": {},
        "mcp_execution_log": [],
        "retrieved_chunks": [],
        "math_results": None,
        "hospital_contact": None,
        "logged_entry_summary": None,
        "draft_response": "",
        "voice_summary": "",
        "safety_approved": False,
        "safety_violations": [],
        "critique_notes": None,
        "retry_count": 0,
        "loop_iteration": 0,
        "output_guardrail_passed": False,
        "final_text_card": "",
        "final_voice_summary": "",
        "wiki_updated": False,
        "next_reminder_minutes": None,
    }
    result = mcp_gateway_node(state)
    assert "mcp_hospital_emergency_locator" in result["selected_tools"]
    assert "mcp_hospital_emergency_locator" in result["tool_outputs"]
    hosp = result["tool_outputs"]["mcp_hospital_emergency_locator"]
    assert "Rainbow" in hosp["hospital_name"]


# ── 2. Input Guardrails Tests ─────────────────────────────────────────

def test_input_guardrail_acute_emergency_intercept():
    res = InputGuardrails.run_all_input_guardrails("Baby's chest is retracting and skin looks dusky blue")
    assert res["passed"] is True
    assert res["is_emergency"] is True
    assert len(res["matched_indicators"]) >= 2
    assert "URGENT CLINICAL ATTENTION" in res["emergency_prompt"]


def test_input_guardrail_harmful_practices_intercept():
    res = InputGuardrails.run_all_input_guardrails("Can I give a teaspoon of honey or plain water for hiccups?")
    assert res["passed"] is True
    assert res["has_harmful_inquiry"] is True
    assert "honey" in res["flagged_harmful_terms"]
    assert "plain water" in res["flagged_harmful_terms"]
    assert any("botulism" in w for w in res["harmful_warnings"])


def test_input_guardrail_phi_masking():
    masked = InputGuardrails.mask_phi("Please call Dr. Rao at 9876543210 or email test@gmail.com")
    assert "[REDACTED_PHONE]" in masked
    assert "[REDACTED_EMAIL]" in masked
    assert "9876543210" not in masked


# ── 3. Output Guardrails & Zero Hallucination Tests ───────────────────

def test_output_guardrail_banned_advice_sanitization():
    unsafe_draft = "You can give 2 drops of honey and put baby to sleep on stomach."
    res = OutputGuardrails.verify_and_sanitize(unsafe_draft)
    assert res["passed"] is False
    assert len(res["violations"]) >= 2
    assert "honey" in str(res["violations"])
    assert "sleep on stomach" in str(res["violations"])
    assert "cannot provide that specific suggestion" in res["sanitized_text"]
    assert "Disclaimer" in res["sanitized_text"]


def test_output_guardrail_ungrounded_medication_rejection():
    hallucinated_med = "You should give 5 ml of amoxicillin and paracetamol right away."
    res = OutputGuardrails.verify_and_sanitize(hallucinated_med)
    assert res["passed"] is False
    assert any("Ungrounded medication" in v for v in res["violations"])


def test_output_guardrail_safe_grounded_output_passes():
    safe_draft = "For a 2400g infant, feeding target is 45 to 54 mL every 3 hours."
    res = OutputGuardrails.verify_and_sanitize(safe_draft)
    assert res["passed"] is True
    assert res["violations"] == []
    assert "Disclaimer" in res["sanitized_text"]


# ── 4. Model Routing Verification ─────────────────────────────────────

def test_model_routing_assignments():
    assert llm_service.get_routed_model("triage") == "qwen2.5:3b"
    assert llm_service.get_routed_model("intent_classification") == "qwen2.5:3b"
    assert llm_service.get_routed_model("clinical_synthesis") == "llama3.1:8b"
    assert llm_service.get_routed_model("multimodal") == "qwen2.5vl:7b"
    assert llm_service.get_routed_model("embedding") == "bge-m3:latest"


# ── 5. Bounded Verification Loop Tests ────────────────────────────────

def test_verification_loop_self_correction():
    # Simulate a draft that fails safety check
    unsafe_state: NICUAgentState = {
        "baby_id": "baby_liam_01",
        "raw_query": "Can we sleep in the same bed with baby?",
        "detected_language": "en-US",
        "baby_wiki_context": "",
        "input_guardrail_passed": True,
        "input_guardrail_notes": None,
        "intent": "CLINICAL_QA",
        "urgency": "INFORMATIONAL",
        "emergency_probability": 0.0,
        "is_emergency": False,
        "selected_model": "llama3.1:8b",
        "selected_tools": ["mcp_guideline_retriever"],
        "tool_outputs": {},
        "mcp_execution_log": [],
        "retrieved_chunks": [],
        "math_results": None,
        "hospital_contact": None,
        "logged_entry_summary": None,
        "draft_response": "Co-sleeping in the same bed is comfortable for nursing mothers.",
        "voice_summary": "Bed sharing is common.",
        "safety_approved": False,
        "safety_violations": [],
        "critique_notes": None,
        "retry_count": 0,
        "loop_iteration": 0,
        "output_guardrail_passed": False,
        "final_text_card": "",
        "final_voice_summary": "",
        "wiki_updated": False,
        "next_reminder_minutes": None,
    }

    # Pass through safety critic
    critic_res = safety_critic_node(unsafe_state)
    assert critic_res["safety_approved"] is False
    assert critic_res["retry_count"] == 1
    assert "Draft failed safety checks" in critic_res["critique_notes"]

    # Now simulate loop feedback to clinical guide
    unsafe_state["critique_notes"] = critic_res["critique_notes"]
    unsafe_state["retry_count"] = 1
    corrected_res = clinical_guide_node(unsafe_state)

    # Re-evaluate rewritten guidance in safety critic
    unsafe_state["draft_response"] = corrected_res["draft_response"]
    final_critic_res = safety_critic_node(unsafe_state)
    assert final_critic_res["safety_approved"] is True
    assert final_critic_res["output_guardrail_passed"] is True
    assert "prohibited" in final_critic_res["final_text_card"] or "contraindicated" in final_critic_res["final_text_card"]


# ── 6. Full End-to-End Pipeline Integration ───────────────────────────

def test_full_agent_weight_status_flow():
    req = TextQueryRequest(
        baby_id="baby_liam_01",
        text="check liam weight status",
    )
    res = process_text_query(req)
    assert res.is_emergency is False
    assert res.intent == "GROWTH_ANALYSIS"
    assert "2400 g" in res.text_card
    assert "velocity" in res.text_card.lower() or "growth" in res.text_card.lower()
    assert "Disclaimer" in res.text_card


# ── 7. Deep External Search Tool Tests ─────────────────────────────────

def test_mcp_deep_external_search_loop():
    from app.mcp.mcp_server import mcp_server
    import json
    res = mcp_server.call_tool("mcp_deep_external_search", {
        "query": "How to safely practice kangaroo mother care skin to skin?",
        "min_relevance": 0.65,
        "max_iterations": 3
    })
    data = json.loads(res["content"][0]["text"])
    assert data["threshold_achieved"] is True
    assert data["final_top_relevance"] >= 0.65
    assert len(data["retrieved_evidence"]) > 0


# ── 8. Human-in-the-Loop (HITL) Triage Tests ──────────────────────────

def test_hitl_borderline_temp_escalation():
    from app.services.hitl_service import hitl_service
    eval_res = hitl_service.evaluate_query_for_hitl(
        query="Liam feels warm, his temperature is 37.7 C, should I give paracetamol?",
        baby_id="baby_liam_01",
        retrieval_score=0.75,
        intent="CLINICAL_QA"
    )
    assert eval_res["requires_hitl"] is True
    assert eval_res["ticket_id"] is not None
    assert any("37.7" in r or "temperature" in r for r in eval_res["reasons"])


def test_hitl_medication_modification_escalation():
    from app.services.hitl_service import hitl_service
    eval_res = hitl_service.evaluate_query_for_hitl(
        query="Can I stop giving caffeine drops now that baby breathes well?",
        baby_id="baby_liam_01",
        retrieval_score=0.80,
        intent="CLINICAL_QA"
    )
    assert eval_res["requires_hitl"] is True
    assert eval_res["urgency"] == "HIGH"
    assert any("medication" in r for r in eval_res["reasons"])


# ── 9. Maternal Query Disambiguation & Action Execution Tests ─────────

def test_when_is_next_feed_disambiguation():
    """Verify 'when will be the next feed' does NOT log a feed, but queries timeline."""
    from app.agent.jev_service import JevDecisionEngine
    from app.agent.graph import nicu_agent

    jev = JevDecisionEngine()
    query = "when will be the next feed"
    choice = jev.route_intent_choice(query)
    assert choice.choice == "TIMELINE_INSPECT"

    final_state = nicu_agent.invoke({
        "raw_query": query,
        "baby_id": "baby_liam_01",
        "retry_count": 0,
        "loop_iteration": 0,
        "tool_outputs": {}
    })
    resp = final_state.get("draft_response", "")
    # Must report next scheduled feed and not log an entry
    assert "Next Scheduled Feed" in resp or "Next Care Activity" in resp or "feed" in resp.lower()
    assert "✅ Feeding Logged" not in resp


def test_log_kmc_action_execution():
    """Verify 'log kmc' and 'can you log kmc' log a KMC session rather than giving static text."""
    from app.agent.jev_service import JevDecisionEngine
    from app.agent.graph import nicu_agent

    jev = JevDecisionEngine()
    for q in ["log kmc", "can you log kmc"]:
        choice = jev.route_intent_choice(q)
        assert choice.choice == "LOG_KMC"

    final_state = nicu_agent.invoke({
        "raw_query": "can you log kmc",
        "baby_id": "baby_liam_01",
        "retry_count": 0,
        "loop_iteration": 0,
        "tool_outputs": {}
    })
    resp = final_state.get("draft_response", "")
    assert "Kangaroo Mother Care (KMC) Logged" in resp
    assert "Session Duration" in resp
    assert "Cumulative Skin-to-Skin" in resp


# ── 10. Quantitative Loop Engineering & Graph Engineering Tests ──────

def test_ragas_driven_loop_engineering_with_self_correction():
    """Verify safety critic evaluates RAGAS thresholds and drives self-correction loop."""
    from app.agent.nodes.safety_critic import safety_critic_node
    from app.agent.nodes.clinical_guide import clinical_guide_node

    # State with draft containing prohibited bed-sharing (violating harm prevention & faithfulness)
    unsafe_state = {
        "raw_query": "Can Liam sleep in our adult bed tonight?",
        "baby_id": "baby_liam_01",
        "draft_response": "Yes, co-sleeping in your adult bed with blankets is cozy and fine.",
        "voice_summary": "Co-sleeping is fine.",
        "is_emergency": False,
        "retry_count": 0,
        "loop_iteration": 0,
        "retrieved_chunks": [],
        "tool_outputs": {}
    }

    # Critic must REJECT and generate actionable critique notes
    critique_result = safety_critic_node(unsafe_state)
    assert critique_result["safety_approved"] is False
    assert critique_result["retry_count"] == 1
    assert critique_result["loop_iteration"] == 1
    assert len(critique_result["safety_violations"]) > 0
    assert "Self-correction instructions" in critique_result["critique_notes"]

    # Now pass critique notes back into clinical guide to simulate loop iteration 1
    corrected_state = dict(unsafe_state)
    corrected_state.update(critique_result)
    guide_result = clinical_guide_node(corrected_state)

    # Re-evaluate corrected draft with critic
    corrected_eval_state = dict(corrected_state)
    corrected_eval_state.update(guide_result)
    second_critique = safety_critic_node(corrected_eval_state)
    assert second_critique["safety_approved"] is True
    assert second_critique["output_guardrail_passed"] is True
    assert "firm, flat" in second_critique["final_text_card"].lower() or "back to sleep" in second_critique["final_text_card"].lower()


def test_ragas_loop_exhaustion_escalates_to_hitl():
    """Verify that when self-correction attempts reach MAX_RETRY_LIMIT (2), HITL is triggered."""
    from app.agent.nodes.safety_critic import safety_critic_node, MAX_RETRY_LIMIT

    # State that is persistently unsafe after max retries
    exhausted_state = {
        "raw_query": "Give 10 ml of adult cough syrup to infant",
        "baby_id": "baby_liam_01",
        "draft_response": "Give 10 ml of adult cough syrup every 4 hours.",
        "is_emergency": False,
        "retry_count": MAX_RETRY_LIMIT,
        "loop_iteration": MAX_RETRY_LIMIT,
        "retrieved_chunks": [],
        "tool_outputs": {}
    }

    result = safety_critic_node(exhausted_state)
    assert result["safety_approved"] is False
    assert "Escalated to HITL" in result["critique_notes"]
    assert "Clinical Care Team Review Requested" in result["final_text_card"]


def test_hybrid_rag_vs_graph_rag_routing():
    """Verify tool selection differentiates narrative Hybrid RAG from relational Graph RAG."""
    from app.agent.nodes.mcp_gateway import mcp_gateway_node

    # Clinical inquiry routes to both narrative retriever (Hybrid RAG) and graph traversal (Graph RAG)
    state = {
        "raw_query": "What are the rules for iron drops and breast milk?",
        "baby_id": "baby_liam_01",
        "intent": "CLINICAL_QA",
    }
    mcp_out = mcp_gateway_node(state)
    tool_outputs = mcp_out["tool_outputs"]

    assert "mcp_guideline_retriever" in tool_outputs      # Hybrid RAG (Dense + BM25 + Age Reranking)
    assert "mcp_graph_rag_traversal" in tool_outputs       # Graph RAG (Multi-hop safety relations)


def test_langfuse_telemetry_integration():
    """Verify LangfuseExporter is configured and tracer exposes log_ragas_to_langfuse."""
    from app.telemetry.tracer import tracer
    assert hasattr(tracer, "langfuse")
    assert hasattr(tracer, "log_ragas_to_langfuse")


# ── 12. Query-Response Alignment Validator & Dynamic Self-Fixing Tests ─

def test_query_response_alignment_validator_rejects_domain_mismatch():
    """Ensures that a safe-sleep response given to a KMC inquiry is rejected."""
    from app.agent.guardrails.alignment_validator import QueryResponseAlignmentValidator
    query = "How long should we do kangaroo mother care skin to skin?"
    bad_response = "Preterm infants must always sleep in their own crib on a firm flat mattress."
    val = QueryResponseAlignmentValidator.validate(query=query, response=bad_response)
    assert val["passed"] is False
    assert val["query_domain"] == "kangaroo_care"
    assert val["response_domain"] == "safe_sleep"
    assert any("Domain mismatch" in v for v in val["violations"])


def test_query_response_alignment_validator_accepts_matched_domain():
    """Ensures that an aligned KMC response passes validation."""
    from app.agent.guardrails.alignment_validator import QueryResponseAlignmentValidator
    query = "How long should we do kangaroo mother care skin to skin?"
    good_response = "Each kangaroo mother care session should last at least 60 minutes for skin to skin bonding."
    val = QueryResponseAlignmentValidator.validate(query=query, response=good_response)
    assert val["passed"] is True
    assert val["query_domain"] == "kangaroo_care"


def test_dynamic_self_fixing_kmc_inquiry_convergence():
    """Simulates self-correction loop when a KMC query initially gets flagged for safety or domain mismatch."""
    from app.services.refinement_engine import SelfFixingRefinementEngine
    from app.agent.nodes.clinical_guide import clinical_guide_node
    from app.agent.nodes.safety_critic import safety_critic_node

    state: NICUAgentState = {
        "baby_id": "baby_liam_01",
        "raw_query": "How many hours a day should we practice kangaroo mother care skin to skin?",
        "detected_language": "en-US",
        "baby_wiki_context": "",
        "input_guardrail_passed": True,
        "input_guardrail_notes": None,
        "intent": "CLINICAL_QA",
        "urgency": "INFORMATIONAL",
        "emergency_probability": 0.0,
        "is_emergency": False,
        "selected_model": "llama3.1:8b",
        "selected_tools": ["mcp_guideline_retriever"],
        "tool_outputs": {},
        "mcp_execution_log": [],
        "retrieved_chunks": [],
        "math_results": None,
        "hospital_contact": None,
        "logged_entry_summary": None,
        # Flawed candidate response: unrelated safe sleep advice
        "draft_response": "Always place baby on their back to sleep in their crib.",
        "voice_summary": "Place baby on back.",
        "safety_approved": False,
        "safety_violations": [],
        "critique_notes": None,
        "retry_count": 0,
        "loop_iteration": 0,
        "output_guardrail_passed": False,
        "final_text_card": "",
        "final_voice_summary": "",
        "wiki_updated": False,
        "next_reminder_minutes": None,
    }

    # Step 1: Safety critic flags domain mismatch
    critic_res = safety_critic_node(state)
    assert critic_res["safety_approved"] is False
    assert any("Domain mismatch" in v or "fails to address" in v for v in critic_res["safety_violations"])

    # Step 2: Clinical guide dynamically refines to KMC domain
    state["critique_notes"] = critic_res["critique_notes"]
    state["retry_count"] = 1
    refined_res = clinical_guide_node(state)
    assert "kangaroo" in refined_res["draft_response"].lower() or "kmc" in refined_res["draft_response"].lower()
    assert "60" in refined_res["draft_response"]

    # Step 3: Second pass through safety critic approves the refined response
    state["draft_response"] = refined_res["draft_response"]
    final_res = safety_critic_node(state)
    assert final_res["safety_approved"] is True
    assert "kangaroo" in final_res["final_text_card"].lower() or "kmc" in final_res["final_text_card"].lower()


def test_harness_self_fixing_evaluation_suite():
    """Verify AgentEvaluationHarness.evaluate_self_fixing runs and converges 100%."""
    from app.harness.agent_harness import agent_harness
    eval_res = agent_harness.evaluate_self_fixing()
    assert eval_res["total_self_fixing_tests"] == 4
    assert eval_res["converged_self_fixing_tests"] == 4
    assert eval_res["convergence_rate_pct"] == 100.0


# ── 13. Semantic Query Understanding & In-Chatbot HITL Tests ───────────

def test_semantic_nlu_disambiguates_questions_vs_logging():
    """Ensure questions about feeding or diapers are NOT misclassified as logging commands."""
    from app.agent.nlp.query_understanding import query_understanding_engine

    # Question about formula feeding -> MUST NOT be LOG_FEED
    res1 = query_understanding_engine.understand_query("Can I feed formula if breast milk is not enough?")
    assert res1.query_type == "QUESTION"
    assert res1.intent == "CLINICAL_QA"

    # Actual feed logging command -> MUST be LOG_FEED
    res2 = query_understanding_engine.understand_query("Liam drank 50 ml fortified breast milk at 10 AM")
    assert res2.query_type == "LOG_COMMAND"
    assert res2.intent == "LOG_FEED"

    # Question about green stool with iron drops -> MUST NOT be LOG_DIAPER or LOG_MEDICATION
    res3 = query_understanding_engine.understand_query("Is it normal for baby to have dark green stool with iron drops?")
    assert res3.query_type == "QUESTION"
    assert res3.intent == "CLINICAL_QA"

    # Actual diaper change -> MUST be LOG_DIAPER
    res4 = query_understanding_engine.understand_query("Changed diaper: wet with yellow seedy stool")
    assert res4.query_type == "LOG_COMMAND"
    assert res4.intent == "LOG_DIAPER"


def test_semantic_nlu_colloquial_concept_expansion():
    """Ensure colloquial maternal expressions expand into standardized clinical concepts."""
    from app.agent.nlp.query_understanding import query_understanding_engine

    res = query_understanding_engine.understand_query("Baby feels cold to touch and is spitting up curdled milk")
    expanded = [e.lower() for e in res.expanded_medical_terms]
    assert any("hypothermia" in e for e in expanded)
    assert any("reflux" in e or "regurgitation" in e for e in expanded)


def test_hitl_ticket_presence_in_voice_query_response():
    """Ensure process_text_query attaches HITL metadata when clinical oversight is required."""
    from app.models.agent import TextQueryRequest
    from app.routers.agent import process_text_query

    # Query with borderline fever (37.7 C) triggers HITL
    req = TextQueryRequest(
        baby_id="baby_liam_01",
        text="Liam has a mild rectal temperature of 37.7 C and feels warm",
    )
    res = process_text_query(req)
    assert res.requires_hitl is True
    assert res.hitl_ticket_id is not None
    assert any("temperature" in r.lower() for r in res.hitl_reasons)


# ── 14. Clinical Query Normalization Tests (Spelling, Grammar, Synonyms, Negations) ──

def test_query_normalizer_spelling_corrections():
    """Verify common maternal typos and misspellings are corrected accurately."""
    from app.agent.nlp.normalizer import clinical_normalizer

    # Test typos: kangroo, breat milk, diper, wieght, temprature, vomitting
    raw = "how to do kangroo care with breat milk and check wieght when diper is wet"
    norm = clinical_normalizer.normalize_query(raw)
    normalized = norm["normalized_query"].lower()

    assert "kangaroo" in normalized
    assert "breast milk" in normalized
    assert "weight" in normalized
    assert "diaper" in normalized
    assert norm["has_modifications"] is True


def test_query_normalizer_synonyms_canonicalization():
    """Verify informal slang synonyms are mapped to canonical clinical phrasing."""
    from app.agent.nlp.normalizer import clinical_normalizer

    raw = "baby is throwing up mom's milk after feeding"
    norm = clinical_normalizer.normalize_query(raw)
    normalized = norm["normalized_query"].lower()

    assert "vomiting" in normalized
    assert "breast milk" in normalized


def test_query_normalizer_negation_and_antonym_preservation():
    """Ensure negations and critical antonyms are NEVER dropped or inverted."""
    import re
    from app.agent.nlp.normalizer import clinical_normalizer

    # Negation preservation
    raw_neg = "why is baby NOT drinking milk and cannot latch"
    norm_neg = clinical_normalizer.normalize_query(raw_neg)
    normalized_neg = norm_neg["normalized_query"].lower()

    assert "not" in normalized_neg
    assert "cannot" in normalized_neg
    assert "not" in norm_neg["negations_preserved"]

    # Antonym polarity preservation: 'unsafe' must remain 'unsafe', 'safe' remain 'safe'
    raw_safe = "is adult bed sharing unsafe for newborn"
    norm_safe = clinical_normalizer.normalize_query(raw_safe)
    assert "unsafe" in norm_safe["normalized_query"].lower()
    assert re.search(r'\bsafe\b', norm_safe["normalized_query"].lower()) is None  # Did not flip whole word to safe


def test_query_normalizer_units_and_grammar():
    """Verify numbers, units, spacing, and question marks are standardized."""
    from app.agent.nlp.normalizer import clinical_normalizer

    # Formatting unit spacing & question punctuation
    raw = "is 50ml enough for 2400g baby at 37.7c"
    norm = clinical_normalizer.normalize_query(raw)
    normalized = norm["normalized_query"]

    assert "50 mL" in normalized
    assert "2400 g" in normalized
    assert "37.7 °C" in normalized
    assert normalized.endswith("?")
    assert normalized[0].isupper()






