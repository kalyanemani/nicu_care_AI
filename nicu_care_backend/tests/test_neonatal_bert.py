"""
Unit and Integration Tests for NeonatalBERT Clinical Transformer Intelligence.
"""
from fastapi.testclient import TestClient

from app.main import app
from app.services.neonatal_bert_service import neonatal_bert_service

client = TestClient(app)


def test_neonatal_bert_critical_green_vomit():
    """Verify NeonatalBERT catches colloquial bilious vomiting as a critical surgical emergency."""
    analysis = neonatal_bert_service.analyze_query("Liam threw up dark greenish liquid and seems fussy")
    assert analysis.intent == "EMERGENCY"
    assert analysis.urgency_tier == "CRITICAL"
    assert analysis.urgency_score >= 0.95
    assert "symptom_green_vomit" in analysis.phenotype_codes
    assert analysis.latency_ms < 50.0  # Ultra fast sub-50ms


def test_neonatal_bert_respiratory_retractions():
    """Verify NeonatalBERT maps colloquial chest pulling to subcostal retractions."""
    analysis = neonatal_bert_service.analyze_query("baby's chest is pulling in deeply under ribs and grunting")
    assert analysis.urgency_tier == "CRITICAL"
    assert "symptom_retractions" in analysis.phenotype_codes


def test_neonatal_bert_pediatric_math_extraction():
    """Verify NeonatalBERT extracts infant weight and classifies mathematical intake query."""
    analysis = neonatal_bert_service.analyze_query("How many ml should I give for my 2400g baby every 3 hours?")
    assert analysis.intent == "PEDIATRIC_MATH"
    assert analysis.numerical_metrics.get("weight_grams") == 2400.0


def test_neonatal_bert_kmc_procedure():
    """Verify Kangaroo Mother Care procedural classification."""
    analysis = neonatal_bert_service.analyze_query("when is the best time to do kangaroo mother care skin to skin?")
    assert analysis.intent == "PROCEDURE"
    assert any(e.entity_id == "proc_kmc" for e in analysis.detected_entities)


def test_neonatal_bert_discharge_deconstruction():
    """Verify parsing unstructured discharge notes into structured clinical milestones."""
    discharge_text = (
        "Preterm male infant delivered at 29w+2d GA, birth weight 1180 grams. "
        "Discharged on Day 56 at 1820g on full oral EBM with HMF (22 kcal/oz). "
        "Diagnosed with BPD Grade 1 (room air). ROP Zone II Stage 1, follow up in 2 weeks."
    )
    decon = neonatal_bert_service.deconstruct_discharge_summary(discharge_text)
    assert decon["gestational_age_weeks"] == 29
    assert decon["gestational_age_days"] == 2
    assert decon["discharge_weight_grams"] == 1820.0
    assert "BPD Grade 1" in decon["bpd_status"]
    assert "ROP Zone II" in decon["rop_status"]
    assert "HMF" in decon["fortifier_regimen"]


def test_neonatal_bert_api_endpoints():
    """Verify FastAPI endpoints for NeonatalBERT."""
    # 1. Analyze endpoint
    resp = client.post(
        "/api/v1/neonatal-bert/analyze",
        json={"query": "Liam has fever with 38.5 C rectal temp"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["urgency_tier"] == "CRITICAL"
    assert "symptom_fever" in data["phenotype_codes"]
    assert data["numerical_metrics"]["temperature_c"] == 38.5

    # 2. Dosage check endpoint
    verify_resp = client.post(
        "/api/v1/neonatal-bert/verify-dosage",
        json={
            "claim_text": "Give 160 ml per kg per day",
            "evidence_guideline": "Standard AAP LBW target is 150-180 ml per kg daily.",
        },
    )
    assert verify_resp.status_code == 200
    assert verify_resp.json()["entailed"] is True
