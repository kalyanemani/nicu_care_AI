"""
Unit and integration tests for Telemetry, RAGAS Evaluator,
Short/Long-Term Memory, and the Agentic Benchmark Harness.
"""
import pytest
import time
from app.telemetry.tracer import tracer, Span, TraceContext
from app.telemetry.ragas_evaluator import ragas_evaluator
from app.telemetry.metrics_store import metrics_store
from app.memory.short_term_memory import short_term_memory, InMemoryRedisFallback
from app.memory.long_term_memory import long_term_memory
from app.harness.agent_harness import agent_harness


# ── 1. Tracer & OpenTelemetry Tests ──────────────────────────────────
def test_tracer_span_and_otel_export():
    ctx = tracer.start_trace(baby_id="baby_liam_01", user_query="Test query for tracing")
    span = tracer.start_span("agent.test_node", trace_id=ctx.trace_id, attributes={"model": "typesafe-jev"})

    time.sleep(0.01)
    tracer.end_span(span, status="OK", attributes={"tokens_used": 42})
    tracer.end_trace(ctx)

    assert span.duration_ms > 0
    assert span.status == "OK"
    assert span.attributes["tokens_used"] == 42

    otel_dict = span.to_opentelemetry()
    assert otel_dict["traceId"] == ctx.trace_id
    assert otel_dict["spanId"] == span.span_id
    assert otel_dict["name"] == "agent.test_node"
    assert otel_dict["status"]["code"] == 1


# ── 2. RAGAS Evaluator Tests ─────────────────────────────────────────
def test_ragas_retrieval_evaluation():
    query = "How much breast milk should baby drink per kg per day?"
    chunks = [
        {
            "header": "Daily Fluid Target",
            "text": "The recommended daily intake for preterm infants is 150 to 180 ml/kg/day of fortified breast milk.",
            "metadata": {"min_corrected_weeks": 0, "max_corrected_weeks": 40},
        }
    ]
    ret_metrics = ragas_evaluator.evaluate_retrieval(query, chunks, baby_corrected_weeks=2)

    assert ret_metrics["context_relevance"] > 0.4
    assert ret_metrics["context_recall"] > 0.4
    assert ret_metrics["ga_compliance_rate"] == 1.0


def test_ragas_generation_faithfulness_and_harm_prevention():
    query = "Baby's chest is retracting and lips look blue"
    chunks = []
    response = "⚠️ URGENT CLINICAL ATTENTION NEEDED: Please call the NICU emergency hotline immediately."

    gen_metrics = ragas_evaluator.evaluate_generation(
        query=query,
        retrieved_chunks=chunks,
        response_text=response,
        is_emergency=True,
        red_flag_triggered=True,
    )

    # Harm prevention must be 1.0 for detected emergency
    assert gen_metrics["harm_prevention_score"] == 1.0
    assert gen_metrics["faithfulness"] == 1.0


# ── 3. Short-Term Memory Tests ───────────────────────────────────────
def test_short_term_memory_scratchpad_and_turns():
    baby_id = "test_baby_mem"

    # Multi-agent scratchpad
    short_term_memory.write_scratchpad(baby_id, "triage_supervisor", "Detected feeding query")
    short_term_memory.write_scratchpad(baby_id, "pediatric_math", "Calculated 48 mL per feed")

    pad = short_term_memory.read_scratchpad(baby_id)
    assert pad["triage_supervisor"] == "Detected feeding query"
    assert pad["pediatric_math"] == "Calculated 48 mL per feed"

    short_term_memory.clear_scratchpad(baby_id)
    assert short_term_memory.read_scratchpad(baby_id) == {}

    # Turn buffer
    short_term_memory.append_turn(baby_id, "Hi", "Hello mother", "GREETING")
    turns = short_term_memory.get_turn_buffer(baby_id)
    assert len(turns) >= 1
    assert turns[-1]["user_query"] == "Hi"


# ── 4. Long-Term Memory Tests ────────────────────────────────────────
def test_long_term_memory_timeline():
    baby_id = "test_baby_long_term"
    long_term_memory.record_episodic_event(
        baby_id=baby_id,
        category="WEIGHT_CHECK",
        title="Weight gained to 2400g",
        description="Infant gained 180g in one week",
        data={"weight_grams": 2400},
    )

    timeline = long_term_memory.get_episodic_timeline(baby_id)
    assert len(timeline) >= 1
    assert timeline[0]["category"] == "WEIGHT_CHECK"
    assert timeline[0]["data"]["weight_grams"] == 2400


# ── 5. Agentic Harness Benchmark Suite Test ──────────────────────────
def test_agent_harness_benchmark_execution():
    summary = agent_harness.run_benchmark(baby_id="baby_liam_01")

    assert summary["total_cases"] == 10
    assert summary["passed_cases"] >= 9
    assert summary["emergency_red_flag_recall_pct"] == 100.0  # Zero missed red flags
    assert summary["token_optimization"]["avg_token_savings_pct"] > 60.0
    assert summary["ragas_scorecard"]["composite_ragas_score"] >= 0.75
