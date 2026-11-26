"""
Semantic Query Understanding & Clinical Disambiguation Engine:
Resolves linguistic variance, maternal colloquialisms, and ambiguity in conversational NLP.
Distinguishes clinical questions from routine logging commands, extracts clinical entities,
expands maternal queries with standardized medical ontologies, and provides LLM fallback.
"""

import re
import json
from typing import Dict, Any, List, Optional, Tuple
from pydantic import BaseModel, Field

from ...services.llm_service import llm_service
from ...services.neonatal_bert_service import neonatal_bert_service


class QueryUnderstandingResult(BaseModel):
    """Structured output of semantic query understanding."""
    raw_query: str
    normalized_query: str
    query_type: str = Field(..., description="QUESTION, LOG_COMMAND, EMERGENCY_ALERT, STATUS_INQUIRY, GENERAL_CHAT")
    intent: str = Field(..., description="Target routing intent, e.g. EMERGENCY, CLINICAL_QA, LOG_FEED, etc.")
    confidence: float = Field(..., ge=0.0, le=1.0)
    clinical_entities: Dict[str, Any] = Field(default_factory=dict)
    expanded_medical_terms: List[str] = Field(default_factory=list)
    requires_hitl: bool = False
    reasoning: str = ""


class SemanticQueryUnderstandingEngine:
    """
    Intelligent semantic parser and intent disambiguator for pediatric neonatal queries.
    Prevents misrouting of clinical questions into care logging actions.
    """

    # Interrogative tokens and question structures
    QUESTION_INDICATORS = [
        "is it", "can i", "can we", "should i", "should we", "how", "what",
        "why", "when", "does", "are", "do", "would", "could", "is that normal",
        "is this normal", "is baby", "how much", "how many", "tell me",
        "help me understand", "what if", "is there", "am i", "ought to"
    ]

    # Explicit logging action markers
    LOGGING_MARKERS = [
        "log ", "logged", "record ", "recorded", "save feed", "save diaper",
        "changed diaper", "wet diaper changed", "gave feed", "drank",
        "started kmc", "finished kmc", "took medication", "administered"
    ]

    # Colloquial Mother Phrases -> Standard Medical Concept Expansion
    CLINICAL_ONTOLOGY_MAP = {
        # Thermoregulation
        "cold to touch": ["neonatal hypothermia", "subnormal body temperature", "thermal instability"],
        "shivering": ["hypothermia", "thermal stress", "metabolic exhaustion"],
        "warm to touch": ["elevated temperature", "hyperthermia", "neonatal fever"],
        # Gastrointestinal & Feeding
        "spitting up": ["gastroesophageal reflux", "postprandial regurgitation", "feeding tolerance"],
        "curdled milk": ["partially digested milk", "normal gastric enzyme action", "reflux"],
        "gripe water": ["contraindicated non-prescribed supplement", "sodium bicarbonate hazard"],
        "not latching": ["poor suck-swallow-breathe coordination", "fatigue at breast"],
        "hiccups": ["diaphragmatic spasm", "aerophagia", "paced bottle feeding"],
        "colic": ["infant dyschezia", "digestive immaturity", "excess gas"],
        # Elimination
        "green stool": ["meconium transition", "iron supplement byproduct", "rapid bowel transit"],
        "brick dust": ["urate crystals in urine", "mild dehydration marker", "oliguria"],
        "not peeing": ["oliguria", "neonatal dehydration", "insufficient hydration intake"],
        "loose stool": ["neonatal diarrhea", "water loss", "electrolyte imbalance"],
        # Neurological & Alertness
        "floppy": ["hypotonia", "neuromuscular depression", "acute neonatal danger sign"],
        "won't wake up": ["neonatal lethargy", "hypoglycemia", "acute infection risk"],
        "sleeping all day": ["altered alertness", "lethargy vs normal preterm sleep pattern"],
        "jittery": ["neonatal jitteriness", "hypoglycemia", "hypocalcemia", "moro reflex"],
    }

    # Canonical Few-Shot Semantic Exemplars for Zero-Shot Classification
    EXEMPLARS: List[Tuple[str, str, str]] = [
        ("Liam drank 50 ml fortified breast milk at 10 AM", "LOG_COMMAND", "LOG_FEED"),
        ("Changed diaper: wet with yellow seedy stool", "LOG_COMMAND", "LOG_DIAPER"),
        ("Pediatrician prescribed iron drops 1.0 mL once daily", "LOG_COMMAND", "LOG_MEDICATION"),
        ("Finished 60 minutes skin-to-skin kangaroo care", "LOG_COMMAND", "LOG_KMC"),
        ("How many hours a day should we practice kangaroo mother care?", "QUESTION", "CLINICAL_QA"),
        ("Can we sleep in the same bed with baby if we are careful?", "QUESTION", "CLINICAL_QA"),
        ("Liam is spitting up milk after feeding, is this reflux?", "QUESTION", "CLINICAL_QA"),
        ("How much milk should a 2400g infant drink daily?", "QUESTION", "FEEDING_INTELLIGENCE"),
        ("Check liam weight status and gain velocity", "STATUS_INQUIRY", "GROWTH_ANALYSIS"),
        ("What should I do next for baby Liam?", "STATUS_INQUIRY", "TIMELINE_INSPECT"),
        ("When will be the next feed?", "STATUS_INQUIRY", "TIMELINE_INSPECT"),
        ("When is the next kmc session scheduled?", "STATUS_INQUIRY", "TIMELINE_INSPECT"),
        ("What is the phone number for Rainbow Hospital NICU?", "QUESTION", "HOSPITAL_LOOKUP"),
        ("Baby stopped breathing and turned dusky blue", "EMERGENCY_ALERT", "EMERGENCY"),
        ("Liam has a fever of 38.3 C and won't wake up", "EMERGENCY_ALERT", "EMERGENCY"),
        ("Baby just threw up dark green liquid", "EMERGENCY_ALERT", "EMERGENCY"),
    ]

    POLITE_LOG_REQUESTS = [
        "can you log", "could you log", "please log", "can you please log",
        "can you record", "could you record", "please record",
        "can we log", "want to log", "i want to log"
    ]

    @classmethod
    def is_question(cls, text: str) -> bool:
        """Determines if a query is an interrogative inquiry rather than an imperative log command."""
        t_lower = text.lower().strip()
        # Polite logging requests (e.g. "can you log kmc") are NOT clinical questions
        if any(p in t_lower for p in cls.POLITE_LOG_REQUESTS):
            return False
        if "?" in t_lower:
            return True
        for q_word in cls.QUESTION_INDICATORS:
            if t_lower.startswith(q_word) or f" {q_word} " in t_lower:
                return True
        return False

    @classmethod
    def is_logging_command(cls, text: str) -> bool:
        """Determines if a query is explicitly reporting a completed care event."""
        t_lower = text.lower().strip()
        # Polite logging commands are explicitly logging commands
        if any(p in t_lower for p in cls.POLITE_LOG_REQUESTS):
            return True
        if cls.is_question(t_lower):
            return False
        for marker in cls.LOGGING_MARKERS:
            if marker in t_lower:
                return True
        return False

    @classmethod
    def extract_entities(cls, text: str) -> Dict[str, Any]:
        """Extracts numerical quantities, vitals, temperatures, and substances."""
        entities: Dict[str, Any] = {}
        t_lower = text.lower()

        # Volume (e.g. 50 ml, 45 mL, 2 oz)
        vol_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:ml|milliliters?|oz|ounces?)', t_lower)
        if vol_match:
            entities["volume_ml"] = float(vol_match.group(1))

        # Weight (e.g. 2400 g, 2.4 kg, 2400 grams)
        wt_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:g|grams?|kg|kilograms?)', t_lower)
        if wt_match:
            val = float(wt_match.group(1))
            entities["weight_grams"] = val * 1000 if "kg" in wt_match.group(0) else val

        # Temperature (e.g. 38.3 C, 37.5 degrees)
        temp_match = re.search(r'(\d{2}(?:\.\d)?)\s*(?:c|degrees|deg|f)?', t_lower)
        if temp_match:
            try:
                t_val = float(temp_match.group(1))
                if 34.0 <= t_val <= 42.0:
                    entities["temperature_c"] = t_val
            except ValueError:
                pass

        # Substances
        if "breast milk" in t_lower or "ebm" in t_lower:
            entities["substance"] = "breast_milk"
        elif "formula" in t_lower or "neosure" in t_lower:
            entities["substance"] = "formula"
        elif "iron" in t_lower:
            entities["substance"] = "iron_drops"
        elif "vitamin" in t_lower or "poly-vi-sol" in t_lower:
            entities["substance"] = "multivitamin"

        return entities

    @classmethod
    def expand_clinical_concepts(cls, text: str) -> List[str]:
        """Maps colloquial maternal terms to validated medical ontology terms."""
        t_lower = text.lower()
        expanded: List[str] = []
        for colloquial, concepts in cls.CLINICAL_ONTOLOGY_MAP.items():
            if colloquial in t_lower:
                expanded.extend(concepts)
        return list(set(expanded))

    @classmethod
    def classify_with_llm(cls, query: str) -> Optional[Dict[str, Any]]:
        """
        Fast zero-shot classification via local Ollama model routing (qwen2.5:3b).
        Used as an intelligent fallback for complex, colloquial, or mixed queries.
        """
        system_prompt = (
            "You are an expert pediatric NICU clinical triage classifier. "
            "Analyze the mother's input and classify into exactly one intent:\n"
            "- EMERGENCY: Acute neonatal red flags (cyanosis, apnea, retractions, rectal fever, green vomit, lethargy)\n"
            "- GROWTH_ANALYSIS: Analyzing infant weight, gain velocity, Fenton growth curves\n"
            "- TIMELINE_INSPECT: Routine care schedule, when is next feed or kmc, upcoming tasks\n"
            "- FEEDING_INTELLIGENCE: Feeding volume calculation, daily requirement standard (150-180 mL/kg/day)\n"
            "- LOG_FEED: Explicit logging of consumed milk, volume, or feeding tolerance\n"
            "- LOG_DIAPER: Explicit logging of wet or soiled diaper changes\n"
            "- LOG_MEDICATION: Explicit logging of iron, vitamins, or prescribed drops\n"
            "- LOG_KMC: Explicit logging of completed skin-to-skin Kangaroo care session\n"
            "- HOSPITAL_LOOKUP: Hospital helpline, emergency contact, or doctor directory\n"
            "- CLINICAL_QA: Medical advice, safe sleep, symptoms, feeding questions, or general preemie guidance\n\n"
            "Return ONLY a valid JSON object with keys: 'intent', 'query_type', 'confidence' (0.0 to 1.0), 'reasoning'."
        )

        try:
            raw_resp = llm_service.generate_chat_response(
                prompt=f"Mother's Query: \"{query}\"",
                system_prompt=system_prompt,
                task_type="intent_classification"
            )
            if raw_resp:
                # Strip markdown code fencing if present
                clean = re.sub(r'```(?:json)?\s*', '', raw_resp).strip('` \n')
                data = json.loads(clean)
                if "intent" in data:
                    return data
        except Exception:
            pass
        return None

    @classmethod
    def understand_query(cls, query: str) -> QueryUnderstandingResult:
        """
        Main entry point for semantic query understanding.
        Combines rule-based grammar, concept expansion, entity extraction, and LLM classification.
        """
        from .normalizer import clinical_normalizer
        norm = clinical_normalizer.normalize_query(query)
        q_norm = norm["normalized_query"]
        q_clean = query.strip()
        q_lower = q_norm.lower()

        entities = cls.extract_entities(q_norm)
        expanded_concepts = cls.expand_clinical_concepts(q_norm)
        is_q = cls.is_question(q_norm)
        is_log = cls.is_logging_command(q_norm)

        # ── 1. Acute Emergency Detection ──────────────────────────────────────
        acute_emergency_kws = [
            "blue", "cyanosis", "stopped breathing", "not breathing", "apnea",
            "chest retracting", "retraction", "retractions", "ribs sucking in",
            "bilious", "green vomit", "unresponsive", "floppy", "cold to touch"
        ]
        if any(kw in q_lower for kw in acute_emergency_kws):
            return QueryUnderstandingResult(
                raw_query=q_clean,
                normalized_query=q_norm,
                query_type="EMERGENCY_ALERT",
                intent="EMERGENCY",
                confidence=0.99,
                clinical_entities=entities,
                expanded_medical_terms=expanded_concepts,
                requires_hitl=False,
                reasoning="Acute neonatal red-flag clinical indicator detected in query."
            )

        # ── 2. Disambiguation: Question vs Logging ────────────────────────────
        # CRITICAL RULE: If query is asking a question about feeding, poop, or meds,
        # it MUST NOT be routed to a logging command!
        if is_q:
            # Timeline / Next Scheduled Task Inquiries
            if any(w in q_lower for w in ["next feed", "next kmc", "next task", "what should i do next", "today's schedule", "when will be", "what time is"]):
                return QueryUnderstandingResult(
                    raw_query=q_clean,
                    normalized_query=q_norm,
                    query_type="STATUS_INQUIRY",
                    intent="TIMELINE_INSPECT",
                    confidence=0.97,
                    clinical_entities=entities,
                    expanded_medical_terms=expanded_concepts,
                    reasoning="Inquiry regarding scheduled upcoming care tasks on daily timeline."
                )

            # Feeding Volume Calculation / Standard Inquiries
            if any(w in q_lower for w in ["how much milk", "feeding target", "daily volume", "recommended volume", "how many ml", "feeding calculation"]):
                return QueryUnderstandingResult(
                    raw_query=q_clean,
                    normalized_query=q_norm,
                    query_type="QUESTION",
                    intent="FEEDING_INTELLIGENCE",
                    confidence=0.96,
                    clinical_entities=entities,
                    expanded_medical_terms=expanded_concepts,
                    reasoning="Calculation of calibrated daily fluid/feeding targets (150-180 mL/kg/day standard)."
                )

            # Growth / Weight Status Inquiries
            if any(w in q_lower for w in ["weight status", "weight gain", "how much has he gained", "fenton", "gain velocity", "is he growing"]):
                return QueryUnderstandingResult(
                    raw_query=q_clean,
                    normalized_query=q_norm,
                    query_type="STATUS_INQUIRY",
                    intent="GROWTH_ANALYSIS",
                    confidence=0.96,
                    clinical_entities=entities,
                    expanded_medical_terms=expanded_concepts,
                    reasoning="Inquiry regarding preterm infant growth velocity and weight accretion."
                )

            # Hospital Helpline / Contact Inquiries
            if any(w in q_lower for w in ["hospital", "helpline", "phone number", "ambulance", "address", "doctor's contact"]):
                return QueryUnderstandingResult(
                    raw_query=q_clean,
                    normalized_query=q_norm,
                    query_type="QUESTION",
                    intent="HOSPITAL_LOOKUP",
                    confidence=0.95,
                    clinical_entities=entities,
                    expanded_medical_terms=expanded_concepts,
                    reasoning="Inquiry seeking discharge hospital contact directory or emergency numbers."
                )

            # Clinical QA (General educational questions, safe sleep, reflux, hygiene)
            return QueryUnderstandingResult(
                raw_query=q_clean,
                normalized_query=q_norm,
                query_type="QUESTION",
                intent="CLINICAL_QA",
                confidence=0.92,
                clinical_entities=entities,
                expanded_medical_terms=expanded_concepts,
                reasoning="General clinical educational question regarding preterm infant health or guidelines."
            )

        # ── 3. Imperative Care Logging Commands ───────────────────────────────
        if is_log or any(w in q_lower for w in ["logged", "recorded", "gave", "finished", "changed diaper"]):
            if any(w in q_lower for w in ["kmc", "kangaroo", "skin-to-skin"]):
                return QueryUnderstandingResult(
                    raw_query=q_clean,
                    normalized_query=q_norm,
                    query_type="LOG_COMMAND",
                    intent="LOG_KMC",
                    confidence=0.96,
                    clinical_entities=entities,
                    reasoning="Caregiver reporting completed skin-to-skin Kangaroo care session."
                )
            if any(w in q_lower for w in ["diaper", "wet", "soiled", "poop", "pee", "stool"]):
                return QueryUnderstandingResult(
                    raw_query=q_clean,
                    normalized_query=q_norm,
                    query_type="LOG_COMMAND",
                    intent="LOG_DIAPER",
                    confidence=0.95,
                    clinical_entities=entities,
                    reasoning="Caregiver logging wet or soiled diaper change event."
                )
            if any(w in q_lower for w in ["iron", "vitamin", "drops", "citrate", "caffeine", "medication", "medicine"]):
                return QueryUnderstandingResult(
                    raw_query=q_clean,
                    normalized_query=q_norm,
                    query_type="LOG_COMMAND",
                    intent="LOG_MEDICATION",
                    confidence=0.94,
                    clinical_entities=entities,
                    reasoning="Caregiver recording administration of prescribed neonatal drops."
                )
            if any(w in q_lower for w in ["feed", "drank", "ml", "milk", "formula"]):
                return QueryUnderstandingResult(
                    raw_query=q_clean,
                    normalized_query=q_norm,
                    query_type="LOG_COMMAND",
                    intent="LOG_FEED",
                    confidence=0.95,
                    clinical_entities=entities,
                    reasoning="Caregiver recording completed feeding volume and intake."
                )

        # ── 4. Growth & Weight Status Checks ──────────────────────────────────
        if any(w in q_lower for w in ["weight", "growth", "growing", "weigh", "gained", "gain", "grams", "fenton"]):
            return QueryUnderstandingResult(
                raw_query=q_clean,
                normalized_query=q_norm,
                query_type="STATUS_INQUIRY",
                intent="GROWTH_ANALYSIS",
                confidence=0.93,
                clinical_entities=entities,
                expanded_medical_terms=expanded_concepts,
                reasoning="Inquiry regarding weight or growth analysis."
            )

        # ── 4.5. Patient Record & Prescriptions Status Inquiries (0ms Deterministic) ──
        med_inquiry_patterns = [
            "active meds", "current meds", "medicines", "prescribed meds",
            "prescriptions", "what meds", "which meds", "iron drops", "vitamin drops",
            "active medications", "current medications", "medication list", "baby's drops"
        ]
        if any(p in q_lower for p in med_inquiry_patterns) and not is_log:
            entities["record_type"] = "MEDICATIONS"
            return QueryUnderstandingResult(
                raw_query=q_clean,
                normalized_query=q_norm,
                query_type="STATUS_INQUIRY",
                intent="PATIENT_RECORD_INQUIRY",
                confidence=0.98,
                clinical_entities=entities,
                expanded_medical_terms=expanded_concepts,
                reasoning="Inquiry regarding infant's verified discharge medications and active prescriptions."
            )

        intake_inquiry_patterns = [
            "intake status", "current intake", "feeding status", "how much has he eaten",
            "48h intake", "48h summary", "feeding summary", "intake summary", "total feeds today"
        ]
        if any(p in q_lower for p in intake_inquiry_patterns) and not is_log:
            entities["record_type"] = "FEEDING_STATUS"
            return QueryUnderstandingResult(
                raw_query=q_clean,
                normalized_query=q_norm,
                query_type="STATUS_INQUIRY",
                intent="PATIENT_RECORD_INQUIRY",
                confidence=0.98,
                clinical_entities=entities,
                expanded_medical_terms=expanded_concepts,
                reasoning="Inquiry regarding infant's 48-hour feeding intake and hydration metrics."
            )

        # ── 5. NeonatalBERT High-Speed Transformer Classification (<3ms) ──────
        bert_res = neonatal_bert_service.analyze_query(q_norm)
        if bert_res and bert_res.intent:
            if bert_res.intent == "MEDICATION":
                target_intent = "PATIENT_RECORD_INQUIRY" if not is_log else "LOG_MEDICATION"
                entities["record_type"] = "MEDICATIONS"
            elif bert_res.intent == "PEDIATRIC_MATH":
                target_intent = "FEEDING_INTELLIGENCE"
            elif bert_res.intent == "PROCEDURE":
                target_intent = "CLINICAL_QA"
            elif bert_res.intent == "EMERGENCY":
                target_intent = "EMERGENCY"
            else:
                target_intent = bert_res.intent

            return QueryUnderstandingResult(
                raw_query=q_clean,
                normalized_query=q_norm,
                query_type="QUESTION" if not is_log else "LOG_COMMAND",
                intent=target_intent,
                confidence=0.95,
                clinical_entities=entities,
                expanded_medical_terms=expanded_concepts,
                reasoning=f"NeonatalBERT fast classification ({bert_res.latency_ms}ms) -> {target_intent}"
            )

        # ── 6. Default Safe Clinical QA ───────────────────────────────────────
        return QueryUnderstandingResult(
            raw_query=q_clean,
            normalized_query=q_norm,
            query_type="QUESTION",
            intent="CLINICAL_QA",
            confidence=0.85,
            clinical_entities=entities,
            expanded_medical_terms=expanded_concepts,
            reasoning="Defaulted to grounded clinical guidance."
        )


# Global Singleton Instance
query_understanding_engine = SemanticQueryUnderstandingEngine()
