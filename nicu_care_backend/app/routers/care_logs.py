"""
API Router for routine care logging: Feeds, Diapers, Medications, and 48h Summaries.
"""

from typing import List, Optional
from fastapi import APIRouter, HTTPException

from ..models.care_log import FeedingEntry, DiaperEntry, MedicationEntry, CareSummary
from ..services.care_log_service import CareLogService
from ..services.wiki_service import WikiService
from ..agent.guardrails.tool_guardrails import ToolGuardrails

router = APIRouter(prefix="/api/v1/baby/{baby_id}", tags=["Care Logs"])

log_service = CareLogService()
wiki_service = WikiService()


@router.post("/feeds", response_model=FeedingEntry, status_code=201)
def log_feed(baby_id: str, entry: FeedingEntry):
    """
    Logs a feeding entry.
    Runs Layer 3 Tool Guardrails to ensure volume doesn't exceed stomach capacity.
    """
    if entry.baby_id != baby_id:
        entry.baby_id = baby_id

    # Retrieve baby weight for physiological validation
    profile = wiki_service.load_baby_profile_json(baby_id)
    weight_grams = profile.discharge_weight_grams if profile else 2000

    val = ToolGuardrails.validate_feed_volume(entry.volume_ml, weight_grams)
    if not val["valid"]:
        raise HTTPException(status_code=422, detail=val["reason"])

    return log_service.log_feed(entry)


@router.get("/feeds", response_model=List[FeedingEntry])
def get_feeds(baby_id: str, since_hours: Optional[int] = 24):
    """Returns recent feeding entries (defaults to past 24 hours)."""
    return log_service.get_feeds(baby_id, since_hours=since_hours)


@router.post("/diapers", response_model=DiaperEntry, status_code=201)
def log_diaper(baby_id: str, entry: DiaperEntry):
    """Logs a diaper change (wet/soiled)."""
    if entry.baby_id != baby_id:
        entry.baby_id = baby_id
    return log_service.log_diaper(entry)


@router.get("/diapers", response_model=List[DiaperEntry])
def get_diapers(baby_id: str, since_hours: Optional[int] = 24):
    """Returns recent diaper entries (defaults to past 24 hours)."""
    return log_service.get_diapers(baby_id, since_hours=since_hours)


@router.post("/medications", response_model=MedicationEntry, status_code=201)
def log_medication(baby_id: str, entry: MedicationEntry):
    """Logs an administered medication or vitamin."""
    if entry.baby_id != baby_id:
        entry.baby_id = baby_id
    return log_service.log_medication(entry)


@router.get("/medications", response_model=List[MedicationEntry])
def get_medications(baby_id: str, since_hours: Optional[int] = 24):
    """Returns recent medication entries."""
    return log_service.get_medications(baby_id, since_hours=since_hours)


@router.get("/summary/48h", response_model=CareSummary)
def get_48h_care_summary(baby_id: str):
    """
    Generates an aggregated 48-hour clinical summary of intake,
    hydration, stool characteristics, and clinical flags.
    """
    return log_service.generate_48h_summary(baby_id)
