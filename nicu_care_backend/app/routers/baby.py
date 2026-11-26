"""
Baby profile and corrected age API endpoints.
"""

from datetime import date, datetime
from typing import Optional
from fastapi import APIRouter, HTTPException

from ..models.baby import BabyProfile, CorrectedAge, GrowthEntry
from ..services.pediatric_math_service import PediatricMathService
from ..services.wiki_service import WikiService

router = APIRouter(prefix="/api/v1/baby", tags=["Baby Profile & Corrected Age"])

math_service = PediatricMathService()
wiki_service = WikiService()


@router.post("/register", response_model=BabyProfile, status_code=201)
def register_baby(baby: BabyProfile):
    """
    Registers a new baby profile.
    Creates the Baby Health Wiki (profile.md) and persists the profile as JSON.
    """
    # Check if baby already exists
    existing = wiki_service.load_baby_profile_json(baby.baby_id)
    if existing:
        raise HTTPException(status_code=409, detail=f"Baby '{baby.baby_id}' already registered.")

    # Stamp creation time
    baby.created_at = datetime.now()

    # Persist JSON profile and generate wiki
    wiki_service.save_baby_profile_json(baby)
    wiki_service.create_profile_from_baby(baby)

    # Create placeholder wiki sections
    wiki_service.write_section(
        baby.baby_id,
        "active_regimen",
        f"# Active Regimen for {baby.name}\n\n*No regimen configured yet. Update after pediatrician visit.*"
    )
    wiki_service.write_section(
        baby.baby_id,
        "clinical_alerts",
        f"# Clinical Alerts for {baby.name}\n\n*No known alerts. Update if any conditions are diagnosed.*"
    )
    wiki_service.write_section(
        baby.baby_id,
        "rolling_log_summary",
        f"# Care Log Summary for {baby.name}\n\n*No entries yet.*"
    )

    return baby


@router.get("/{baby_id}/profile", response_model=BabyProfile)
def get_baby_profile(baby_id: str):
    """Returns the full clinical profile for a registered baby."""
    baby = wiki_service.load_baby_profile_json(baby_id)
    if not baby:
        raise HTTPException(status_code=404, detail=f"Baby '{baby_id}' not found.")
    return baby


@router.get("/{baby_id}/corrected-age", response_model=CorrectedAge)
def get_corrected_age(baby_id: str, as_of: Optional[date] = None):
    """
    Calculates the corrected gestational age for a baby.

    Query Parameters
    ----------------
    as_of : date, optional
        Calculate as of a specific date. Defaults to today.
    """
    baby = wiki_service.load_baby_profile_json(baby_id)
    if not baby:
        raise HTTPException(status_code=404, detail=f"Baby '{baby_id}' not found.")

    corrected = math_service.calculate_corrected_age(baby, as_of=as_of)
    return corrected


@router.get("/{baby_id}/feeding-targets")
def get_feeding_targets(baby_id: str, current_weight_grams: Optional[int] = None):
    """
    Calculates the daily feeding volume target based on the baby's current weight.

    Query Parameters
    ----------------
    current_weight_grams : int, optional
        Baby's current weight. Defaults to discharge weight.
    """
    baby = wiki_service.load_baby_profile_json(baby_id)
    if not baby:
        raise HTTPException(status_code=404, detail=f"Baby '{baby_id}' not found.")

    weight = current_weight_grams or baby.discharge_weight_grams
    targets = math_service.calculate_daily_volume_target(weight)
    return targets


@router.get("/{baby_id}/validate-dose")
def validate_medication_dose(
    baby_id: str,
    drug_name: str,
    proposed_dose_ml: float,
    current_weight_grams: Optional[int] = None,
):
    """
    Validates a proposed medication dose against safe upper limits.

    Query Parameters
    ----------------
    drug_name : str
        Name of the medication (e.g., 'iron', 'vitamin_d', 'caffeine_citrate').
    proposed_dose_ml : float
        The dose in mL the mother intends to give.
    current_weight_grams : int, optional
        Baby's current weight. Defaults to discharge weight.
    """
    baby = wiki_service.load_baby_profile_json(baby_id)
    if not baby:
        raise HTTPException(status_code=404, detail=f"Baby '{baby_id}' not found.")

    weight = current_weight_grams or baby.discharge_weight_grams
    result = math_service.validate_medication_dose(drug_name, weight, proposed_dose_ml)
    return result


@router.get("/list/all")
def list_all_babies():
    """Lists all registered baby IDs."""
    babies = wiki_service.list_babies()
    return {"babies": babies, "count": len(babies)}
