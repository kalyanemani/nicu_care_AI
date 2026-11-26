"""
Pydantic schemas for daily routine care logging:
Feedings, Diapers, Medications, and 48-Hour Rolling Summaries.
"""

from datetime import datetime
from typing import Optional, Literal, List
from pydantic import BaseModel, Field, field_validator


class FeedingEntry(BaseModel):
    """Log entry for an infant feeding."""
    entry_id: Optional[str] = None
    baby_id: str = Field(..., description="Unique baby ID, e.g. 'baby_liam_01'")
    timestamp: datetime = Field(default_factory=datetime.now)
    volume_ml: float = Field(..., gt=0, le=300, description="Volume ingested in mL")
    feed_type: Literal["breast_milk", "formula", "fortified_breast_milk", "mixed"] = "fortified_breast_milk"
    fortifier: Optional[str] = Field(default=None, description="e.g. 'Similac HMF 24 kcal/oz'")
    duration_minutes: Optional[int] = Field(default=None, ge=0, le=120)
    tolerated: bool = Field(default=True, description="False if baby had spit-up or vomiting")
    notes: Optional[str] = None

    @field_validator("timestamp", mode="after")
    @classmethod
    def strip_timezone(cls, v: datetime) -> datetime:
        if v and getattr(v, "tzinfo", None) is not None:
            return v.replace(tzinfo=None)
        return v


class DiaperEntry(BaseModel):
    """Log entry for diaper changes."""
    entry_id: Optional[str] = None
    baby_id: str
    timestamp: datetime = Field(default_factory=datetime.now)
    wet: bool = Field(default=True, description="Urine present")
    soiled: bool = Field(default=False, description="Stool present")
    stool_color: Optional[Literal[
        "yellow_seedy", "yellow", "brown", "green", "black", "red_blood"
    ]] = Field(default=None, description="Stool color (green/black/red are clinical flags)")
    stool_consistency: Optional[Literal["soft", "liquid", "hard", "mucus"]] = None
    notes: Optional[str] = None

    @field_validator("timestamp", mode="after")
    @classmethod
    def strip_timezone(cls, v: datetime) -> datetime:
        if v and getattr(v, "tzinfo", None) is not None:
            return v.replace(tzinfo=None)
        return v


class MedicationEntry(BaseModel):
    """Log entry for administered medications or vitamins."""
    entry_id: Optional[str] = None
    baby_id: str
    timestamp: datetime = Field(default_factory=datetime.now)
    medication_name: str = Field(..., description="e.g. 'Poly-Vi-Sol with Iron'")
    dose_ml: float = Field(..., gt=0)
    route: Literal["oral", "topical", "nasal"] = "oral"
    notes: Optional[str] = None

    @field_validator("timestamp", mode="after")
    @classmethod
    def strip_timezone(cls, v: datetime) -> datetime:
        if v and getattr(v, "tzinfo", None) is not None:
            return v.replace(tzinfo=None)
        return v
    notes: Optional[str] = None


class CareSummary(BaseModel):
    """Aggregated clinical summary of care over a rolling window (typically 48 hours)."""
    baby_id: str
    period_hours: int = 48
    generated_at: datetime = Field(default_factory=datetime.now)
    total_feeds: int
    total_volume_ml: float
    avg_volume_per_feed_ml: float
    daily_avg_volume_ml: float
    intake_target_status: Literal["adequate", "borderline", "low"]
    wet_diaper_count: int
    soiled_diaper_count: int
    has_spitup_or_vomit: bool
    has_concerning_stool: bool
    concerning_stool_colors: List[str] = []
    clinical_flags: List[str] = []
    summary_paragraph: str
