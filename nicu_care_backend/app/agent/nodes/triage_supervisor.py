"""
Node 1: Triage Supervisor
Gatekeeper agent. Evaluates urgency with Layer 1 Input Guardrails, Model Routing,
and Jev Decision Engine, then routes to specialized subagents and MCP Gateway.
"""

from typing import Dict, Any
from ..state import NICUAgentState
from ..guardrails.input_guardrails import InputGuardrails
from ..jev_service import JevDecisionEngine
from ...services.llm_service import llm_service
from ...services.neonatal_bert_service import neonatal_bert_service
from ..nlp.query_understanding import query_understanding_engine

jev = JevDecisionEngine()


def triage_supervisor_node(state: NICUAgentState) -> Dict[str, Any]:
    trace_id = state.get("trace_id")
    parent_span_id = state.get("parent_span_id")
    triage_span = None
    if trace_id and parent_span_id:
        from ...telemetry.tracer import tracer
        triage_span = tracer.start_span("agent.langgraph.triage", trace_id=trace_id, parent_span_id=parent_span_id)

    def _return_with_span(res: Dict[str, Any]) -> Dict[str, Any]:
        if triage_span:
            from ...telemetry.tracer import tracer
            tracer.end_span(triage_span, status="OK")
        return res

    raw_query = state.get("raw_query", "")

    # 1. Comprehensive Input Guardrails Suite (Length, PHI Masking, Emergency, Harmful Practices, Scope)
    guard_res = InputGuardrails.run_all_input_guardrails(raw_query)

    if not guard_res["passed"]:
        # Check if query was rejected as out-of-domain scope
        if guard_res.get("is_out_of_domain"):
            boundary_text = guard_res.get("out_of_domain_prompt")
            return _return_with_span({
                "input_guardrail_passed": False,
                "input_guardrail_notes": "Out of domain query blocked by Layer 1 Input Guardrail",
                "intent": "OUT_OF_DOMAIN",
                "urgency": "INFORMATIONAL",
                "is_emergency": False,
                "emergency_probability": 0.0,
                "draft_response": boundary_text,
                "voice_summary": "I am specialized only for NICU post-discharge baby care. That inquiry is outside my clinical scope.",
                "selected_model": "deterministic_boundary_block",
                "safety_approved": True,
                "output_guardrail_passed": True,
                "final_text_card": boundary_text,
                "final_voice_summary": "I am specialized only for NICU post-discharge baby care. That inquiry is outside my clinical scope.",
            })

        # Query invalid (e.g. empty or over max characters)
        return _return_with_span({
            "input_guardrail_passed": False,
            "input_guardrail_notes": guard_res.get("reason"),
            "intent": "CLINICAL_QA",
            "urgency": "INFORMATIONAL",
            "is_emergency": False,
            "emergency_probability": 0.0,
            "draft_response": f"I couldn't process your request: {guard_res.get('reason')}",
            "voice_summary": "I could not process your request due to an input validation error.",
            "selected_model": "deterministic_fallback"
        })

    # 2. Deterministic Layer 1 Emergency Scan
    if guard_res["is_emergency"]:
        return _return_with_span({
            "input_guardrail_passed": True,
            "input_guardrail_notes": f"Acute red-flag signs detected: {guard_res['matched_indicators']}",
            "intent": "EMERGENCY",
            "urgency": "EMERGENCY",
            "is_emergency": True,
            "emergency_probability": 0.99,
            "draft_response": guard_res["emergency_prompt"],
            "voice_summary": "Please call your hospital's NICU emergency line immediately. These symptoms require prompt medical evaluation.",
            "selected_model": "deterministic_emergency_bypass"
        })

    # 2.5. NeonatalBERT Deep Phenotype & Urgency Transformer Scan (<15ms)
    bert_analysis = neonatal_bert_service.analyze_query(raw_query)
    if bert_analysis.urgency_score >= 0.90:
        phenotypes_str = ", ".join([e.raw_span for e in bert_analysis.detected_entities if e.entity_type == "PHENOTYPE"]) or "Acute neonatal distress signs"
        return _return_with_span({
            "input_guardrail_passed": True,
            "input_guardrail_notes": f"NeonatalBERT detected acute red flags ({bert_analysis.urgency_score:.2f}): {phenotypes_str}",
            "intent": "EMERGENCY",
            "urgency": "EMERGENCY",
            "is_emergency": True,
            "emergency_probability": bert_analysis.urgency_score,
            "draft_response": (
                "⚠️ URGENT CLINICAL ATTENTION NEEDED\n\n"
                f"Neonatal danger signs detected ({phenotypes_str}). Please call your hospital NICU helpline (+91 866 669 0000) or dial 108 immediately."
            ),
            "voice_summary": "Please call your hospital emergency line immediately. These symptoms require prompt evaluation.",
            "selected_model": "neonatal_bert_transformer_fastpath"
        })

    # 3. Jev Probabilistic Decision Engine
    noul = jev.evaluate_emergency_noul(raw_query)
    if noul.value:
        return _return_with_span({
            "input_guardrail_passed": True,
            "input_guardrail_notes": "Jev emergency probability threshold exceeded",
            "intent": "EMERGENCY",
            "urgency": "EMERGENCY",
            "is_emergency": True,
            "emergency_probability": noul.probability,
            "draft_response": (
                "⚠️ URGENT CLINICAL ATTENTION NEEDED\n\n"
                "Acute neonatal danger signs detected. Please contact your hospital emergency team or call 108/911 immediately."
            ),
            "voice_summary": "Please call your hospital emergency line right away.",
            "selected_model": "typesafe_jev_noul"
        })

    # 4. Multi-Intent Semantic Understanding (Disambiguating questions vs logs & concept expansion)
    nlu_res = query_understanding_engine.understand_query(raw_query)
    intent = nlu_res.intent
    urgency = "ROUTINE" if intent.startswith("LOG_") else "INFORMATIONAL"

    # 5. Model Routing
    requested_model = state.get("requested_model") or state.get("selected_model")
    routed_model = requested_model or llm_service.get_routed_model("intent_classification")

    return _return_with_span({
        "input_guardrail_passed": True,
        "input_guardrail_notes": f"NLU routed to {intent} (confidence {nlu_res.confidence:.2f})",
        "intent": intent,
        "urgency": urgency,
        "is_emergency": False,
        "emergency_probability": noul.probability,
        "clinical_entities": nlu_res.clinical_entities,
        "expanded_medical_terms": nlu_res.expanded_medical_terms,
        "selected_model": routed_model,
        "requested_model": requested_model,
        "retry_count": 0,
        "loop_iteration": 0,
    })
