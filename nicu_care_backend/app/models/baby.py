"""
Pydantic models for baby clinical profiles and corrected gestational age.
"""

from datetime import date, datetime
from typing import Optional, Literal
from pydantic import BaseModel, Field


class BabyProfile(BaseModel):
    """Complete clinical identity of a NICU-discharged infant."""

    baby_id: str = Field(..., description="Unique identifier, e.g. 'baby_liam_01'")
    name: str = Field(..., description="Baby's first name")
    date_of_birth: date = Field(..., description="Actual date of birth")
    gestational_age_weeks: int = Field(
        ..., ge=22, le=42,
        description="Gestational age at birth in completed weeks (e.g. 29)"
    )
    gestational_age_days: int = Field(
        default=0, ge=0, le=6,
        description="Additional days beyond completed weeks (0-6)"
    )
    sex: Literal["male", "female"] = Field(..., description="Biological sex")
    birth_weight_grams: int = Field(
        ..., gt=0,
        description="Weight at birth in grams"
    )
    discharge_weight_grams: int = Field(
        ..., gt=0,
        description="Weight at NICU discharge in grams"
    )
    discharge_date: date = Field(..., description="Date of NICU discharge")
    discharge_hospital: str = Field(
        ...,
        description="Name of the discharging hospital, e.g. 'BirthRight Rainbow Vijayawada'"
    )
    pediatrician_name: Optional[str] = Field(
        default=None,
        description="Name of the follow-up pediatrician"
    )
    mother_preferred_language: str = Field(
        default="en-US",
        description="BCP-47 language tag for the mother's preferred language"
    )
    blood_type: Optional[str] = Field(default=None, description="Blood type, e.g. 'O+'")
    created_at: Optional[datetime] = Field(default=None)


class CorrectedAge(BaseModel):
    """
    Corrected (adjusted) gestational age for a preterm infant.

    Corrected Age = Chronological Age − Weeks Born Early
    """

    baby_id: str
    date_calculated: date

    # Chronological (actual) age
    chronological_days: int = Field(..., description="Days since birth")
    chronological_weeks: int = Field(..., description="Complete weeks since birth")
    chronological_remaining_days: int = Field(..., description="Days beyond complete weeks")

    # How early the baby was born
    weeks_born_early: int = Field(
        ..., description="40 − gestational_age_weeks"
    )
    days_born_early: int = Field(
        ..., description="Total days of prematurity including partial week"
    )

    # Corrected age
    corrected_total_days: int = Field(..., description="Total corrected age in days (can be negative if before due date)")
    corrected_weeks: int = Field(..., description="Corrected age in complete weeks (0 if negative)")
    corrected_remaining_days: int = Field(..., description="Days beyond corrected complete weeks")

    # Clinical note
    note: str = Field(
        ...,
        description="Plain-language explanation for the mother"
    )
    has_reached_due_date: bool = Field(
        ...,
        description="True if baby has passed their original due date"
    )


class GrowthEntry(BaseModel):
    """A single growth measurement (weight, length, or head circumference)."""

    baby_id: str
    measured_at: date
    weight_grams: Optional[int] = Field(default=None, gt=0)
    length_cm: Optional[float] = Field(default=None, gt=0)
    head_circumference_cm: Optional[float] = Field(default=None, gt=0)
    notes: Optional[str] = None


class FeedingPlan(BaseModel):
    """Structured feeding prescription at discharge."""
    method: str = Field(default="Fortified Breast Milk via Paced Bottle or Paladai")
    target_volume_ml_per_day: int = Field(default=380, description="Target daily volume in mL")
    per_feed_ml: str = Field(default="45-54 mL every 2.5 to 3 hours")
    fortification_instructions: Optional[str] = Field(
        default="Human milk fortifier added per pediatrician protocol",
        description="Fortification formula or additive instructions"
    )


class MedicationPrescription(BaseModel):
    """Specific discharge medication or supplement."""
    name: str = Field(..., description="Medication or supplement name, e.g. Iron drops")
    dose: str = Field(..., description="Dose volume or strength, e.g. 1.2 mL")
    frequency: str = Field(..., description="Frequency, e.g. Once daily")
    instructions: Optional[str] = Field(default=None, description="Administration instructions")


class KMCPlan(BaseModel):
    """Individualized Kangaroo Mother Care post-discharge prescription."""
    daily_target_hours: float = Field(default=2.0, ge=1.0, description="Target total KMC hours per day")
    minimum_session_minutes: int = Field(default=60, description="Minimum duration per session")
    position: str = Field(
        default="Upright between breasts, frog-legged, head turned with clear airway",
        description="Prescribed safe positioning"
    )


class FollowUpAppointment(BaseModel):
    """Post-discharge clinical review appointment."""
    clinic_or_specialty: str = Field(..., description="Specialty, e.g. High-Risk Infant Follow-up Clinic")
    scheduled_date: str = Field(..., description="Date or timeframe for appointment")
    notes: Optional[str] = Field(default=None)


class BabyDischargePlan(BaseModel):
    """
    Separated, clinician-approved individual discharge plan for a preterm infant.
    Stored separately from general medical knowledge so patient-specific prescriptions
    are never conflated with general clinical literature.
    """
    baby_id: str = Field(..., description="Unique infant identifier")
    discharge_date: date = Field(..., description="Date of discharge from NICU")
    gestational_age_at_birth: str = Field(..., description="GA at birth, e.g. 29 weeks 2 days")
    birth_weight_g: int = Field(..., gt=0, description="Birth weight in grams")
    discharge_weight_g: int = Field(..., gt=0, description="Weight at discharge in grams")
    feeding_plan: FeedingPlan = Field(default_factory=FeedingPlan)
    medications: list[MedicationPrescription] = Field(default_factory=list)
    kmc_plan: KMCPlan = Field(default_factory=KMCPlan)
    follow_up_appointments: list[FollowUpAppointment] = Field(default_factory=list)
    clinician_approved: bool = Field(default=True, description="Explicit clinician sign-off flag")
    approving_clinician: Optional[str] = Field(
        default="Dr. Rao (Senior Neonatologist)",
        description="Name/designation of approving neonatologist"
    )

