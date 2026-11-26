"""
Pydantic schemas for the Personalized Care Timeline, KMC Sessions,
Growth Intelligence, and Maternal Recovery.
"""
from datetime import datetime, date
from typing import Optional, Literal, List, Dict, Any
from pydantic import BaseModel, Field, field_validator


class TimelineTask(BaseModel):
    """A single scheduled or dynamic care activity on the baby's daily timeline."""
    task_id: str
    time_str: str = Field(..., description="e.g. '08:00 AM'")
    category: Literal["FEEDING", "KMC_SESSION", "MEDICATION", "HYGIENE", "GROWTH", "MATERNAL_CARE", "APPOINTMENT"]
    title: str
    description: str
    status: Literal["COMPLETED", "DUE", "UPCOMING", "MISSED"]
    is_next: bool = False
    details: Optional[Dict[str, Any]] = None


class KMCSession(BaseModel):
    """A single Kangaroo Mother Care skin-to-skin session."""
    session_id: Optional[str] = None
    baby_id: str
    timestamp: datetime = Field(default_factory=datetime.now)
    duration_minutes: int = Field(..., gt=0, le=480, description="Duration in minutes")
    caregiver: Literal["mother", "father", "other"] = "mother"
    tolerated: bool = True
    notes: Optional[str] = None

    @field_validator("timestamp", mode="after")
    @classmethod
    def strip_timezone(cls, v: datetime) -> datetime:
        if v and getattr(v, "tzinfo", None) is not None:
            return v.replace(tzinfo=None)
        return v


class GrowthRecord(BaseModel):
    """Physical growth measurement with clinical velocity tracking."""
    record_id: Optional[str] = None
    baby_id: str
    date_recorded: date = Field(default_factory=date.today)
    weight_grams: Optional[int] = Field(default=None, gt=400, le=10000)
    length_cm: Optional[float] = Field(default=None, gt=20.0, le=80.0)
    head_circumference_cm: Optional[float] = Field(default=None, gt=15.0, le=55.0)
    corrected_age_weeks: Optional[int] = None
    daily_gain_g_per_day: Optional[float] = None
    velocity_status: Optional[Literal["adequate", "slow", "rapid"]] = None
    notes: Optional[str] = None


class MaternalWellbeing(BaseModel):
    """Maternal postpartum recovery, rest, and emotional wellbeing log."""
    entry_id: Optional[str] = None
    baby_id: str
    timestamp: datetime = Field(default_factory=datetime.now)
    hydration_glasses: int = Field(default=0, ge=0, le=25)
    rest_hours: float = Field(default=0.0, ge=0.0, le=24.0)
    mood: Literal["feeling_good", "tired_but_coping", "overwhelmed", "anxious", "exhausted"] = "tired_but_coping"
    notes: Optional[str] = None
