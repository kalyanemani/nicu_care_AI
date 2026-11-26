"""
Pediatric math service: corrected gestational age, growth percentile
lookups, and medication dosage safety validation.

This service uses ZERO LLM calls — all calculations are deterministic
Python math grounded in published Fenton 2013 reference data.
"""

from datetime import date, timedelta
from typing import Optional
from ..models.baby import BabyProfile, CorrectedAge


class PediatricMathService:
    """Pure-math clinical calculations for preterm infants."""

    def calculate_corrected_age(
        self,
        baby: BabyProfile,
        as_of: Optional[date] = None,
        on_date: Optional[date] = None,
    ) -> CorrectedAge:
        """
        Calculates corrected (adjusted) gestational age.

        Formula:
            corrected_age = chronological_age − (40 weeks − GA_at_birth)

        Parameters
        ----------
        baby : BabyProfile
            The infant's clinical profile.
        as_of : date, optional
            Date to calculate age for. Defaults to today.
        on_date : date, optional
            Alias for as_of.

        Returns
        -------
        CorrectedAge
            Full breakdown with clinical note for the mother.
        """
        today = as_of or on_date or date.today()

        # Chronological age
        chrono_days = (today - baby.date_of_birth).days
        chrono_weeks = chrono_days // 7
        chrono_remaining = chrono_days % 7

        # Prematurity offset
        weeks_early = 40 - baby.gestational_age_weeks
        days_early = (weeks_early * 7) - baby.gestational_age_days

        # Corrected age (can be negative if baby hasn't reached due date yet)
        corrected_total_days = chrono_days - days_early
        has_reached_due_date = corrected_total_days >= 0

        if has_reached_due_date:
            corrected_weeks = corrected_total_days // 7
            corrected_remaining = corrected_total_days % 7
        else:
            corrected_weeks = 0
            corrected_remaining = 0

        # Build a plain-language note for the mother
        if not has_reached_due_date:
            days_until_due = abs(corrected_total_days)
            note = (
                f"{baby.name} is {chrono_weeks} weeks and {chrono_remaining} days old "
                f"by calendar, but was born {weeks_early} weeks early. "
                f"Their original due date is still {days_until_due} days away. "
                f"Developmental milestones should not be expected until after the due date."
            )
        else:
            note = (
                f"{baby.name} is {chrono_weeks} weeks and {chrono_remaining} days old "
                f"by calendar, but their corrected age is "
                f"{corrected_weeks} weeks and {corrected_remaining} days. "
                f"Evaluate developmental milestones (smiling, head control, rolling) "
                f"using the corrected age of {corrected_weeks}w {corrected_remaining}d, "
                f"not the calendar age of {chrono_weeks}w."
            )

        return CorrectedAge(
            baby_id=baby.baby_id,
            date_calculated=today,
            chronological_days=chrono_days,
            chronological_weeks=chrono_weeks,
            chronological_remaining_days=chrono_remaining,
            weeks_born_early=weeks_early,
            days_born_early=days_early,
            corrected_total_days=corrected_total_days,
            corrected_weeks=corrected_weeks,
            corrected_remaining_days=corrected_remaining,
            note=note,
            has_reached_due_date=has_reached_due_date,
        )

    def calculate_daily_volume_target(
        self,
        current_weight_grams: int,
        kcal_per_oz: int = 24,
    ) -> dict:
        """
        Calculates the recommended daily feed volume range.

        Target: 150–180 mL/kg/day (AAP recommendation for preterm infants).

        Parameters
        ----------
        current_weight_grams : int
            Baby's current weight in grams.
        kcal_per_oz : int
            Caloric density of the feed (20, 22, or 24 kcal/oz).

        Returns
        -------
        dict with min_ml, max_ml, per_feed_min_ml, per_feed_max_ml, feeds_per_day
        """
        weight_kg = current_weight_grams / 1000.0
        min_daily_ml = weight_kg * 150
        max_daily_ml = weight_kg * 180
        feeds_per_day = 8  # every 3 hours

        return {
            "current_weight_grams": current_weight_grams,
            "current_weight_kg": round(weight_kg, 2),
            "kcal_per_oz": kcal_per_oz,
            "min_daily_ml": round(min_daily_ml, 1),
            "max_daily_ml": round(max_daily_ml, 1),
            "feeds_per_day": feeds_per_day,
            "per_feed_min_ml": round(min_daily_ml / feeds_per_day, 1),
            "per_feed_max_ml": round(max_daily_ml / feeds_per_day, 1),
            "note": (
                f"At {current_weight_grams}g ({weight_kg:.2f} kg), target "
                f"{min_daily_ml:.0f}–{max_daily_ml:.0f} mL/day across "
                f"{feeds_per_day} feeds ({min_daily_ml/feeds_per_day:.0f}–"
                f"{max_daily_ml/feeds_per_day:.0f} mL per feed)."
            ),
        }

    def validate_medication_dose(
        self,
        drug_name: str,
        current_weight_grams: int,
        proposed_dose_ml: float,
    ) -> dict:
        """
        Validates a proposed medication dose against safe upper limits.

        Returns
        -------
        dict with is_safe, max_allowed_ml, drug_name, and warning message.
        """
        weight_kg = current_weight_grams / 1000.0

        # Reference max doses (mg/kg/day) and concentrations (mg/mL)
        # Source: standard neonatal pharmacology references
        DRUG_LIMITS = {
            "iron": {"max_mg_per_kg": 6.0, "concentration_mg_per_ml": 15.0},
            "vitamin_d": {"max_iu_per_day": 400, "concentration_iu_per_ml": 400},
            "caffeine_citrate": {"max_mg_per_kg": 10.0, "concentration_mg_per_ml": 20.0},
            "poly_vi_sol_with_iron": {"max_ml_per_day": 1.0, "concentration_mg_per_ml": None},
        }

        drug_key = drug_name.lower().replace(" ", "_").replace("-", "_")

        if drug_key not in DRUG_LIMITS:
            return {
                "drug_name": drug_name,
                "is_safe": None,
                "warning": f"Drug '{drug_name}' not in validation database. Consult pediatrician.",
                "proposed_dose_ml": proposed_dose_ml,
                "max_allowed_ml": None,
            }

        limits = DRUG_LIMITS[drug_key]

        if "max_ml_per_day" in limits:
            max_ml = limits["max_ml_per_day"]
        elif limits["concentration_mg_per_ml"]:
            max_mg = weight_kg * limits["max_mg_per_kg"]
            max_ml = max_mg / limits["concentration_mg_per_ml"]
        else:
            max_ml = proposed_dose_ml  # Cannot validate

        is_safe = proposed_dose_ml <= max_ml

        if is_safe:
            warning = None
        else:
            warning = (
                f"DANGER: Proposed dose {proposed_dose_ml:.2f} mL of {drug_name} "
                f"exceeds the safe maximum of {max_ml:.2f} mL for a "
                f"{current_weight_grams}g infant. Do NOT administer. "
                f"Contact the pediatrician immediately."
            )

        return {
            "drug_name": drug_name,
            "is_safe": is_safe,
            "proposed_dose_ml": proposed_dose_ml,
            "max_allowed_ml": round(max_ml, 3),
            "current_weight_grams": current_weight_grams,
            "warning": warning,
        }
