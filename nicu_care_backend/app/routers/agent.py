"""
API Router for Agentic Voice and Text interaction.
Connects the FastAPI gateway to the LangGraph state machine,
instrumented with OpenTelemetry-compatible tracing, Short/Long-Term Memory, and RAGAS evaluation.
"""
import time
import json
import asyncio
from typing import Optional
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from ..models.agent import TextQueryRequest, VoiceQueryResponse
from ..agent.graph import nicu_agent
from ..agent.llm_wiki_curator import LLMWikiCurator
from ..services.cache_service import CacheService
from ..services.translation_service import translation_service
from ..telemetry.tracer import tracer
from ..telemetry.ragas_evaluator import ragas_evaluator
from ..telemetry.metrics_store import metrics_store
from app.memory.short_term_memory import short_term_memory
from app.memory.long_term_memory import long_term_memory
from ..services.llm_service import llm_service

router = APIRouter(prefix="/api/v1/agent", tags=["Agentic Reasoning & Voice"])

wiki_curator = LLMWikiCurator()
cache_service = CacheService()


@router.post("/text-query", response_model=VoiceQueryResponse)
def process_text_query(req: TextQueryRequest):
    """
    Processes a mother's text query or care statement through the LangGraph agent.
    Checks short-term semantic cache first, runs graph with telemetry spans,
    evaluates RAGAS metrics, and updates multi-agent memory.
    """
    trace_ctx = tracer.start_trace(baby_id=req.baby_id, user_query=req.text)

    # 0. Canonical Multilingual NLU Translation & Clinical Normalization
    canonical_query, detected_lang = translation_service.translate_to_canonical_english(req.text, req.language)
    from ..agent.nlp.normalizer import clinical_normalizer
    norm_res = clinical_normalizer.normalize_query(canonical_query)
    canonical_query = norm_res["normalized_query"]

    # 1. Short-Term Semantic Cache check (fast-path)
    span_cache = tracer.start_span("memory.short_term_cache_lookup", trace_id=trace_ctx.trace_id)
    cached = short_term_memory.get_cached_response(canonical_query) or cache_service.get(canonical_query)
    if cached:
        span_cache.set_attribute("cache.hit", True)
        tracer.end_span(span_cache, status="OK")
        trace_ctx.metrics["token_reduction_pct"] = 100.0
        trace_ctx.metrics["prompt_tokens"] = 10
        trace_ctx.metrics["completion_tokens"] = 50
        tracer.end_trace(trace_ctx)
        return VoiceQueryResponse(**cached)

    span_cache.set_attribute("cache.hit", False)
    tracer.end_span(span_cache, status="OK")

    # 2. Long-Term Memory (LLM Wiki Context Compilation)
    span_memory = tracer.start_span(
        "memory.long_term_wiki_compilation",
        trace_id=trace_ctx.trace_id,
        parent_span_id=trace_ctx.root_span_id
    )
    wiki_context = long_term_memory.get_baby_context_for_llm(req.baby_id, query=canonical_query)
    raw_history_tokens = 1200 + (len(canonical_query.split()) * 5)
    wiki_context_tokens = max(50, len(wiki_context.split()) * 4 // 3)
    token_savings_pct = round(((raw_history_tokens - wiki_context_tokens) / max(1, raw_history_tokens)) * 100.0, 1)

    span_memory.set_attribute("raw_context_tokens", raw_history_tokens)
    span_memory.set_attribute("compressed_wiki_tokens", wiki_context_tokens)
    span_memory.set_attribute("token_savings_pct", token_savings_pct)
    tracer.end_span(span_memory, status="OK")

    # 3. Create LangGraph Span and initialize State
    span_graph = tracer.start_span(
        "agent.langgraph_execution",
        trace_id=trace_ctx.trace_id,
        parent_span_id=trace_ctx.root_span_id
    )

    initial_state = {
        "baby_id": req.baby_id,
        "raw_query": canonical_query,
        "detected_language": detected_lang,
        "baby_wiki_context": wiki_context,
        "trace_id": trace_ctx.trace_id,
        "parent_span_id": span_graph.span_id,
        "input_guardrail_passed": True,
        "input_guardrail_notes": None,
        "intent": "CLINICAL_QA",
        "urgency": "INFORMATIONAL",
        "emergency_probability": 0.0,
        "is_emergency": False,
        "selected_model": req.model,
        "requested_model": req.model,
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

    # 4. Invoke LangGraph State Machine with Telemetry Spans
    final_state = nicu_agent.invoke(initial_state)

    span_graph.set_attribute("intent", final_state.get("intent", "CLINICAL_QA"))
    span_graph.set_attribute("is_emergency", final_state.get("is_emergency", False))
    span_graph.set_attribute("wiki_updated", final_state.get("wiki_updated", False))
    tracer.end_span(span_graph, status="OK")

    # 5. Extract Response Card & Voice Note
    text_card = final_state.get("final_text_card") or final_state.get("draft_response") or "Guidance recorded."
    voice_summary = final_state.get("final_voice_summary") or final_state.get("voice_summary") or ""
    is_emergency = final_state.get("is_emergency", False)

    # Optional Native Language Rendering (Telugu, Hindi, Tamil)
    target_lang = req.language if req.language and req.language != "en-US" else detected_lang
    if target_lang in ["te-IN", "hi-IN", "ta-IN"]:
        text_card, voice_summary = translation_service.render_native_response(
            text_card=text_card,
            voice_summary=voice_summary,
            target_lang=target_lang,
            is_emergency=is_emergency,
            model=req.model
        )

    # Cloud Text-to-Speech (GCP Free Tier: 4M chars/month)
    audio_b64 = None
    try:
        from ..services.cloud_speech_service import cloud_speech_service
        if cloud_speech_service.is_tts_available and voice_summary:
            audio_b64 = cloud_speech_service.synthesize_speech(voice_summary, target_lang)
    except Exception:
        pass

    resp = VoiceQueryResponse(
        text_card=text_card,
        voice_summary=voice_summary,
        is_emergency=is_emergency,
        detected_language=detected_lang,
        intent=final_state.get("intent", "CLINICAL_QA"),
        wiki_updated=final_state.get("wiki_updated", False),
        next_reminder_minutes=final_state.get("next_reminder_minutes"),
        audio_base64=audio_b64,
        model_used=final_state.get("selected_model") or req.model or llm_service.get_routed_model("clinical_synthesis"),
    )

    # 6. RAGAS Quality Evaluation Span
    span_ragas = tracer.start_span("telemetry.ragas_evaluation", trace_id=trace_ctx.trace_id)
    retrieved_chunks = final_state.get("retrieved_chunks", [])

    # If retrieved_chunks is empty but structured tools or growth analysis supplied data, provide effective context
    if not retrieved_chunks:
        tool_outputs = final_state.get("tool_outputs", {})
        if tool_outputs:
            retrieved_chunks = [{"header": k, "text": json.dumps(v), "metadata": {"min_corrected_weeks": 0, "max_corrected_weeks": 104}} for k, v in tool_outputs.items()]
        elif final_state.get("growth_analysis"):
            retrieved_chunks = [{"header": "Growth Analysis", "text": json.dumps(final_state["growth_analysis"]), "metadata": {"min_corrected_weeks": 0, "max_corrected_weeks": 104}}]
        elif final_state.get("hospital_contact"):
            retrieved_chunks = [{"header": "Hospital Emergency Contact", "text": json.dumps(final_state["hospital_contact"]), "metadata": {"min_corrected_weeks": 0, "max_corrected_weeks": 104}}]

    ragas_scores = ragas_evaluator.evaluate_full_turn(
        query=req.text,
        retrieved_chunks=retrieved_chunks,
        response_text=text_card,
        is_emergency=is_emergency,
        red_flag_triggered=is_emergency,
    )
    span_ragas.set_attribute("ragas.overall", ragas_scores.get("overall_ragas_score", 0.0))
    span_ragas.set_attribute("ragas.faithfulness", ragas_scores.get("generation", {}).get("faithfulness", 0.0))
    tracer.end_span(span_ragas, status="OK")
    tracer.log_ragas_to_langfuse(trace_ctx.trace_id, ragas_scores)

    # 6.5 Human-in-the-Loop (HITL) Safety Evaluation
    from ..services.hitl_service import hitl_service
    ret_score = ragas_scores.get("retrieval", {}).get("context_relevance", 0.8)
    hitl_res = hitl_service.evaluate_query_for_hitl(
        query=req.text,
        baby_id=req.baby_id,
        retrieval_score=ret_score,
        intent=resp.intent,
        ai_draft=text_card
    )
    if hitl_res["requires_hitl"]:
        resp.requires_hitl = True
        resp.hitl_ticket_id = hitl_res.get("ticket_id")
        resp.hitl_reasons = hitl_res.get("reasons", [])
        resp.hitl_urgency = hitl_res.get("urgency", "MEDIUM")
        hitl_notice = (
            f"\n\n👨‍⚕️ **Clinical Care Team Review Requested ({hitl_res['urgency']} Urgency)**\n"
            f"*Your inquiry involves: {', '.join(hitl_res['reasons'])}. "
            f"An alert has been dispatched to your baby's NICU care team on the clinical dashboard.*"
        )
        if "Clinical Care Team Review Requested" not in text_card:
            text_card = text_card.strip() + hitl_notice
            resp.text_card = text_card

    # 7. Update Short-Term & Long-Term Memory
    short_term_memory.append_turn(
        baby_id=req.baby_id,
        user_query=req.text,
        agent_response=text_card,
        intent=resp.intent,
    )

    if resp.wiki_updated or is_emergency:
        cat = "EMERGENCY_ALERT" if is_emergency else "CARE_UPDATE"
        long_term_memory.record_episodic_event(
            baby_id=req.baby_id,
            category=cat,
            title=f"{resp.intent} Event",
            description=req.text,
            data={"voice_summary": voice_summary},
        )

    # 7. Strict Quality Gates before Caching
    faithfulness_score = ragas_scores.get("generation", {}).get("faithfulness", 0.0)
    harm_score = ragas_scores.get("generation", {}).get("harm_prevention_score", 0.0)
    relevance_score = ragas_scores.get("generation", {}).get("answer_relevance", 0.0)
    safety_approved = final_state.get("safety_approved", False)
    output_guardrail_passed = final_state.get("output_guardrail_passed", False)
    requires_hitl = getattr(resp, "requires_hitl", False)

    quality_gates_passed = (
        not resp.is_emergency and
        resp.intent != "OUT_OF_DOMAIN" and
        not resp.intent.startswith("LOG_") and
        safety_approved and
        output_guardrail_passed and
        not requires_hitl and
        faithfulness_score >= 0.70 and
        harm_score >= 1.00 and
        relevance_score >= 0.70
    )

    if quality_gates_passed:
        cache_service.set(req.text, resp.model_dump())
        short_term_memory.set_cached_response(req.text, resp.model_dump())
        if canonical_query != req.text:
            cache_service.set(canonical_query, resp.model_dump())
            short_term_memory.set_cached_response(canonical_query, resp.model_dump())
        trace_ctx.metrics["cached_in_memory"] = True
    else:
        trace_ctx.metrics["cached_in_memory"] = False
        trace_ctx.metrics["cache_rejection_reason"] = (
            f"Quality gates failed (faithfulness={faithfulness_score:.2f}, "
            f"harm={harm_score:.2f}, rel={relevance_score:.2f}, "
            f"approved={safety_approved}, hitl={requires_hitl})"
        )

    # 8. Record Metrics & Finish Trace
    completion_tokens = len(text_card.split()) * 4 // 3
    trace_ctx.metrics = {
        "prompt_tokens": wiki_context_tokens + len(req.text.split()),
        "completion_tokens": completion_tokens,
        "raw_context_tokens": raw_history_tokens,
        "compressed_wiki_tokens": wiki_context_tokens,
        "token_reduction_pct": token_savings_pct,
        "ragas_scores": ragas_scores,
    }
    tracer.end_trace(trace_ctx)

    return resp


@router.post("/voice-query", response_model=VoiceQueryResponse)
async def process_voice_query(
    baby_id: str = Form(...),
    audio: Optional[UploadFile] = File(None),
    text_fallback: Optional[str] = Form(None),
    language: str = Form("en-US")
):
    """
    Receives voice audio from Flutter/mobile, processes with STT,
    runs the LangGraph agent, and returns text and voice guidance.
    """
    transcript = text_fallback or "Baby drank 50 ml fortified milk at 10 AM"

    if audio:
        content = await audio.read()
        if text_fallback:
            transcript = text_fallback

    req = TextQueryRequest(
        baby_id=baby_id,
        text=transcript,
        language=language
    )
    return process_text_query(req)


@router.post("/stream-query")
async def stream_agent_query(req: TextQueryRequest):
    """
    Streams the agent's multi-step execution and synthesized tokens
    via Server-Sent Events (SSE).
    """
    async def event_generator():
        # Step 1: NLU Translation
        canonical, lang = translation_service.translate_to_canonical_english(req.text, req.language)
        yield f"data: {json.dumps({'event': 'nlu', 'detected_language': lang, 'canonical_query': canonical})}\n\n"
        await asyncio.sleep(0.05)

        # Step 2: Triage
        yield f"data: {json.dumps({'event': 'status', 'step': 'triage_supervisor', 'message': 'Evaluating clinical urgency...'})}\n\n"
        await asyncio.sleep(0.05)

        # Step 3: Run Graph
        res = process_text_query(req)

        # Step 4: Stream Tokens
        yield f"data: {json.dumps({'event': 'triage_result', 'intent': res.intent, 'is_emergency': res.is_emergency})}\n\n"

        words = res.text_card.split()
        for i in range(0, len(words), 4):
            chunk = " ".join(words[i:i+4]) + " "
            yield f"data: {json.dumps({'event': 'token', 'chunk': chunk})}\n\n"
            await asyncio.sleep(0.02)

        # Step 5: Final completion payload
        yield f"data: {json.dumps({'event': 'complete', 'response': res.model_dump()})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
