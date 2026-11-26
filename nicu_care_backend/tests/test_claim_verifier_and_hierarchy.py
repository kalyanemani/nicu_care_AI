"""
Unit tests for Claim-Level Grounded Verification, Wiki Context Deduplication,
Hierarchical OpenTelemetry Spans, and Structured Discharge Plans.
"""

from datetime import date
import pytest
from app.agent.guardrails.claim_verifier import ClaimVerificationEngine
from app.models.baby import BabyDischargePlan, FeedingPlan, MedicationPrescription, KMCPlan
from app.services.wiki_service import WikiService
from app.memory.long_term_memory import LongTermMemoryManager
from app.services.rag_service import ClinicalRAGService
from app.telemetry.tracer import AgentTracer, TraceContext
from app.routers.agent import process_text_query
from app.models.agent import TextQueryRequest


def test_claim_level_verification_engine_grounded():
    retrieved_chunks = [{
        "header": "KMC Positioning",
        "text": "Hold the baby upright against the bare chest, between the breasts in a frog-like position with head turned and airway clear."
    }]
    response = (
        "🩺 **Clinical Guidance: KMC Positioning**\n\n"
        "Hold the baby upright against the bare chest in a frog-like position. "
        "Keep the baby's head turned to one side with the airway clear at all times.\n\n"
        "Disclaimer: This guidance is educational."
    )
    res = ClaimVerificationEngine.verify_claims(response, retrieved_chunks, intent="CLINICAL_QA")
    assert res["passed"] is True
    assert res["faithfulness"] >= 0.90
    assert len(res["unsupported_claims"]) == 0


def test_claim_level_verification_engine_unsupported():
    retrieved_chunks = [{
        "header": "Safe Sleep",
        "text": "Place baby on their back on a firm mattress without loose blankets or pillows."
    }]
    # Candidate LLM response makes unsupported claim
    response = (
        "Place baby on their back on a firm mattress. "
        "You can give the baby chamomile tea and water every 2 hours to calm reflux."
    )
    res = ClaimVerificationEngine.verify_claims(response, retrieved_chunks, intent="CLINICAL_QA")
    assert len(res["unsupported_claims"]) > 0
    assert res["faithfulness"] < 0.90


def test_wiki_deduplication_and_selective_retrieval(tmp_path):
    ws = WikiService()
    mem = LongTermMemoryManager(wiki_svc=ws)

    # Test patch deduplication
    sec_content = ws.patch_section("baby_liam_01", "active_regimen", "Iron drops 1.2 mL daily")
    len_before = len(sec_content)
    # Repeated patch with same content should NOT inflate section
    sec_content2 = ws.patch_section("baby_liam_01", "active_regimen", "Iron drops 1.2 mL daily")
    assert len(sec_content2) == len_before

    # Test query-selective retrieval for procedural query
    procedural_ctx = mem.get_baby_context_for_llm("baby_liam_01", query="how to do KMC")
    assert len(procedural_ctx.split()) < 350
    # Procedural query should omit bloated regimen logs
    assert "ACTIVE_REGIMEN" not in procedural_ctx


def test_hierarchical_opentelemetry_spans():
    req = TextQueryRequest(baby_id="baby_liam_01", text="how to do KMC")
    resp = process_text_query(req)
    assert resp is not None

    from app.telemetry.tracer import tracer
    traces = tracer.get_recent_traces(limit=1)
    assert len(traces) > 0
    t = traces[0]

    # Verify root span exists
    spans = t["spans"]
    root_span = next((s for s in spans if s["name"] == "request"), None)
    assert root_span is not None
    assert root_span["parent_span_id"] is None

    # Verify child spans reference parent properly
    graph_span = next((s for s in spans if s["name"] == "agent.langgraph_execution"), None)
    assert graph_span is not None
    assert graph_span["parent_span_id"] == root_span["span_id"]

    # Verify langgraph inner node spans reference graph_span
    triage_span = next((s for s in spans if s["name"] == "agent.langgraph.triage"), None)
    if triage_span:
        assert triage_span["parent_span_id"] == graph_span["span_id"]

    guide_span = next((s for s in spans if s["name"] == "agent.langgraph.clinical_guide"), None)
    if guide_span:
        assert guide_span["parent_span_id"] == graph_span["span_id"]

    critic_span = next((s for s in spans if s["name"] == "agent.langgraph.safety_critic"), None)
    if critic_span:
        assert critic_span["parent_span_id"] == graph_span["span_id"]


def test_baby_discharge_plan_model():
    plan = BabyDischargePlan(
        baby_id="baby_liam_01",
        discharge_date=date(2026, 11, 3),
        gestational_age_at_birth="29 weeks 2 days",
        birth_weight_g=1180,
        discharge_weight_g=1820,
        feeding_plan=FeedingPlan(
            target_volume_ml_per_day=380,
            per_feed_ml="45-54 mL every 3 hours"
        ),
        medications=[
            MedicationPrescription(
                name="Iron Drops",
                dose="1.2 mL",
                frequency="Once daily"
            )
        ],
        kmc_plan=KMCPlan(
            daily_target_hours=2.5,
            minimum_session_minutes=60
        ),
        clinician_approved=True,
        approving_clinician="Dr. Rao"
    )
    assert plan.baby_id == "baby_liam_01"
    assert plan.clinician_approved is True
    assert len(plan.medications) == 1
    assert plan.feeding_plan.target_volume_ml_per_day == 380


def test_clinical_rag_procedural_boost_and_12_domains():
    rag = ClinicalRAGService()
    # Check that chunks are mapped into domains
    assert len(rag.chunks) > 0
    domains = {c.get("domain") for c in rag.chunks}
    assert "kangaroo_mother_care" in domains

    # Procedural retrieval should rank Positioning or Preparation at the top
    results = rag.retrieve("how to do KMC", top_k=2)
    assert len(results) == 2
    top_headers = [r["header"] for r in results]
    assert any("Positioning" in h or "Preparation" in h for h in top_headers)
