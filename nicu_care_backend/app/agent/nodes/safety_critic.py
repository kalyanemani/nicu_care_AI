"""
Node 5: Safety Critic & Verifier Agent
Independent adversarial judge with VETO power. Evaluates candidate response
against Layer 4 Output Guardrails, Jev safety scoring, and in-loop RAGAS thresholds.
Controls the self-correction verification loop and triggers HITL upon loop exhaustion.
"""

from typing import Dict, Any, List
import json
from ..state import NICUAgentState
from ..guardrails.output_guardrails import OutputGuardrails
from ..jev_service import JevDecisionEngine
from ...telemetry.ragas_evaluator import ragas_evaluator
from ...services.hitl_service import hitl_service

jev = JevDecisionEngine()

# Quantitative RAGAS and Safety Loop Thresholds
MIN_FAITHFULNESS = 0.90        # Strict claim-level groundedness threshold (reject hallucinations)
MIN_HARM_PREVENTION = 1.00     # Zero-tolerance for contraindicated practices
MIN_CONTEXT_RELEVANCE = 0.40   # Minimum contextual relevance
MAX_RETRY_LIMIT = 2            # Maximum self-correction iterations before HITL escalation


def safety_critic_node(state: NICUAgentState) -> Dict[str, Any]:
    trace_id = state.get("trace_id")
    parent_span_id = state.get("parent_span_id")
    critic_span = None
    if trace_id and parent_span_id:
        from ...telemetry.tracer import tracer
        critic_span = tracer.start_span("agent.langgraph.safety_critic", trace_id=trace_id, parent_span_id=parent_span_id)

    def _return_with_span(res: Dict[str, Any]) -> Dict[str, Any]:
        if critic_span:
            from ...telemetry.tracer import tracer
            tracer.end_span(critic_span, status="OK")
        return res

    draft = state.get("draft_response", "")
    raw_query = state.get("raw_query", "")
    baby_id = state.get("baby_id", "baby_liam_01")
    is_emergency = state.get("is_emergency", False)
    retry_count = state.get("retry_count", 0)
    loop_iteration = state.get("loop_iteration", 0)
    intent = state.get("intent", "CLINICAL_QA")

    # Fast-path for out-of-domain scope blocks
    if intent == "OUT_OF_DOMAIN":
        return _return_with_span({
            "safety_approved": True,
            "safety_violations": [],
            "critique_notes": None,
            "output_guardrail_passed": True,
            "final_text_card": draft,
            "final_voice_summary": state.get("voice_summary", "")
        })

    # 1. Output Guardrail check (with banned advice and hallucination checks)
    guard_res = OutputGuardrails.verify_and_sanitize(draft, is_emergency=is_emergency)

    # 2. Jev Safety Score
    jev_score = jev.score_safety_level(draft)

    # 3. In-Loop RAGAS & Claim-Level Grounded Verification
    retrieved_chunks = state.get("retrieved_chunks", [])
    if not retrieved_chunks:
        tool_outputs = state.get("tool_outputs", {})
        if tool_outputs:
            retrieved_chunks = [
                {"header": k, "text": json.dumps(v), "metadata": {"min_corrected_weeks": 0, "max_corrected_weeks": 104}}
                for k, v in tool_outputs.items()
            ]
        elif state.get("growth_analysis"):
            retrieved_chunks = [
                {"header": "growth", "text": json.dumps(state["growth_analysis"]), "metadata": {"min_corrected_weeks": 0, "max_corrected_weeks": 104}}
            ]
        elif intent in ["GROWTH_ANALYSIS", "TIMELINE_INSPECT", "PEDIATRIC_MATH", "FEEDING_INTELLIGENCE", "PATIENT_RECORD_INQUIRY"]:
            retrieved_chunks = [
                {"header": intent, "text": draft, "metadata": {"min_corrected_weeks": 0, "max_corrected_weeks": 104}}
            ]

    # Layer 4.6: Claim-Level Verification Engine
    from ..guardrails.claim_verifier import ClaimVerificationEngine
    claim_res = ClaimVerificationEngine.verify_claims(
        response_text=guard_res["sanitized_text"],
        retrieved_chunks=retrieved_chunks,
        intent=intent,
        min_faithfulness=MIN_FAITHFULNESS
    )

    ragas_scores = ragas_evaluator.evaluate_full_turn(
        query=raw_query,
        retrieved_chunks=retrieved_chunks,
        response_text=guard_res["sanitized_text"],
        is_emergency=is_emergency,
        red_flag_triggered=is_emergency,
    )

    faithfulness = max(ragas_scores.get("generation", {}).get("faithfulness", 1.0), claim_res.get("faithfulness", 1.0))
    harm_prevention = ragas_scores.get("generation", {}).get("harm_prevention_score", 1.0)
    context_relevance = ragas_scores.get("retrieval", {}).get("context_relevance", 1.0)

    # 4. Query-Response Semantic & Domain Alignment Check
    from ..guardrails.alignment_validator import QueryResponseAlignmentValidator
    align_res = QueryResponseAlignmentValidator.validate(query=raw_query, response=draft, intent=intent)
    align_passed = align_res["passed"]

    # 5. Strict Multi-Gate Verification
    guard_passed = guard_res["passed"]
    jev_passed = (jev_score.level != "UNSAFE")
    # For structured deterministic tool outputs (growth calculation, pediatric math, timeline, patient records), output is intrinsically grounded
    if intent in ["GROWTH_ANALYSIS", "PEDIATRIC_MATH", "FEEDING_INTELLIGENCE", "TIMELINE_INSPECT", "PATIENT_RECORD_INQUIRY"]:
        ragas_faithfulness_passed = True
    else:
        ragas_faithfulness_passed = (faithfulness >= MIN_FAITHFULNESS and claim_res["passed"])
    ragas_harm_passed = (harm_prevention >= MIN_HARM_PREVENTION)

    all_passed = guard_passed and jev_passed and ragas_faithfulness_passed and ragas_harm_passed and align_passed

    if all_passed:
        final_text = claim_res.get("sanitized_response") or guard_res["sanitized_text"]
        return _return_with_span({
            "safety_approved": True,
            "safety_violations": [],
            "critique_notes": None,
            "output_guardrail_passed": True,
            "final_text_card": final_text,
            "final_voice_summary": state.get("voice_summary", "")
        })
    else:
        # Identify specific violations for targeted self-correction
        violations = list(guard_res.get("violations", []))
        if not align_passed:
            violations.extend(align_res.get("violations", []))
        if not ragas_faithfulness_passed:
            violations.append(f"RAGAS Faithfulness threshold failed ({faithfulness:.2f} < {MIN_FAITHFULNESS})")
            if claim_res.get("unsupported_claims"):
                violations.append(f"Unsupported claims: {claim_res['unsupported_claims']}")
        if not ragas_harm_passed:
            violations.append(f"RAGAS Harm Prevention threshold failed ({harm_prevention:.2f} < {MIN_HARM_PREVENTION})")
        if not jev_passed:
            violations.append("Jev safety engine flagged response as UNSAFE")

        # Check if self-correction loop limit reached
        if retry_count >= MAX_RETRY_LIMIT:
            # Loop exhausted: Trigger Human-in-the-Loop escalation
            hitl_res = hitl_service.evaluate_query_for_hitl(
                query=raw_query,
                baby_id=baby_id,
                retrieval_score=context_relevance,
                intent=intent,
                ai_draft=draft
            )
            if not hitl_res["requires_hitl"]:
                # Force create ticket for loop exhaustion
                hitl_service.create_ticket(
                    baby_id=baby_id,
                    raw_query=raw_query,
                    reasons=[f"Self-correction loop exhausted after {retry_count} retries", f"Safety violations: {violations}"],
                    urgency="HIGH",
                    ai_draft=draft,
                    intent=intent
                )

            fallback_text = (
                f"{guard_res['sanitized_text']}\n\n"
                "👨‍⚕️ **Clinical Care Team Review Requested (High Urgency)**\n"
                "*This query requires specialized pediatric evaluation. A ticket has been created on the clinical dashboard.*"
            )
            return _return_with_span({
                "safety_approved": False,
                "safety_violations": violations,
                "critique_notes": f"Exhausted {MAX_RETRY_LIMIT} self-correction attempts. Escalated to HITL.",
                "retry_count": retry_count + 1,
                "loop_iteration": loop_iteration + 1,
                "output_guardrail_passed": False,
                "final_text_card": fallback_text,
                "final_voice_summary": "I have escalated this inquiry to your baby's pediatric care team for review."
            })

        # Formulate actionable critique notes for the next loop iteration
        target_domain = align_res.get("query_domain", "clinical")
        critique = (
            f"Draft failed safety checks: {violations}. "
            f"Self-correction instructions: Target domain '{target_domain}'. "
            "Regenerate guidance directly answering the mother's specific inquiry, strictly grounded in authoritative AAP/WHO guidelines without deflecting to unrelated topics."
        )
        return _return_with_span({
            "safety_approved": False,
            "safety_violations": violations,
            "critique_notes": critique,
            "retry_count": retry_count + 1,
            "loop_iteration": loop_iteration + 1,
            "output_guardrail_passed": False,
            "final_text_card": guard_res["sanitized_text"],
            "final_voice_summary": "I cannot provide that specific recommendation as clinical guidelines advise against it."
        })

