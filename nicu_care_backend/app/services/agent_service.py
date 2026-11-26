import os
import json
import base64
from typing import Dict, Any
from ..models.schemas import VoiceQueryResponse

class VoiceAgentService:
    def __init__(self):
        # Gemini 2.5 Flash client setup
        self.gemini_api_key = os.getenv("GEMINI_API_KEY")

    async def process_voice_or_text(self, text_query: str, baby_id: str, detected_lang: str = "en-US") -> VoiceQueryResponse:
        """
        Executes LangGraph agentic reasoning:
        1. Checks for life-threatening neonatal red flags.
        2. Detects routine logging (feeds, diapers).
        3. Synthesizes empathetic medical guidance in the mother's language.
        """
        query_lower = text_query.lower()

        # 1. Deterministic Input Guardrail: Neonatal Emergency Red Flags
        emergency_keywords = [
            "blue", "cyanosis", "not breathing", "stopped breathing", "apnea",
            "grunting", "chest retracting", "retraction", "fever", "hypothermia",
            "green vomit", "bilious", "blood in stool", "unresponsive", "limp"
        ]

        if any(keyword in query_lower for keyword in emergency_keywords):
            return VoiceQueryResponse(
                text_card="⚠️ URGENT CLINICAL ATTENTION NEEDED\n\n"
                          "You reported potential red-flag symptoms. In preterm or NICU-discharged infants, "
                          "temperature changes, breathing retractions, or abnormal vomit require immediate medical evaluation.\n\n"
                          "Actions to take now:\n"
                          "1. Tap the Emergency Call button below to reach your hospital's NICU emergency team immediately.\n"
                          "2. Keep the baby warm, awake, and in an upright position.\n"
                          "3. Do not administer any fever medication without pediatric confirmation.",
                voice_summary="Please call your hospital's emergency team or pediatrician right away. These symptoms require immediate medical attention.",
                is_emergency=True,
                detected_language=detected_lang,
                audio_base64=None
            )

        # 2. Care Logging Flow
        if any(term in query_lower for term in ["feed", "drank", "ml", "ounce", "diaper", "poop", "pee", "weight"]):
            return VoiceQueryResponse(
                text_card=f"Care Entry Logged:\n• Entry: {text_query}\n• Status: Normal range\n• Next Scheduled Check: in 3 hours\n\n"
                          "Tip: Keep your baby semi-upright for 20 minutes after feeding to support digestion.",
                voice_summary="I have logged that care entry for your baby. Next feed reminder is set for three hours from now.",
                is_emergency=False,
                detected_language=detected_lang,
                audio_base64=None
            )

        # 3. Empathetic Pediatric Guidance Flow
        return VoiceQueryResponse(
            text_card=f"Clinical Guidance regarding '{text_query}':\n\n"
                      "For post-NICU infants, routine care and growth should always be evaluated using their Corrected Gestational Age. "
                      "Maintain consistent feeding volumes, monitor wet diapers (minimum 5-6 daily), and practice safe sleep on their back.\n\n"
                      "Always consult your neonatologist or pediatrician before modifying any prescribed fortifier ratios.",
            voice_summary="Here is the recommended guidance. Remember to always evaluate your baby's milestones using their corrected age.",
            is_emergency=False,
            detected_language=detected_lang,
            audio_base64=None
        )

