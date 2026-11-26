"""
REST Router for Timeline, KMC Tracking, Growth, Hygiene, and Maternal Wellbeing.
"""

from fastapi import APIRouter, HTTPException, Query
from datetime import date
from typing import Optional, List, Dict, Any

from ..models.timeline import TimelineTask, KMCSession, GrowthRecord, MaternalWellbeing
from ..services.timeline_service import timeline_service

router = APIRouter(prefix="/api/v1/timeline", tags=["Timeline & Routine Care"])


@router.get("/{baby_id}", response_model=List[TimelineTask])
def get_daily_timeline(baby_id: str, target_date: Optional[date] = None):
    """Returns today's personalized care schedule with task completion status."""
    return timeline_service.get_daily_timeline(baby_id, target_date)


@router.get("/{baby_id}/next")
def get_what_should_i_do_next(baby_id: str):
    """Calculates the immediate upcoming or due care activity for the mother."""
    return timeline_service.get_what_should_i_do_next(baby_id)


@router.get("/{baby_id}/next-schedule")
def get_care_schedule_status(baby_id: str):
    """Calculates exact next feed & KMC due times from latest logged timestamps."""
    return timeline_service.get_care_schedule_status(baby_id)


# ── KMC Endpoints ───────────────────────────────────────────────────
@router.post("/kmc", response_model=KMCSession)
@router.post("/kmc/log", response_model=KMCSession)
def log_kmc_session(session: KMCSession):
    """Logs a skin-to-skin Kangaroo Mother Care session."""
    return timeline_service.log_kmc_session(session)


@router.get("/kmc/summary/{baby_id}")
def get_kmc_summary(baby_id: str, target_date: Optional[date] = None):
    """Returns today's cumulative KMC duration and remaining target."""
    return timeline_service.get_daily_kmc_summary(baby_id, target_date)


# ── Growth Intelligence ─────────────────────────────────────────────
@router.post("/growth/log", response_model=GrowthRecord)
def log_growth_measurement(record: GrowthRecord):
    """Logs infant physical measurements and calculates growth velocity."""
    return timeline_service.log_growth(record)


@router.get("/growth/{baby_id}", response_model=List[GrowthRecord])
def get_growth_records(baby_id: str):
    """Returns historical growth measurements and weight gain trend."""
    return timeline_service.get_growth_records(baby_id)


# ── Hygiene & Sterilization ─────────────────────────────────────────
@router.get("/hygiene/sterilization-protocol")
def get_sterilization_protocol():
    """Returns the 5-step clinical feeding equipment sterilization protocol."""
    return timeline_service.get_sterilization_protocol()


# ── Maternal Recovery & Wellbeing ───────────────────────────────────
@router.post("/maternal/checkin", response_model=MaternalWellbeing)
def log_maternal_checkin(entry: MaternalWellbeing):
    """Logs maternal postpartum hydration, rest, and emotional wellbeing."""
    return timeline_service.log_maternal_checkin(entry)


@router.get("/maternal/{baby_id}", response_model=List[MaternalWellbeing])
def get_maternal_records(baby_id: str):
    """Returns maternal recovery history."""
    return timeline_service.get_maternal_records(baby_id)
