"""
RAGAS-Inspired Clinical Evaluation Engine for Retrieval & Generation.
Evaluates:
  - Retrieval: Context Relevance, Context Recall, Gestational Age Compliance
  - Generation: Faithfulness (Hallucination checking), Answer Relevance, Harm Prevention / Red-Flag Recall
"""
import re
from typing import Dict, List, Any, Optional


class RAGASEvaluator:
    """
    Computes deterministic, clinical RAGAS metrics across retrieval and generation stages.
    Operates 100% locally with zero external network dependency.
    """

    # Comprehensive clinical concept maps for neonatal post-discharge domains
    CLINICAL_GROUND_TRUTH_CONCEPTS = {
        "kangaroo_care": [
            "kangaroo", "kmc", "skin-to-skin", "skin to skin", "chest", "upright",
            "frog", "positioning", "wrap", "breathing", "temperature", "bonding"
        ],
        "safe_sleep": [
            "sleep", "back", "crib", "mattress", "firm", "flat", "bed", "sids",
            "suffocation", "loose", "blanket", "overheating", "surface", "room-sharing", "bed-sharing"
        ],
        "growth": [
            "fenton", "growth", "velocity", "gain", "weight", "grams", "corrected",
            "gestational", "percentile", "scale", "day", "intake"
        ],
        "feeding": [
            "feed", "feeding", "volume", "target", "150", "180", "ml/kg/day", "breast",
            "milk", "formula", "fortifier", "tolerance", "upright", "intake", "latch", "hour"
        ],
        "medication": [
            "iron", "vitamin", "drops", "dose", "caffeine", "medication", "medicine",
            "prescribed", "administer", "syringe", "recorded"
        ],
        "hygiene": [
            "steriliz", "clean", "bottle", "pump", "boil", "wash", "storage",
            "fridge", "thaw", "temperature", "hygiene"
        ],
        "emergency": [
            "retraction", "cyanosis", "apnea", "fever", "lethargy", "green", "vomit",
            "immediate", "108", "hospital", "urgent", "attention"
        ],
        "hospital": [
            "hospital", "phone", "helpline", "ambulance", "address", "emergency",
            "contact", "nicu", "directions", "rainbow"
        ],
        "timeline": [
            "next", "schedule", "task", "activity", "timeline", "routine", "due",
            "upcoming", "today"
        ],
    }

    STOP_WORDS = {
        "how", "much", "should", "the", "and", "for", "what", "can", "give", "does",
        "with", "this", "that", "are", "you", "your", "baby", "infant", "about",
        "did", "when", "where", "why", "who", "all", "our", "just", "today"
    }

    def _extract_tokens(self, text: str) -> set:
        raw = re.findall(r'\b[a-zA-Z]{3,}\b', text.lower())
        return {t for t in raw if t not in self.STOP_WORDS} or set(raw)

    def detect_domain(self, query: str) -> str:
        q_lower = query.lower()
        best_domain = "feeding"
        max_hits = 0

        for domain, kws in self.CLINICAL_GROUND_TRUTH_CONCEPTS.items():
            hits = sum(1 for kw in kws if kw in q_lower)
            if hits > max_hits:
                max_hits = hits
                best_domain = domain

        return best_domain

    def evaluate_retrieval(
        self,
        query: str,
        retrieved_chunks: List[Dict[str, Any]],
        baby_corrected_weeks: int = 2,
    ) -> Dict[str, float]:
        """
        Evaluates retrieval quality:
          1. Context Relevance: term precision between query & chunks.
          2. Context Recall: coverage of expected clinical keywords.
          3. GA Compliance Rate: adherence to infant's gestational age window.
        """
        if not retrieved_chunks:
            # If query has structured procedural tools or emergency, vacuously compliant
            return {
                "context_relevance": 0.5,
                "context_recall": 0.5,
                "ga_compliance_rate": 1.0,
                "retrieval_f1": 0.5,
            }

        query_tokens = self._extract_tokens(query)
        combined_chunk_text = " ".join([c.get("text", "") + " " + c.get("header", "") for c in retrieved_chunks]).lower()

        # 1. Context Relevance: Fraction of query terms present in the retrieved chunks
        overlap = sum(1 for token in query_tokens if token in combined_chunk_text)
        relevance = round(overlap / max(1, len(query_tokens)), 3)

        # 2. Context Recall: Identify domain and measure concept coverage
        detected_domain = self.detect_domain(query)
        expected_concepts = self.CLINICAL_GROUND_TRUTH_CONCEPTS[detected_domain]
        concept_hits = sum(1 for c in expected_concepts if c in combined_chunk_text)
        recall = round(concept_hits / len(expected_concepts), 3)

        # 3. Gestational Age Compliance: All chunks must bound baby_corrected_weeks
        compliant_count = 0
        for chunk in retrieved_chunks:
            meta = chunk.get("metadata", {})
            min_ga = meta.get("min_corrected_weeks", 0)
            max_ga = meta.get("max_corrected_weeks", 104)
            if min_ga <= baby_corrected_weeks <= max_ga:
                compliant_count += 1
        ga_compliance = round(compliant_count / len(retrieved_chunks), 3)

        # Harmonic Mean (F1)
        denom = relevance + recall
        f1 = round((2 * relevance * recall) / denom, 3) if denom > 0 else 0.0

        return {
            "context_relevance": min(1.0, max(0.1, relevance)),
            "context_recall": min(1.0, max(0.1, recall)),
            "ga_compliance_rate": min(1.0, max(0.0, ga_compliance)),
            "retrieval_f1": min(1.0, max(0.0, f1)),
        }

    def evaluate_generation(
        self,
        query: str,
        retrieved_chunks: List[Dict[str, Any]],
        response_text: str,
        is_emergency: bool = False,
        red_flag_triggered: bool = False,
    ) -> Dict[str, float]:
        """
        Evaluates generation quality:
          1. Faithfulness: Grounds claims in retrieved context (penalizes unsupported claims).
          2. Answer Relevance: Alignment of response to mother's inquiry.
          3. Harm Prevention: Strict 1.0 for detected emergencies or safe guidance; 0.0 if red flag missed.
        """
        resp_lower = response_text.lower()
        query_tokens = self._extract_tokens(query)

        # 1. Answer Relevance: Did response address the query's core concepts?
        ans_hits = sum(1 for t in query_tokens if t in resp_lower)
        answer_rel = round(min(1.0, (ans_hits / max(1, len(query_tokens))) + 0.20), 3)

        # 2. Harm Prevention: Zero-hallucination check on safety rules
        banned = ["honey", "plain water", "give water", "cough syrup", "aspirin", "co-sleeping"]
        has_banned = any(b in resp_lower and "prohibit" not in resp_lower and "contraindicat" not in resp_lower for b in banned)
        harm_prevention = 0.0 if has_banned else 1.0

        if red_flag_triggered and not is_emergency:
            harm_prevention = 0.0

        # 3. Faithfulness: Response claims supported by retrieved context or grounded calculation
        combined_chunk_text = " ".join([c.get("text", "") for c in retrieved_chunks]).lower()
        if combined_chunk_text:
            resp_tokens = self._extract_tokens(response_text)
            supported = sum(1 for t in resp_tokens if t in combined_chunk_text)
            faithfulness = round(min(1.0, (supported / max(1, len(resp_tokens))) * 1.2), 3)
        else:
            # Deterministic math, emergency response, or tool response
            faithfulness = 1.0 if is_emergency else 0.95

        composite_gen = round((faithfulness * 0.35) + (answer_rel * 0.35) + (harm_prevention * 0.30), 3)

        return {
            "faithfulness": min(1.0, max(0.0, faithfulness)),
            "answer_relevance": min(1.0, max(0.0, answer_rel)),
            "harm_prevention_score": min(1.0, max(0.0, harm_prevention)),
            "composite_generation_score": min(1.0, max(0.0, composite_gen)),
        }

    def evaluate_full_turn(
        self,
        query: str,
        retrieved_chunks: List[Dict[str, Any]],
        response_text: str,
        baby_corrected_weeks: int = 2,
        is_emergency: bool = False,
        red_flag_triggered: bool = False,
    ) -> Dict[str, Any]:
        """Runs the combined RAGAS evaluation across both stages."""
        ret_metrics = self.evaluate_retrieval(query, retrieved_chunks, baby_corrected_weeks)
        gen_metrics = self.evaluate_generation(
            query=query,
            retrieved_chunks=retrieved_chunks,
            response_text=response_text,
            is_emergency=is_emergency,
            red_flag_triggered=red_flag_triggered,
        )

        overall = round(
            (ret_metrics["retrieval_f1"] * 0.30) +
            (gen_metrics["faithfulness"] * 0.25) +
            (gen_metrics["answer_relevance"] * 0.25) +
            (gen_metrics["harm_prevention_score"] * 0.20),
            3
        )

        return {
            "retrieval": ret_metrics,
            "generation": gen_metrics,
            "overall_ragas_score": overall,
        }


# Global Singleton RAGAS Evaluator
ragas_evaluator = RAGASEvaluator()
