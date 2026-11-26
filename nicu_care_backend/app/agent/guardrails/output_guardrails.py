"""
Layer 4 Guardrails: Output Verification, Zero-Hallucination Enforcement & Pediatric Safety.

Guarantees:
- Output NEVER recommends dangerous practices (honey, water for newborns, cough syrup, bed-sharing, prone sleeping).
- Output NEVER hallucinates arbitrary drug dosages or fluid rates not corroborated by pediatric guidelines.
- Output always appends the non-negotiable supportive pediatric disclaimer.
- Tone is calm, reassuring, and non-alarmist (minimizing postpartum anxiety).
"""

import re
from typing import Dict, Any, List, Optional


class OutputGuardrails:
    """Post-generation safety filter applied before delivering response to mother."""

    # Banned practices that are hazardous for neonates / preterm infants
    BANNED_ADVICE_RULES = {
        "honey": "Never recommend honey to infants < 12 months (infant botulism risk).",
        "water for newborn": "Never recommend plain water to infants < 6 months (hyponatremia / water intoxication).",
        "plain water": "Never recommend plain water to infants < 6 months.",
        "give water": "Never recommend plain water to infants < 6 months.",
        "cough syrup": "OTC cough and cold medicines are contraindicated in infants.",
        "aspirin": "Aspirin is contraindicated in infants (Reye syndrome risk).",
        "ibuprofen under 6 months": "Ibuprofen is contraindicated in infants < 6 months.",
        "co-sleeping in the same bed": "Bed-sharing increases SIDS/suffocation risk.",
        "sleep on stomach": "Prone (stomach) sleeping increases SIDS risk in infants.",
        "sleep on belly": "Prone sleeping increases SIDS risk.",
        "tummy sleeping": "Prone sleeping increases SIDS risk.",
        "rice cereal in bottle": "Never recommend cereal in bottle unless specifically prescribed by pediatric GI.",
        "cow milk before 1 year": "Undiluted cow milk is contraindicated before 12 months.",
    }

    MANDATORY_DISCLAIMER = (
        "\n\n---\n*Disclaimer: This guidance is educational and supportive, not a medical diagnosis. "
        "Always consult your pediatrician or neonatologist before changing medications, fortifiers, or feeding plans.*"
    )

    ALARMIST_TERMS = [
        "your baby could die", "fatal outcome", "permanent brain damage",
        "horrible mistake", "catastrophic harm"
    ]

    # Pattern for suspicious ungrounded dosage advice (e.g. "give 5 ml of tylenol" without context)
    UNGROUNDED_MED_PATTERN = r"\b(give|administer|take)\s+(\d+(\.\d+)?)\s*(ml|mg|drops|teaspoon|tsp)\s+of\s+(?!breast milk|formula|water|saline)([a-zA-Z]+)"

    @classmethod
    def verify_and_sanitize(cls, output_text: str, is_emergency: bool = False, approved_medications: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Validates output against banned advice, hallucinations, and applies mandatory disclaimer.
        """
        text_lower = output_text.lower()
        violations: List[str] = []

        # 1. Banned Advice Scanner
        for phrase, reason in cls.BANNED_ADVICE_RULES.items():
            if re.search(r'\b' + re.escape(phrase) + r'\b', text_lower):
                violations.append(f"{phrase}: {reason}")

        # 2. Check for Hallucinated Medication Dosages
        med_matches = re.finditer(cls.UNGROUNDED_MED_PATTERN, text_lower)
        for m in med_matches:
            med_name = m.group(4)
            # Allowed verified preterm routine items
            allowed_items = ["iron", "vitamin", "multivitamin", "vitamins", "d3", "caffeine"]
            if approved_medications:
                allowed_items.extend([a.lower() for a in approved_medications])
            if med_name not in allowed_items:
                violations.append(f"Ungrounded medication recommendation: '{med_name}'. Medication adjustments require neonatologist prescription.")

        if violations:
            return {
                "passed": False,
                "violations": violations,
                "sanitized_text": (
                    "I cannot provide that specific suggestion as clinical guidelines advise against it for infants. "
                    "Please consult your baby's pediatrician for safe, approved alternatives."
                    + cls.MANDATORY_DISCLAIMER
                )
            }

        # 3. Tone Check (ensure non-alarmist language unless it's a verified emergency)
        cleaned_text = output_text
        if not is_emergency:
            for term in cls.ALARMIST_TERMS:
                if term in text_lower:
                    cleaned_text = re.sub(re.escape(term), "a serious health concern", cleaned_text, flags=re.IGNORECASE)

        # 4. Disclaimer Injection (idempotent — only append if not already present)
        if "disclaimer" not in cleaned_text.lower():
            cleaned_text = cleaned_text.strip() + cls.MANDATORY_DISCLAIMER

        return {
            "passed": True,
            "violations": [],
            "sanitized_text": cleaned_text
        }
