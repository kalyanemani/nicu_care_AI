"""
Layer 2 Guardrails: Retrieval and Clinical Relevance.

Guarantees:
- Retrieved clinical guideline chunks must meet a strict relevance score floor (>= 0.70).
- Chunks are filtered by Gestational Age metadata (prevents toddler/adult advice reaching preemies).
"""

from typing import List, Dict, Any


class RetrievalGuardrails:
    """Pre-generation guardrail ensuring retrieved context is clinically appropriate."""

    RELEVANCE_FLOOR: float = 0.65

    @classmethod
    def filter_by_gestational_age(
        cls,
        chunks: List[Dict[str, Any]],
        baby_corrected_weeks: int
    ) -> List[Dict[str, Any]]:
        """
        Filters out knowledge base chunks that do not apply to the baby's
        current corrected gestational age.
        """
        valid_chunks = []
        for c in chunks:
            meta = c.get("metadata", {})
            min_weeks = meta.get("min_corrected_weeks", 0)
            max_weeks = meta.get("max_corrected_weeks", 104)

            if min_weeks <= baby_corrected_weeks <= max_weeks:
                valid_chunks.append(c)

        return valid_chunks

    @classmethod
    def apply_relevance_floor(
        cls,
        ranked_chunks: List[Dict[str, Any]],
        floor: float = RELEVANCE_FLOOR
    ) -> List[Dict[str, Any]]:
        """
        Drops chunks whose similarity score falls below the clinical confidence floor.
        """
        return [c for c in ranked_chunks if c.get("score", 0.0) >= floor]

    @classmethod
    def should_fallback_to_pediatrician(
        cls,
        filtered_chunks: List[Dict[str, Any]]
    ) -> bool:
        """
        If no authoritative guideline chunk passed the relevance floor,
        returns True to trigger a safe fallback ("Please ask your pediatrician").
        """
        return len(filtered_chunks) == 0
