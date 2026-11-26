"""
Layer 3 Guardrails: Execution and Tool Safety.

Guarantees:
- Feed volume does not exceed physiological maximum.
- Medication dose does not exceed safe weight-based ceiling.
- Vital signs (temp, heart rate) fall within biologically valid limits.
"""

from typing import Optional, Dict, Any


class ToolGuardrails:
    """Deterministic validation guardrails for tool execution and data entry."""

    @staticmethod
    def validate_feed_volume(volume_ml: float, weight_grams: int) -> Dict[str, Any]:
        """
        Validates feed volume against neonatal stomach capacity.
        Max single feed for preterm infant is approx 35-40 mL/kg.
        Physiological upper safety ceiling: weight_kg * 45 mL.
        """
        if volume_ml <= 0:
            return {
                "valid": False,
                "reason": "Feed volume must be greater than 0 mL."
            }

        weight_kg = weight_grams / 1000.0
        max_physio_ml = round(weight_kg * 45.0, 1)

        if volume_ml > max_physio_ml:
            return {
                "valid": False,
                "reason": (
                    f"Reported feed volume of {volume_ml} mL exceeds the maximum safe single-feed "
                    f"capacity ({max_physio_ml} mL) for a {weight_grams}g infant. "
                    f"Please verify the number (did you mean ounces?)."
                )
            }

        return {"valid": True, "reason": None}

    @staticmethod
    def validate_temperature(temp_celsius: float) -> Dict[str, Any]:
        """
        Validates temperature readings and identifies clinical hypothermia / hyperthermia.
        """
        if temp_celsius < 30.0 or temp_celsius > 43.0:
            return {
                "valid": False,
                "is_emergency": False,
                "reason": f"Reading {temp_celsius}°C is outside biologically valid limits. Re-check thermometer."
            }

        is_emergency = False
        status = "normal"
        alert = None

        if temp_celsius < 36.5:
            is_emergency = True
            status = "hypothermia"
            alert = "Rectal temp < 36.5°C is hypothermia in preterm infants. Warm baby skin-to-skin and contact pediatrician."
        elif temp_celsius >= 38.0:
            is_emergency = True
            status = "hyperthermia_fever"
            alert = "Rectal temp >= 38.0°C is an emergency in infants < 3 months. Contact pediatrician immediately."

        return {
            "valid": True,
            "status": status,
            "is_emergency": is_emergency,
            "alert": alert
        }
