"""
Open-Source OpenTelemetry-Compatible Tracer & Span Engine.
Captures node-level multi-agent spans, RAG retrieval timings,
token optimization statistics, and cyclic graph iterations.
"""
import os
import json
import time
import uuid
from typing import Dict, List, Any, Optional
from pathlib import Path

TELEMETRY_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "telemetry"
TELEMETRY_DIR.mkdir(parents=True, exist_ok=True)
TRACES_FILE = TELEMETRY_DIR / "traces.jsonl"


class Span:
    """Represents a single instrumented execution unit in the agent graph."""

    def __init__(
        self,
        name: str,
        trace_id: str,
        parent_span_id: Optional[str] = None,
        attributes: Optional[Dict[str, Any]] = None,
    ):
        self.span_id = uuid.uuid4().hex[:16]
        self.trace_id = trace_id
        self.parent_span_id = parent_span_id
        self.name = name
        self.start_time = time.time()
        self.end_time: Optional[float] = None
        self.duration_ms: float = 0.0
        self.status: str = "RUNNING"
        self.attributes: Dict[str, Any] = attributes or {}
        self.events: List[Dict[str, Any]] = []

    def set_attribute(self, key: str, value: Any):
        self.attributes[key] = value

    def add_event(self, name: str, payload: Optional[Dict[str, Any]] = None):
        self.events.append({
            "name": name,
            "timestamp": time.time(),
            "payload": payload or {},
        })

    def end(self, status: str = "OK", error_msg: Optional[str] = None):
        self.end_time = time.time()
        self.duration_ms = round((self.end_time - self.start_time) * 1000.0, 2)
        self.status = status
        if error_msg:
            self.attributes["error.message"] = error_msg

    def to_dict(self) -> Dict[str, Any]:
        return {
            "span_id": self.span_id,
            "trace_id": self.trace_id,
            "parent_span_id": self.parent_span_id,
            "name": self.name,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration_ms": self.duration_ms,
            "status": self.status,
            "attributes": self.attributes,
            "events": self.events,
        }

    def to_opentelemetry(self) -> Dict[str, Any]:
        """Exports in standard OpenTelemetry JSON format for Phoenix / Arize / OTel collector."""
        return {
            "traceId": self.trace_id,
            "spanId": self.span_id,
            "parentSpanId": self.parent_span_id or "",
            "name": self.name,
            "kind": "SPAN_KIND_INTERNAL",
            "startTimeUnixNano": int(self.start_time * 1e9),
            "endTimeUnixNano": int((self.end_time or time.time()) * 1e9),
            "status": {"code": 1 if self.status == "OK" else 2},
            "attributes": [
                {"key": k, "value": {"stringValue": str(v)}}
                for k, v in self.attributes.items()
            ],
        }


class TraceContext:
    """Encapsulates a full end-to-end conversation turn trace."""

    def __init__(self, trace_id: str, baby_id: str, user_query: str):
        self.trace_id = trace_id
        self.baby_id = baby_id
        self.user_query = user_query
        self.start_time = time.time()
        self.end_time: Optional[float] = None
        self.total_duration_ms: float = 0.0
        self.spans: List[Span] = []
        self.root_span: Optional[Span] = None
        self.root_span_id: Optional[str] = None
        self.metrics: Dict[str, Any] = {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "raw_context_tokens": 0,
            "compressed_wiki_tokens": 0,
            "token_reduction_pct": 0.0,
            "ragas_scores": {},
        }
        self.status = "OK"

    def add_span(self, span: Span):
        self.spans.append(span)

    def finish(self):
        self.end_time = time.time()
        self.total_duration_ms = round((self.end_time - self.start_time) * 1000.0, 2)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "baby_id": self.baby_id,
            "user_query": self.user_query,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "total_duration_ms": self.total_duration_ms,
            "status": self.status,
            "metrics": self.metrics,
            "spans": [s.to_dict() for s in self.spans],
        }


