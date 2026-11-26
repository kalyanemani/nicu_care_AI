import urllib.request
import json
import sys
import os

sys.path.insert(0, os.path.abspath("."))

def fetch(url):
    try:
        req = urllib.request.urlopen(url, timeout=4)
        raw = req.read().decode("utf-8")
        try:
            data = json.loads(raw)
        except Exception:
            data = raw
        return req.status, data
    except Exception as e:
        return "ERR", str(e)

print("=== 1. SERVICES HEALTH ===")
for name, url in [
    ("FastAPI Backend (8000)", "http://127.0.0.1:8000/"),
    ("Streamlit Mother App (8501)", "http://127.0.0.1:8501/_stcore/health"),
    ("Streamlit Monitoring (8502)", "http://127.0.0.1:8502/_stcore/health")
]:
    code, _ = fetch(url)
    print(f"  {name}: HTTP {code}")

print("\n=== 2. LOCAL OLLAMA INFERENCE DAEMON ===")
code, ollama_ps = fetch("http://127.0.0.1:11434/api/ps")
if code != "ERR":
    running = [m.get("name") for m in ollama_ps.get("models", [])]
    print(f"  Models Currently Loaded in RAM/VRAM: {running if running else 'None (idle)'}")
else:
    print(f"  Ollama ps error: {ollama_ps}")

code, llm_status = fetch("http://127.0.0.1:8000/api/v1/telemetry/llm-status")
if code != "ERR":
    print(f"  Inference Status: {llm_status.get('status')}")
    print(f"  Active Generation Model: {llm_status.get('active_generation_model')}")
    print(f"  Timeouts Disabled: {llm_status.get('timeouts_disabled')}")
    print("  Task Routing:")
    for task, m in llm_status.get("routing_table", {}).items():
        print(f"    - {task}: {m}")

print("\n=== 3. TELEMETRY & RAGAS BENCHMARK SUMMARY ===")
code, summary = fetch("http://127.0.0.1:8000/api/v1/telemetry/summary")
if code != "ERR":
    print(f"  Total Traced Queries: {summary.get('total_traces_count', 0)}")
    print(f"  Rolling Latency: p50 = {summary.get('latency_p50_ms')} ms | p95 = {summary.get('latency_p95_ms')} ms")
    print(f"  Avg Token Savings: {summary.get('avg_token_reduction_pct')} %")
    print(f"  Avg RAGAS Faithfulness: {summary.get('avg_ragas_faithfulness')}")
    print(f"  Avg RAGAS Relevance: {summary.get('avg_ragas_relevance')}")
    print(f"  Avg Harm Prevention: {summary.get('avg_harm_prevention_score')}")

print("\n=== 4. RECENT 5 QUERY TRACES ===")
code, traces = fetch("http://127.0.0.1:8000/api/v1/telemetry/traces?limit=5")
if code != "ERR" and isinstance(traces, list):
    for t in traces[:5]:
        query = t.get("metadata", {}).get("user_query", "N/A")
        duration = t.get("duration_ms", 0)
        status = t.get("status", "N/A")
        ragas = t.get("metrics", {}).get("ragas_score", "N/A")
        print(f"  Query: \"{query}\" | Duration: {duration:.1f}ms | Status: {status} | RAGAS: {ragas}")
else:
    print(f"  Traces: {traces}")

print("\n=== 5. HUMAN-IN-THE-LOOP (HITL) QUEUE ===")
try:
    from app.services.hitl_service import hitl_service
    tickets = hitl_service.get_all_tickets()
    pending = [t for t in tickets if t.get("status") == "PENDING"]
    print(f"  Total HITL Tickets: {len(tickets)} (Pending Review: {len(pending)})")
    for t in pending[:3]:
        print(f"    Ticket {t.get('ticket_id')}: [{t.get('urgency')}] {t.get('reasons')}")
except Exception as e:
    print(f"  HITL check error: {e}")
