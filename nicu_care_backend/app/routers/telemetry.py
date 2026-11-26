"""
API Router for Telemetry, RAGAS Quality Metrics, Multi-Agent Memory, and Benchmark Harness.
"""
from typing import Optional, List, Dict, Any
from fastapi import APIRouter
from ..telemetry.tracer import tracer
from ..telemetry.metrics_store import metrics_store
from ..harness.agent_harness import agent_harness, BENCHMARK_OUTPUT_FILE
from app.memory.short_term_memory import short_term_memory
from app.memory.long_term_memory import long_term_memory
from ..services.llm_service import llm_service
import json

router = APIRouter(prefix="/api/v1", tags=["Telemetry & Observability"])


@router.get("/telemetry/llm-status")
def get_llm_status():
    """Returns the operational status of local Ollama models, embedding model, and fallbacks."""
    return llm_service.check_ollama_status()


@router.post("/telemetry/select-model")
def select_model(payload: Dict[str, str]):
    """
    Dynamically select the model for a task (e.g. {"model": "medgemma1.5:latest", "task_type": "clinical_synthesis"}).
    """
    model = payload.get("model", "medgemma1.5:latest")
    task_type = payload.get("task_type", "clinical_synthesis")
    llm_service.set_task_model(task_type, model)
    return {
        "status": "UPDATED",
        "task_type": task_type,
        "active_model": model,
        "routing_table": llm_service.TASK_ROUTING_TABLE,
        "timeouts_disabled": True,
    }


@router.post("/telemetry/enable-medgemma")
def enable_medgemma():
    """
    Activates MedGemma 1.5 as the primary pediatric reasoning model for clinical synthesis.
    """
    llm_service.enable_medgemma("medgemma1.5:latest")
    return {
        "status": "MEDGEMMA_ACTIVATED",
        "active_model": "medgemma1.5:latest",
        "role": "Primary Pediatric Clinical Reasoning & Synthesis",
        "timeouts_disabled": True,
        "routing_table": llm_service.TASK_ROUTING_TABLE,
    }


@router.get("/telemetry/summary")
def get_telemetry_summary():
    """Returns rolling p50/p95 latency, token savings, and average RAGAS scores."""
    return metrics_store.compute_summary()


@router.get("/telemetry/traces")
def get_recent_traces(limit: int = 50):
    """Returns recent OpenTelemetry-compatible agent traces."""
    return tracer.get_recent_traces(limit=limit)


@router.get("/telemetry/benchmark/latest")
def get_latest_benchmark():
    """Returns the latest benchmark scorecard from disk or runs a fresh one if missing."""
    if BENCHMARK_OUTPUT_FILE.exists():
        try:
            return json.loads(BENCHMARK_OUTPUT_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return agent_harness.run_benchmark()


@router.post("/telemetry/benchmark/run")
def trigger_benchmark(baby_id: str = "baby_liam_01"):
    """Triggers on-demand execution of the 10-case clinical evaluation benchmark harness."""
    return agent_harness.run_benchmark(baby_id=baby_id)


@router.get("/memory/short-term/keys")
def get_short_term_keys():
    """Returns all active keys in the Redis / In-Memory Short-Term store."""
    return short_term_memory.get_all_keys()


@router.get("/memory/short-term/turns/{baby_id}")
def get_short_term_turns(baby_id: str):
    """Returns the active session turn buffer for an infant."""
    return short_term_memory.get_turn_buffer(baby_id)


@router.get("/memory/long-term/timeline/{baby_id}")
def get_long_term_timeline(baby_id: str):
    """Returns the durable episodic memory timeline for an infant."""
    return long_term_memory.get_episodic_timeline(baby_id)
