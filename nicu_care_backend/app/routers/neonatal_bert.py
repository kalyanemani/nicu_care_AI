"""
NeonatalBERT Clinical Transformer Router.

Exposes endpoints for:
- Real-time maternal query analysis & phenotype extraction (<20ms)
- Hospital discharge summary deconstruction
- Clinical dosage and claim entailment verification
"""
from typing import Dict, Any, List
from pydantic import BaseModel, Field
from fastapi import APIRouter

from ..services.neonatal_bert_service import neonatal_bert_service

router = APIRouter(prefix="/api/v1/neonatal-bert", tags=["NeonatalBERT Transformer Intelligence"])


class AnalyzeQueryRequest(BaseModel):
    query: str = Field(..., description="Maternal conversational query or reported symptoms")


class DischargeDeconstructRequest(BaseModel):
    discharge_summary_text: str = Field(..., description="Unstructured clinical discharge text from hospital")


class DosageVerifyRequest(BaseModel):
    claim_text: str
    evidence_guideline: str


@router.post("/analyze")
def analyze_query(req: AnalyzeQueryRequest) -> Dict[str, Any]:
    """Analyzes query with NeonatalBERT NLU, returning subword tokens, extracted entities, and urgency tier."""
    res = neonatal_bert_service.analyze_query(req.query)
    return {
        "query": res.query,
        "tokens": res.tokens,
        "intent": res.intent,
        "urgency_tier": res.urgency_tier,
        "urgency_score": res.urgency_score,
        "detected_entities": [
            {
                "entity_type": e.entity_type,
                "entity_id": e.entity_id,
                "raw_span": e.raw_span,
                "severity": e.severity,
                "confidence": e.confidence,
            }
            for e in res.detected_entities
        ],
        "phenotype_codes": res.phenotype_codes,
        "numerical_metrics": res.numerical_metrics,
        "latency_ms": res.latency_ms,
        "model_version": res.model_version,
    }


@router.post("/deconstruct-discharge")
def deconstruct_discharge(req: DischargeDeconstructRequest) -> Dict[str, Any]:
    """Deconstructs unstructured hospital discharge text into structured clinical parameters."""
    return neonatal_bert_service.deconstruct_discharge_summary(req.discharge_summary_text)


@router.post("/verify-dosage")
def verify_dosage(req: DosageVerifyRequest) -> Dict[str, Any]:
    """Checks mathematical and clinical entailment between an LLM claim and clinical guideline."""
    entailed, reason = neonatal_bert_service.verify_dosage_claim(req.claim_text, req.evidence_guideline)
    return {
        "entailed": entailed,
        "reason": reason,
    }
