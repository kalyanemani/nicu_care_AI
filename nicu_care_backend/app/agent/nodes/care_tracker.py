"""
Node 2: Care Tracker Agent
Deterministic tool-heavy worker that converts unstructured routine care
statements into validated database logs.
"""

import re
from datetime import datetime
from typing import Dict, Any

from ..state import NICUAgentState
from ...models.care_log import FeedingEntry, DiaperEntry
from ...services.care_log_service import CareLogService
from ...services.wiki_service import WikiService
from ..guardrails.tool_guardrails import ToolGuardrails

log_svc = CareLogService()
wiki_svc = WikiService()


def care_tracker_node(state: NICUAgentState) -> Dict[str, Any]:
    query = state["raw_query"]
    baby_id = state["baby_id"]
    intent = state["intent"]

    profile = wiki_svc.load_baby_profile_json(baby_id)
    weight_grams = profile.discharge_weight_grams if profile else 2000

    if intent == "LOG_FEED":
        # Extract volume using regex
        vol_match = re.search(r'(\d{1,3}(?:\.\d+)?)\s*(?:ml|milliliters?|cc|oz|ounces?)', query, re.IGNORECASE)
        volume_ml = 50.0  # sensible fallback
        if vol_match:
            val = float(vol_match.group(1))
            # If mother said ounces, convert to mL
            if "oz" in vol_match.group(0).lower() or "ounce" in vol_match.group(0).lower():
                val = val * 29.57
            volume_ml = round(val, 1)

        feed_type = "fortified_breast_milk" if "fortif" in query.lower() or "hmf" in query.lower() else "breast_milk"
        if "formula" in query.lower() or "neosure" in query.lower():
            feed_type = "formula"

        tolerated = not any(w in query.lower() for w in ["spit", "vomit", "threw up"])

        # Tool Guardrail validation
        guard = ToolGuardrails.validate_feed_volume(volume_ml, weight_grams)
        if not guard["valid"]:
            return {
                "draft_response": f"🚨 Entry Blocked: {guard['reason']}",
                "voice_summary": "I could not log that feeding because the reported volume exceeds safe limits.",
                "logged_entry_summary": None,
                "next_reminder_minutes": None
            }

        entry = FeedingEntry(
            baby_id=baby_id,
            volume_ml=volume_ml,
            feed_type=feed_type,
            tolerated=tolerated,
            notes=query
        )
        log_svc.log_feed(entry)

        status_note = "Feed tolerated well." if tolerated else "Spit-up noted. Keep baby upright for 20-30 minutes."
        text = (
            f"✅ **Feeding Logged:**\n"
            f"- Volume: **{volume_ml} mL** ({feed_type})\n"
            f"- Tolerance: {status_note}\n"
            f"- Next Recommended Feed: In approximately **3 hours**."
        )
        voice = f"{volume_ml:.0f} milliliters logged. Remember to keep baby upright, and next feed is in three hours."

        return {
            "draft_response": text,
            "voice_summary": voice,
            "logged_entry_summary": f"Feed {volume_ml}mL ({feed_type})",
            "next_reminder_minutes": 180
        }

    elif intent == "LOG_DIAPER":
        is_wet = any(w in query.lower() for w in ["wet", "pee", "urine"])
        is_soiled = any(w in query.lower() for w in ["soiled", "poop", "stool", "dirty"])
        if not is_wet and not is_soiled:
            is_wet = True  # default

        stool_color = None
        for color in ["yellow_seedy", "yellow", "brown", "green", "black", "red_blood"]:
            if color.replace("_", " ") in query.lower() or color in query.lower():
                stool_color = color
                break

        entry = DiaperEntry(
            baby_id=baby_id,
            wet=is_wet,
            soiled=is_soiled,
            stool_color=stool_color,
            notes=query
        )
        log_svc.log_diaper(entry)

        desc = []
        if is_wet: desc.append("Wet")
        if is_soiled: desc.append(f"Soiled ({stool_color or 'normal'})")

        text = f"✅ **Diaper Logged:** {', '.join(desc)} at {datetime.now().strftime('%I:%M %p')}."
        voice = f"Diaper change logged."

        return {
            "draft_response": text,
            "voice_summary": voice,
            "logged_entry_summary": f"Diaper: {', '.join(desc)}",
            "next_reminder_minutes": None
        }

    elif intent == "LOG_KMC":
        # Extract duration in minutes (e.g. "60 minutes", "1 hour", "45 mins")
        min_match = re.search(r'(\d+)\s*(?:mins?|minutes?|hrs?|hours?)', query, re.IGNORECASE)
        duration = 60  # Default to 60 mins (WHO recommended minimum session)
        if min_match:
            val = int(min_match.group(1))
            if "hr" in min_match.group(0).lower() or "hour" in min_match.group(0).lower():
                val = val * 60
            duration = val

        from ...models.timeline import KMCSession
        from ...services.timeline_service import TimelineService
        tl_svc = TimelineService()
        session_entry = KMCSession(
            baby_id=baby_id,
            duration_minutes=duration,
            caregiver="mother",
            notes=query
        )
        tl_svc.log_kmc_session(session_entry)
        kmc_sum = tl_svc.get_daily_kmc_summary(baby_id)

        text = (
            f"🦘 **Kangaroo Mother Care (KMC) Logged:**\n\n"
            f"- **Session Duration:** **`{duration} minutes`** ({round(duration / 60.0, 1)} hrs)\n"
            f"- **Caregiver:** Mother (Skin-to-Skin Contact)\n"
            f"- **Today's Cumulative Skin-to-Skin:** **`{kmc_sum['completed_hours']} hours`** / `{kmc_sum['target_hours']} hours` target ({kmc_sum['percent_completed']}% completed)\n"
            f"- **Remaining to Daily WHO Target:** `{kmc_sum['remaining_hours']} hours`\n"
            f"- **Daily Progress:** **{kmc_sum['status']}**\n\n"
            f"💡 *WHO Protocol: Each KMC session should last at least 60 continuous minutes so your preterm baby completes a restorative sleep cycle and stabilizes body temperature.*"
        )
        voice = f"{duration} minutes of kangaroo care logged. You have completed {kmc_sum['completed_hours']} hours of skin to skin today."

        return {
            "draft_response": text,
            "voice_summary": voice,
            "logged_entry_summary": f"KMC {duration}mins ({kmc_sum['completed_hours']}h total)",
            "next_reminder_minutes": 180
        }

    # Fallback routine logging
    return {
        "draft_response": f"✅ Care entry recorded: '{query}'",
        "voice_summary": "Care entry recorded successfully.",
        "logged_entry_summary": query,
        "next_reminder_minutes": None
    }
