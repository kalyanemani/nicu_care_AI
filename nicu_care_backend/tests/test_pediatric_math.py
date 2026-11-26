"""
Unit tests for PediatricMathService: corrected age, volume targets, and dose validation.
"""

import pytest
from datetime import date, timedelta

from app.models.baby import BabyProfile
from app.services.pediatric_math_service import PediatricMathService


@pytest.fixture
def math_service():
    return PediatricMathService()


@pytest.fixture
def baby_liam():
    """A baby born at 29w2d, 8 weeks ago."""
    return BabyProfile(
        baby_id="baby_liam_01",
        name="Liam",
        date_of_birth=date.today() - timedelta(days=56),  # 8 weeks ago
        gestational_age_weeks=29,
        gestational_age_days=2,
        sex="male",
        birth_weight_grams=1180,
        discharge_weight_grams=1820,
        discharge_date=date.today() - timedelta(days=21),
        discharge_hospital="BirthRight Rainbow Vijayawada",
    )


@pytest.fixture
def baby_near_term():
    """A baby born at 36w0d, 4 weeks ago."""
    return BabyProfile(
        baby_id="baby_mia_01",
        name="Mia",
        date_of_birth=date.today() - timedelta(days=28),  # 4 weeks ago
        gestational_age_weeks=36,
        gestational_age_days=0,
        sex="female",
        birth_weight_grams=2400,
        discharge_weight_grams=2550,
        discharge_date=date.today() - timedelta(days=25),
        discharge_hospital="KIMS Hyderabad",
    )


class TestCorrectedAge:
    """Tests for corrected gestational age calculation."""

    def test_preterm_29_weeker(self, math_service, baby_liam):
        result = math_service.calculate_corrected_age(baby_liam)

        assert result.baby_id == "baby_liam_01"
        assert result.chronological_weeks == 8
        assert result.weeks_born_early == 11  # 40 - 29 = 11

        # Corrected total days = 56 - (11*7 - 2) = 56 - 75 = -19
        # Baby has NOT reached their due date yet
        assert result.corrected_total_days < 0
        assert result.has_reached_due_date is False
        assert result.corrected_weeks == 0
        assert "due date" in result.note.lower()

    def test_near_term_36_weeker(self, math_service, baby_near_term):
        result = math_service.calculate_corrected_age(baby_near_term)

        assert result.chronological_weeks == 4
        assert result.weeks_born_early == 4  # 40 - 36 = 4

        # Corrected total days = 28 - (4*7 - 0) = 28 - 28 = 0
        # Baby is exactly at their due date
        assert result.corrected_total_days >= 0
        assert result.has_reached_due_date is True

    def test_specific_date(self, math_service, baby_liam):
        """Test corrected age calculation for a specific future date."""
        # 100 days after birth
        future_date = baby_liam.date_of_birth + timedelta(days=100)
        result = math_service.calculate_corrected_age(baby_liam, as_of=future_date)

        assert result.chronological_days == 100
        # Corrected = 100 - (11*7 - 2) = 100 - 75 = 25 days = 3w 4d
        assert result.corrected_total_days == 25
        assert result.corrected_weeks == 3
        assert result.corrected_remaining_days == 4
        assert result.has_reached_due_date is True

    def test_note_contains_baby_name(self, math_service, baby_liam):
        result = math_service.calculate_corrected_age(baby_liam)
        assert "Liam" in result.note


class TestDailyVolumeTargets:
    """Tests for feeding volume calculations."""

    def test_2kg_baby(self, math_service):
        result = math_service.calculate_daily_volume_target(2000)

        assert result["current_weight_kg"] == 2.0
        assert result["min_daily_ml"] == 300.0  # 2.0 * 150
        assert result["max_daily_ml"] == 360.0  # 2.0 * 180
        assert result["feeds_per_day"] == 8
        assert result["per_feed_min_ml"] == 37.5
        assert result["per_feed_max_ml"] == 45.0

    def test_1_5kg_baby(self, math_service):
        result = math_service.calculate_daily_volume_target(1500)

        assert result["current_weight_kg"] == 1.5
        assert result["min_daily_ml"] == 225.0
        assert result["max_daily_ml"] == 270.0

    def test_note_is_descriptive(self, math_service):
        result = math_service.calculate_daily_volume_target(1820)
        assert "1820g" in result["note"]
        assert "mL/day" in result["note"]


class TestMedicationDoseValidation:
    """Tests for medication dosage safety checks."""

    def test_safe_iron_dose(self, math_service):
        # 2kg baby, iron max = 6mg/kg/day = 12mg, at 15mg/mL = 0.8 mL max
        result = math_service.validate_medication_dose("iron", 2000, 0.5)
        assert result["is_safe"] is True
        assert result["warning"] is None

    def test_dangerous_iron_dose(self, math_service):
        # 2kg baby, giving 2.0 mL of iron (max is 0.8 mL)
        result = math_service.validate_medication_dose("iron", 2000, 2.0)
        assert result["is_safe"] is False
        assert "DANGER" in result["warning"]
        assert "Do NOT administer" in result["warning"]

    def test_safe_poly_vi_sol_dose(self, math_service):
        result = math_service.validate_medication_dose("poly_vi_sol_with_iron", 2000, 1.0)
        assert result["is_safe"] is True

    def test_excessive_poly_vi_sol_dose(self, math_service):
        result = math_service.validate_medication_dose("poly_vi_sol_with_iron", 2000, 2.5)
        assert result["is_safe"] is False

    def test_unknown_drug(self, math_service):
        result = math_service.validate_medication_dose("some_unknown_drug", 2000, 1.0)
        assert result["is_safe"] is None
        assert "not in validation database" in result["warning"]
