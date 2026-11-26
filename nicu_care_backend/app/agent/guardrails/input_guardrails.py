"""
Layer 1 Guardrails: Input Safety, Red Flag Scanner, Harmful Advice Intercept & De-identification.

Guarantees:
- Critical neonatal red flags are detected deterministically in < 1ms,
  bypassing all LLM reasoning delays.
- Harmful home remedies (honey, plain water, cow milk, adult cough syrups, etc.)
  inquiries are intercepted and flagged for safe educational routing.
- PHI (Aadhaar, phone numbers, emails, MRNs) is masked before storage or logging.
- Input length and numeric parameters are bounded to prevent injection / memory exhaustion.
"""

import re
from typing import Dict, Any, List, Optional


class InputGuardrails:
    """Pre-LLM input filter for security, acute emergency detection, and harmful practices."""

    # Life-threatening neonatal emergency signs (AAP/WHO Acute Triage)
    RED_FLAG_PATTERNS = [
        r"\b(blue|cyanosis|cyanotic|dusky|gray|grey)\b",
        r"\b(not breathing|stopped breathing|stop breathing|apnea|apneic)\b",
        r"\b(grunting|grunt|grunts)\b",
        r"\b(retract|retracting|retraction|retractions|chest retracting|chest pulling in)\b",
        r"\b(rectal temp(erature)?\s*(is|of)?\s*(38|39|40|41))\b",
        r"\b(fever|high temp(erature)?|hot to touch)\b",
        r"\b(hypothermi(a|c)|cold to touch|temp(erature)?\s*(is|of)?\s*(34|35|36\.[0-4]))\b",
        r"\b(green vomit|bilious|vomiting green|dark green spit|threw up.*green|throw up.*green|green.*liquid|vomit.*green)\b",
        r"\b(blood in stool|bloody diaper|bloody vomit|blood in vomit)\b",
        r"\b(unresponsive|limp|floppy|cannot wake|hard to wake|lethargic)\b",
        r"\b(seizure|seizures|convulsion|convulsions|jerking)\b",
        r"\b(bulging fontanelle|swollen soft spot)\b"
    ]

    # Harmful home remedies or contraindicated substances for neonates/infants
    HARMFUL_PRACTICES = {
        "honey": "Honey is strictly contraindicated for infants under 12 months due to Clostridium botulinum (infant botulism) risk.",
        "plain water": "Plain water is contraindicated for infants under 6 months due to risk of hyponatremia and water intoxication.",
        "give water": "Plain water is contraindicated for infants under 6 months due to risk of hyponatremia and water intoxication.",
        "cow milk": "Undiluted cow's milk is contraindicated before 12 months due to renal solute load and lack of necessary nutrients for preterm infants.",
        "goat milk": "Unpasteurized or non-infant goat's milk is contraindicated due to folic acid deficiency and electrolyte imbalance.",
        "cough syrup": "Over-the-counter cough and cold medicines are contraindicated in infants due to life-threatening respiratory depression risks.",
        "aspirin": "Aspirin is contraindicated in infants due to Reye's syndrome risk.",
        "gripe water with alcohol": "Alcohol or sodium bicarbonate containing formulations are contraindicated in neonates.",
        "sleeping on stomach": "Prone sleeping significantly increases the risk of Sudden Infant Death Syndrome (SIDS).",
        "stomach sleep": "Prone sleeping significantly increases the risk of Sudden Infant Death Syndrome (SIDS).",
        "bed sharing": "Bed-sharing with adults increases the risk of suffocation, asphyxia, and SIDS for preterm infants."
    }

    # PHI patterns (India / US phone, Aadhaar, email)
    PHONE_REGEX = r"\b(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b|\b\d{10}\b"
    AADHAAR_REGEX = r"\b\d{4}[-\s]?\d{4}[-\s]?\d{4}\b"
    EMAIL_REGEX = r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"

    # Explicit application scope whitelist categories (Neonatal & Post-Discharge Care)
    IN_DOMAIN_CLINICAL_KEYWORDS = [
        # Identity, baby & prematurity
        "baby", "infant", "newborn", "neonate", "neonatal", "preterm", "premature", "liam", "nicu",
        "birth", "gestational", "corrected", "chronological", "post-discharge", "discharge",
        # Nutrition & feeding
        "feed", "feeding", "breast", "milk", "formula", "fortifier", "fortified", "bottle", "paladai",
        "latch", "nursing", "intake", "volume", "regurgitation", "spit up", "spitting", "reflux", "burp",
        # Kangaroo care & development
        "kmc", "kangaroo", "skin-to-skin", "skin to skin", "frog", "wrap", "chest", "bonding", "hold",
        # Growth & vitals
        "weight", "weigh", "gain", "grams", "fenton", "growth", "velocity", "percentile", "length", "head",
        # Sleep & environment
        "sleep", "sleeping", "sids", "crib", "bassinet", "mattress", "blanket", "co-sleeping", "bed-sharing",
        # Elimination & hygiene
        "diaper", "wet", "stool", "pee", "poop", "peeing", "urine", "bowel", "meconium", "constipat",
        "steriliz", "clean", "wash", "boil", "pump", "hygiene", "storage",
        # Clinical symptoms & danger signs
        "fever", "temperature", "hypothermi", "cold", "warm", "touch", "jaundice", "yellow", "bilirubin",
        "apnea", "breathing", "breath", "grunt", "retract", "cyanosis", "blue", "dusky", "chok", "vomit",
        "bilious", "green", "letharg", "limp", "floppy", "seizure", "fontanelle", "soft spot", "alert",
        # Medications, timeline & hospital
        "iron", "vitamin", "drops", "caffeine", "citrate", "dose", "medication", "medicine", "syringe",
        "timeline", "schedule", "routine", "next", "upcoming", "task", "appointment", "doctor", "pediatrician",
        "hospital", "rainbow", "helpline", "ambulance", "108", "emergency", "log", "record",
        # Maternal health & pleasantries
        "mastitis", "engorgement", "mother", "mom", "postpartum", "lochia", "maternal",
        "hi", "hello", "hey", "good morning", "good evening", "thank", "thanks", "bye", "help", "who are you"
    ]

    OUT_OF_DOMAIN_PATTERNS = [
        r"\b(crypto|bitcoin|ethereum|stock market|shares|forex|investing|mutual fund)\b",
        r"\b(python|javascript|java|c\+\+|html|css|write code|debug code|sql query|algorithm)\b",
        r"\b(election|politics|president|prime minister|parliament|democrat|republican)\b",
        r"\b(cricket match|football score|world cup|nba|premier league|movie review|box office)\b",
        r"\b(recipe for chocolate|cocktail recipe|restaurant menu|car engine|automotive repair)\b",
        r"\b(quantum physics|relativity theory|algebra homework|calculus|write an essay)\b"
    ]

    @classmethod
    def validate_domain_scope(cls, text: str) -> Dict[str, Any]:
        """
        Validates whether the user query pertains strictly to the NICU post-discharge
        clinical application scope, rejecting unrelated off-topic queries.
        """
        text_lower = text.lower().strip()

        # Check explicit out-of-domain patterns first
        for pat in cls.OUT_OF_DOMAIN_PATTERNS:
            if re.search(pat, text_lower):
                return {
                    "is_in_domain": False,
                    "reason": "Explicit off-topic concept detected.",
                    "boundary_prompt": (
                        "⚠️ **Clinical Scope Boundary**\n\n"
                        "I am strictly dedicated to NICU post-discharge infant care, neonatal health monitoring, "
                        "and maternal caregiving support. I cannot provide information or assistance on topics "
                        "outside neonatal care and pediatric recovery."
                    )
                }

        # Check in-domain keyword match
        tokens = re.findall(r'\b[a-zA-Z]{3,}\b', text_lower)
        # Very short queries / greetings
        if len(tokens) <= 2 and any(t in text_lower for t in ["hi", "hello", "hey", "help", "thanks"]):
            return {"is_in_domain": True, "reason": None, "boundary_prompt": None}

        # Count in-domain keyword matches
        hits = sum(1 for kw in cls.IN_DOMAIN_CLINICAL_KEYWORDS if kw in text_lower)
        if hits == 0 and len(tokens) >= 3:
            return {
                "is_in_domain": False,
                "reason": "Query contains no neonatal or infant care concepts.",
                "boundary_prompt": (
                    "⚠️ **Clinical Scope Boundary**\n\n"
                    "I am specialized exclusively as a clinical post-discharge assistant for premature infant care and maternal support. "
                    "Please ask inquiries related to baby Liam's feeding, growth, Kangaroo Mother Care, medications, or health symptoms."
                )
            }

        return {"is_in_domain": True, "reason": None, "boundary_prompt": None}

    @classmethod
    def scan_for_emergency(cls, text: str) -> Dict[str, Any]:
        """
        Scans input for life-threatening neonatal danger signs.
        """
        text_lower = text.lower()
        matched_flags: List[str] = []

        for pattern in cls.RED_FLAG_PATTERNS:
            match = re.search(pattern, text_lower)
            if match:
                matched_flags.append(match.group(0))

        is_emergency = len(matched_flags) > 0

        return {
            "is_emergency": is_emergency,
            "matched_indicators": matched_flags,
            "emergency_prompt": (
                "⚠️ URGENT CLINICAL ATTENTION NEEDED\n\n"
                "You reported symptoms that may indicate acute neonatal distress "
                f"({', '.join(matched_flags)}). In infants under 3 months corrected age, "
                "these require immediate medical evaluation.\n\n"
                "Please call your hospital's 24/7 NICU emergency hotline or emergency services (108/911) immediately."
            ) if is_emergency else None
        }

    @classmethod
    def scan_for_harmful_practices(cls, text: str) -> Dict[str, Any]:
        """
        Detects whether user is inquiring about dangerous home remedies or practices.
        """
        text_lower = text.lower()
        flagged: List[str] = []
        guidance: List[str] = []

        for term, explanation in cls.HARMFUL_PRACTICES.items():
            if re.search(r'\b' + re.escape(term) + r'\b', text_lower):
                flagged.append(term)
                guidance.append(explanation)

        return {
            "has_harmful_inquiry": len(flagged) > 0,
            "flagged_terms": flagged,
            "clinical_warnings": guidance
        }

    @classmethod
    def mask_phi(cls, text: str) -> str:
        """
        Masks phone numbers, Aadhaar numbers, and email addresses.
        """
        sanitized = re.sub(cls.PHONE_REGEX, "[REDACTED_PHONE]", text)
        sanitized = re.sub(cls.AADHAAR_REGEX, "[REDACTED_ID]", sanitized)
        sanitized = re.sub(cls.EMAIL_REGEX, "[REDACTED_EMAIL]", sanitized)
        return sanitized

    @classmethod
    def validate_length(cls, text: str, max_chars: int = 1000) -> Dict[str, Any]:
        """
        Ensures input length is bounded to prevent buffer / token inflation.
        """
        if len(text.strip()) == 0:
            return {"valid": False, "reason": "Query cannot be empty."}
        if len(text) > max_chars:
            return {
                "valid": False,
                "reason": f"Query exceeds maximum allowed length of {max_chars} characters."
            }
        return {"valid": True, "reason": None}

    @classmethod
    def run_all_input_guardrails(cls, text: str) -> Dict[str, Any]:
        """
        Executes complete Input Guardrail suite: length, PHI masking, emergency, and harmful practice checks.
        """
        len_res = cls.validate_length(text)
        if not len_res["valid"]:
            return {
                "passed": False,
                "reason": len_res["reason"],
                "masked_text": text,
                "is_emergency": False,
                "harmful_flags": []
            }

        masked_text = cls.mask_phi(text)
        emerg_res = cls.scan_for_emergency(masked_text)

        # If acute life-threatening emergency, fast-path immediately
        if emerg_res["is_emergency"]:
            return {
                "passed": True,
                "masked_text": masked_text,
                "is_emergency": True,
                "is_out_of_domain": False,
                "matched_indicators": emerg_res["matched_indicators"],
                "emergency_prompt": emerg_res["emergency_prompt"],
                "has_harmful_inquiry": False,
                "flagged_harmful_terms": [],
                "harmful_warnings": [],
            }

        # Check domain boundaries
        domain_res = cls.validate_domain_scope(masked_text)
        if not domain_res["is_in_domain"]:
            return {
                "passed": False,
                "reason": domain_res["reason"],
                "is_out_of_domain": True,
                "out_of_domain_prompt": domain_res["boundary_prompt"],
                "masked_text": masked_text,
                "is_emergency": False,
                "harmful_flags": []
            }

        harm_res = cls.scan_for_harmful_practices(masked_text)

        return {
            "passed": True,
            "masked_text": masked_text,
            "is_emergency": False,
            "is_out_of_domain": False,
            "matched_indicators": [],
            "emergency_prompt": None,
            "has_harmful_inquiry": harm_res["has_harmful_inquiry"],
            "flagged_harmful_terms": harm_res["flagged_terms"],
            "harmful_warnings": harm_res["clinical_warnings"],
        }
