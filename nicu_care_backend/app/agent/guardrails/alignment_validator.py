"""
Layer 4.5: Query-Response Semantic & Domain Alignment Validator
Pre-delivery verification gate that ensures the candidate response directly,
accurately, and specifically answers the mother's actual clinical inquiry.
Prevents topic drifting, irrelevant canned responses, and hallucinated deflections.
"""

import re
from typing import Dict, Any, List, Optional


class QueryResponseAlignmentValidator:
    """
    Validates that a candidate agent response matches the clinical domain,
    core entities, and specific intent of the mother's query before delivery.
    """

    DOMAIN_KEYWORDS = {
        "emergency": ["retract", "cyanosis", "dusky", "blue", "apnea", "fever", "letharg", "vomit", "emergency", "108", "112", "urgent", "ribs", "breathing"],
        "kangaroo_care": ["kmc", "kangaroo", "skin-to-skin", "skin to skin", "chest-to-chest", "upright chest", "frog-leg"],
        "feeding": ["feed", "feeding", "milk", "formula", "bottle", "latch", "volume", "ml", "hungry", "breast", "intake", "drank"],
        "growth": ["weight", "gain", "grams", "fenton", "growth", "weigh", "percentile", "scale"],
        "safe_sleep": ["sleep", "crib", "bassinet", "mattress", "back", "sids", "bed-sharing", "bed sharing", "co-sleeping", "blanket", "surface"],
        "medication": ["iron", "vitamin", "drops", "caffeine", "citrate", "dose", "medicine", "medication", "syringe", "meds", "prescriptions", "regimen"],
        "hygiene": ["steriliz", "clean", "wash", "boil", "pump parts", "bottles", "storage", "fridge", "thaw"],
        "hospital": ["hospital", "phone", "helpline", "ambulance", "address", "rainbow", "doctor", "contact"],
        "timeline": ["schedule", "routine", "what should i do", "what's next", "today's care", "timeline"],
        "temperature": ["temperature", "temparature", "temp", "cold", "warm", "degrees", "celsius", "fahrenheit", "overheating", "hypothermia", "hyperthermia", "chilled", "room temperature"],
    }

    STOP_WORDS = {
        "how", "much", "should", "the", "and", "for", "what", "can", "give", "does",
        "with", "this", "that", "are", "you", "your", "baby", "infant", "about",
        "did", "when", "where", "why", "who", "all", "our", "just", "today", "liam", "please"
    }

    @classmethod
    def extract_keywords(cls, text: str) -> set:
        words = re.findall(r'\b[a-zA-Z]{3,}\b', text.lower())
        return {w for w in words if w not in cls.STOP_WORDS} or set(words)

    @classmethod
    def detect_domain(cls, text: str, intent: Optional[str] = None) -> str:
        text_lower = text.lower()

        # Check for acute red flags first
        for em_kw in cls.DOMAIN_KEYWORDS["emergency"]:
            if em_kw in text_lower:
                return "emergency"

        best_domain = "general"
        max_score = 0

        for domain, kws in cls.DOMAIN_KEYWORDS.items():
            hits = sum(1 for kw in kws if kw in text_lower)
            if hits > max_score:
                max_score = hits
                best_domain = domain

        if best_domain != "general":
            return best_domain

        # Fall back to structured intent if text had no specific domain keywords
        if intent == "EMERGENCY":
            return "emergency"
        if intent in ["GROWTH_ANALYSIS", "PEDIATRIC_MATH"]:
            return "growth"
        if intent == "TIMELINE_INSPECT":
            return "timeline"

        return best_domain

    @classmethod
    def validate(cls, query: str, response: str, intent: Optional[str] = None) -> Dict[str, Any]:
        """
        Validates semantic alignment between query and candidate response.
        Returns a dictionary with passed status, alignment score, and detailed reasons.
        """
        q_lower = query.lower()
        r_lower = response.lower()

        # 1. Domain Detection
        q_domain = cls.detect_domain(query, intent=intent)
        r_domain = cls.detect_domain(response)

        # 2. Key Concept Overlap
        q_tokens = cls.extract_keywords(query)
        if not q_tokens:
            q_tokens = set(re.findall(r'\b[a-zA-Z]{2,}\b', q_lower))

        r_tokens = cls.extract_keywords(response)
        overlap = q_tokens.intersection(r_tokens)
        overlap_score = len(overlap) / max(1, len(q_tokens))

        # Check for direct keyword occurrences in response text
        direct_hits = sum(1 for t in q_tokens if t in r_lower)
        coverage_score = direct_hits / max(1, len(q_tokens))

        violations: List[str] = []

        # 3. Domain Mismatch Evaluation
        # If the query is strongly in one domain (e.g. kangaroo_care, growth, medication)
        # but the response belongs to another domain (e.g. safe_sleep), flag mismatch!
        if q_domain != "general" and r_domain != "general":
            if q_domain != r_domain:
                # Check if query domain concepts are well-represented in response
                q_domain_kws = cls.DOMAIN_KEYWORDS.get(q_domain, [])
                hits_in_response = sum(1 for kw in q_domain_kws if kw in r_lower)

                # Exemption 1: If query domain is strongly present in response (>= 2 keywords), response addresses it
                # Exemption 2: Paired domains (e.g. growth & feeding: weight calculation includes calibrated feeding targets)
                is_paired = ({q_domain, r_domain} == {"growth", "feeding"}) or (intent in ["GROWTH_ANALYSIS", "PEDIATRIC_MATH"])
                # Exemption 3: Timeline general queries
                is_timeline = (intent == "TIMELINE_INSPECT" or "next" in q_lower or "schedule" in q_lower)
                specific_subtopic = any(kw in q_lower for kw in ["kmc", "feed", "bath", "med", "sleep"])

                if not (hits_in_response >= 2 or is_paired or (is_timeline and not specific_subtopic)):
                    violations.append(
                        f"Domain mismatch: query is about '{q_domain}', but response discusses '{r_domain}'."
                    )

        # 4. Coverage Threshold Check
        # For clinical queries, at least some key query terms or domain terms must appear in response
        if coverage_score < 0.25 and q_domain not in ["emergency"]:
            # Check if any domain keywords for query domain appear in response
            domain_kws = cls.DOMAIN_KEYWORDS.get(q_domain, [])
            has_domain_term = any(kw in r_lower for kw in domain_kws)
            if not has_domain_term:
                violations.append(
                    f"Low semantic relevance (coverage {coverage_score:.2f}): response fails to address key query concepts ({', '.join(list(q_tokens)[:4])})."
                )

        passed = len(violations) == 0
        alignment_score = round(max(overlap_score, coverage_score), 3)

        return {
            "passed": passed,
            "alignment_score": alignment_score,
            "query_domain": q_domain,
            "response_domain": r_domain,
            "violations": violations,
            "reason": "; ".join(violations) if violations else "Query and response are semantically aligned"
        }