class LangfuseExporter:
    """Exports trace contexts, spans, and RAGAS evaluation scores to Langfuse via modern OpenTelemetry."""

    def __init__(self):
        self.enabled = False
        self.provider = None
        self.tracer = None
        self.pk = os.getenv("LANGFUSE_PUBLIC_KEY")
        self.sk = os.getenv("LANGFUSE_SECRET_KEY")
        self.host = (os.getenv("LANGFUSE_HOST") or os.getenv("LANGFUSE_BASE_URL") or "https://cloud.langfuse.com").rstrip("/")
        if self.pk and self.sk:
            self.enabled = True
            try:
                import base64
                from opentelemetry import trace
                from opentelemetry.sdk.resources import Resource
                from opentelemetry.sdk.trace import TracerProvider
                from opentelemetry.sdk.trace.export import SimpleSpanProcessor
                from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

                encoded_auth = base64.b64encode(f"{self.pk}:{self.sk}".encode("utf-8")).decode("utf-8")
                self.provider = TracerProvider(resource=Resource.create({"service.name": "nicu-care-backend"}))
                otlp_exporter = OTLPSpanExporter(
                    endpoint=f"{self.host}/api/public/otel/v1/traces",
                    headers={
                        "Authorization": f"Basic {encoded_auth}",
                        "x-langfuse-ingestion-version": "4",
                    },
                )
                self.provider.add_span_processor(SimpleSpanProcessor(otlp_exporter))
                self.tracer = self.provider.get_tracer("nicu-agent-tracer")
            except Exception as e:
                import logging
                logging.getLogger("tracer").warning(f"Could not initialize OpenTelemetry exporter: {e}")

    def export_trace(self, trace_dict: Dict[str, Any]):
        if not self.enabled or not self.tracer:
            return
        try:
            import uuid
            from opentelemetry import trace
            from opentelemetry.trace import SpanContext, TraceFlags, NonRecordingSpan

            trace_id_hex = trace_dict.get("trace_id") or uuid.uuid4().hex
            # Ensure valid 32-hex format
            if len(trace_id_hex) < 32:
                trace_id_hex = trace_id_hex.zfill(32)
            elif len(trace_id_hex) > 32:
                trace_id_hex = trace_id_hex[:32]

            span_id_hex = uuid.uuid4().hex[:16]
            remote_ctx = SpanContext(
                trace_id=int(trace_id_hex, 16),
                span_id=int(span_id_hex, 16),
                is_remote=True,
                trace_flags=TraceFlags(0x01),
            )
            parent_ctx = trace.set_span_in_context(NonRecordingSpan(remote_ctx))

            query = trace_dict.get("user_query", "")
            baby_id = trace_dict.get("baby_id", "baby_unknown")
            trace_name = f"nicu_agent_{query[:30]}" if query else "nicu_agent_query"

            with self.tracer.start_as_current_span(trace_name, context=parent_ctx) as root:
                root.set_attribute("user.id", baby_id)
                root.set_attribute("baby_id", baby_id)
                root.set_attribute("user_query", query)
                root.set_attribute("status", trace_dict.get("status", "OK"))

                for s in trace_dict.get("spans", []):
                    span_name = s.get("name", "span")
                    if span_name == "request":
                        continue
                    with self.tracer.start_as_current_span(span_name) as child:
                        for k, v in s.get("attributes", {}).items():
                            if isinstance(v, (str, bool, int, float)):
                                child.set_attribute(str(k), v)
                        child.set_attribute("span_status", s.get("status", "OK"))

            if self.provider:
                self.provider.force_flush()
        except Exception as e:
            import logging
            logging.getLogger("tracer").warning(f"Langfuse export_trace error: {e}")

    def export_ragas_scores(self, trace_id: str, ragas_scores: Dict[str, Any]):
        if not self.enabled or not self.pk or not self.sk:
            return
        try:
            import base64
            import urllib.request
            auth = base64.b64encode(f"{self.pk}:{self.sk}".encode()).decode()
            gen = ragas_scores.get("generation", {})
            ret = ragas_scores.get("retrieval", {})
            scores_to_send = [
                ("ragas.faithfulness", gen.get("faithfulness")),
                ("ragas.harm_prevention", gen.get("harm_prevention_score")),
                ("ragas.answer_relevance", gen.get("answer_relevance")),
                ("ragas.context_relevance", ret.get("context_relevance")),
                ("ragas.composite", ragas_scores.get("overall_ragas_score")),
            ]
            for name, val in scores_to_send:
                if val is not None:
                    payload = {
                        "traceId": trace_id,
                        "name": name,
                        "value": float(val),
                        "dataType": "NUMERIC",
                        "comment": "Evaluated by NICU Care RAGAS engine",
                    }
                    req = urllib.request.Request(
                        f"{self.host}/api/public/scores",
                        data=json.dumps(payload).encode("utf-8"),
                        headers={"Authorization": f"Basic {auth}", "Content-Type": "application/json"},
                    )
                    with urllib.request.urlopen(req, timeout=5) as resp:
                        pass
        except Exception as e:
            import logging
            logging.getLogger("tracer").warning(f"Langfuse export_ragas_scores error: {e}")


