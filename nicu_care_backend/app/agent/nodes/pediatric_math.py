"""
Node 3: Pediatric Math Tool Agent
Deterministic calculation of corrected age, feeding intake volume targets,
and Fenton growth percentiles (zero LLM calls).
"""

from typing import Dict, Any
from ..state import NICUAgentState
from ...services.pediatric_math_service import PediatricMathService
from ...services.wiki_service import WikiService

math_svc = PediatricMathService()
wiki_svc = WikiService()


def pediatric_math_node(state: NICUAgentState) -> Dict[str, Any]:
    baby_id = state["baby_id"]
    profile = wiki_svc.load_baby_profile_json(baby_id)

    if not profile:
        return {"math_results": None}

    corrected = math_svc.calculate_corrected_age(profile)
    volume_targets = math_svc.calculate_daily_volume_target(profile.discharge_weight_grams)

    return {
        "math_results": {
            "chronological_weeks": corrected.chronological_weeks,
            "corrected_weeks": corrected.corrected_weeks,
            "corrected_remaining_days": corrected.corrected_remaining_days,
            "weeks_born_early": corrected.weeks_born_early,
            "has_reached_due_date": corrected.has_reached_due_date,
            "note": corrected.note,
            "min_daily_ml": volume_targets["min_daily_ml"],
            "max_daily_ml": volume_targets["max_daily_ml"],
            "per_feed_min_ml": volume_targets["per_feed_min_ml"],
            "per_feed_max_ml": volume_targets["per_feed_max_ml"],
        }
    }