class AgentTracer:
    """Manages active traces, Langfuse exporter, and persistent streaming trace logs."""

    def __init__(self, trace_file: Path = TRACES_FILE):
        self.trace_file = trace_file
        self.active_traces: Dict[str, TraceContext] = {}
        self.langfuse = LangfuseExporter()

    def start_trace(self, baby_id: str, user_query: str) -> TraceContext:
        trace_id = uuid.uuid4().hex
        ctx = TraceContext(trace_id=trace_id, baby_id=baby_id, user_query=user_query)
        # Create root span "request" representing the full execution hierarchy
        root_span = Span(
            name="request",
            trace_id=trace_id,
            parent_span_id=None,
            attributes={"baby_id": baby_id, "user_query": user_query}
        )
        ctx.root_span = root_span
        ctx.root_span_id = root_span.span_id
        ctx.add_span(root_span)
        self.active_traces[trace_id] = ctx
        return ctx

    def start_span(
        self,
        name: str,
        trace_id: str,
        parent_span_id: Optional[str] = None,
        attributes: Optional[Dict[str, Any]] = None,
    ) -> Span:
        # Default parent_span_id to the root span if not explicitly provided
        if parent_span_id is None and trace_id in self.active_traces:
            parent_span_id = self.active_traces[trace_id].root_span_id

        span = Span(name=name, trace_id=trace_id, parent_span_id=parent_span_id, attributes=attributes)
        if trace_id in self.active_traces:
            self.active_traces[trace_id].add_span(span)
        return span

    def end_span(
        self,
        span: Span,
        status: str = "OK",
        error_msg: Optional[str] = None,
        attributes: Optional[Dict[str, Any]] = None,
    ):
        if attributes:
            for k, v in attributes.items():
                span.set_attribute(k, v)
        span.end(status=status, error_msg=error_msg)

    def end_trace(self, trace_ctx: TraceContext, status: str = "OK"):
        if trace_ctx.root_span and trace_ctx.root_span.status == "RUNNING":
            trace_ctx.root_span.end(status=status)
        trace_ctx.status = status
        trace_ctx.finish()
        trace_dict = trace_ctx.to_dict()
        if trace_ctx.trace_id in self.active_traces:
            del self.active_traces[trace_ctx.trace_id]

        # Write to JSONL persistence
        try:
            with open(self.trace_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(trace_dict) + "\n")
        except Exception:
            pass

        # Export to Langfuse if enabled
        if self.langfuse.enabled:
            self.langfuse.export_trace(trace_dict)
            ragas_scores = trace_dict.get("metrics", {}).get("ragas_scores")
            if ragas_scores:
                self.langfuse.export_ragas_scores(trace_dict["trace_id"], ragas_scores)

    def log_ragas_to_langfuse(self, trace_id: str, ragas_scores: Dict[str, Any]):
        """Scores the trace in Langfuse with quantitative RAGAS metrics."""
        if self.langfuse.enabled:
            self.langfuse.export_ragas_scores(trace_id, ragas_scores)

    def get_recent_traces(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Reads recent traces from JSONL store."""
        if not self.trace_file.exists():
            return []
        traces = []
        try:
            with open(self.trace_file, "r", encoding="utf-8") as f:
                lines = f.readlines()
                for line in lines[-limit:]:
                    line_clean = line.strip()
                    if line_clean:
                        traces.append(json.loads(line_clean))
        except Exception:
            pass
        return list(reversed(traces))


# Global Singleton Tracer
tracer = AgentTracer()
