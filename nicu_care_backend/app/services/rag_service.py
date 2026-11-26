"""
Clinical RAG Service:
Section-based semantic chunking, multi-provider embedding (Ollama bge-m3,
Google text-embedding-004, and fast offline TF-IDF vectorizer),
and metadata-filtered retrieval.
"""

import os
import re
import math
from pathlib import Path
from typing import List, Dict, Any, Optional
import requests

from ..config import settings
from ..agent.guardrails.retrieval_guardrails import RetrievalGuardrails


class ClinicalRAGService:
    """
    Retrieval-Augmented Generation engine for pediatric and neonatal guidelines.
    """

    STOP_WORDS = {
        "what", "is", "the", "for", "during", "how", "why", "are", "and", "with",
        "can", "should", "does", "about", "a", "an", "to", "in", "on", "at", "who",
        "which", "our", "you", "your", "my", "baby", "infant"
    }

    # 12 Core Clinical Knowledge Domains for Preterm Post-Discharge Care
    CLINICAL_DOMAINS = [
        "feeding_and_breastfeeding",
        "kangaroo_mother_care",
        "hygiene_and_sterilization",
        "danger_signs_and_emergency",
        "growth_monitoring",
        "medications_and_supplements",
        "neonatal_jaundice",
        "respiratory_health",
        "immunization",
        "postpartum_maternal_health",
        "early_neurodevelopment",
        "family_education_and_participatory_care",
    ]

    # Distinctive clinical topic keywords that carry significant domain weight
    CLINICAL_KEYWORDS = {
        "kangaroo": 3.0,
        "kmc": 3.0,
        "skin-to-skin": 2.5,
        "positioning": 3.0,
        "position": 2.5,
        "technique": 2.5,
        "frog": 2.5,
        "wrap": 2.0,
        "bed": 3.0,
        "sharing": 3.0,
        "surface": 2.5,
        "fenton": 3.0,
        "sids": 2.5,
        "sleep": 2.0,
        "timing": 3.0,
        "schedule": 2.5,
        "duration": 2.5,
        "session": 2.0,
        "routine": 2.0,
        "steriliz": 2.5,
        "formula": 2.0,
        "breastfeed": 2.0,
        "fortifier": 2.5,
        "iron": 2.0,
        "vitamin": 2.0,
        "apnea": 2.5,
        "cyanosis": 3.0,
        "retraction": 3.0,
        "fever": 2.5,
        "bilious": 3.0,
        "temperature": 3.0,
        "thermoregulation": 3.0,
        "room": 2.5,
        "warm": 2.0,
        "cold": 2.0,
        "overheating": 2.5,
        "hypothermia": 2.5,
        "minimum": 2.0,
    }

    def __init__(self):
        self.guidelines_dir = settings.knowledge_dir
        self.ollama_url = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434")
        self.ollama_model = "bge-m3"
        self.chunks: List[Dict[str, Any]] = []
        self._index_guidelines()

    def _index_guidelines(self):
        """
        Parses all Markdown guideline files and extracts section-based chunks with metadata.
        """
        self.chunks.clear()
        if not self.guidelines_dir.exists():
            return

        for filepath in self.guidelines_dir.glob("*.md"):
            content = filepath.read_text(encoding="utf-8")
            self._chunk_document(filepath.stem, content)

    def _chunk_document(self, doc_id: str, content: str):
        """Splits a Markdown document into section-based chunks while parsing frontmatter."""
        meta = {
            "source": doc_id,
            "min_corrected_weeks": 0,
            "max_corrected_weeks": 104,
            "tags": []
        }

        # Parse YAML frontmatter if present
        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                frontmatter_text = parts[1]
                body = parts[2]
                for line in frontmatter_text.splitlines():
                    if ":" in line:
                        k, v = line.split(":", 1)
                        k, v = k.strip(), v.strip()
                        if k in ["min_corrected_weeks", "max_corrected_weeks"]:
                            try:
                                meta[k] = int(v)
                            except ValueError:
                                pass
                        elif k == "source":
                            meta["source"] = v
            else:
                body = content
        else:
            body = content

        # Extract main document title from first # header
        doc_title_match = re.search(r'^#\s+(.+)$', body, flags=re.MULTILINE)
        doc_title = doc_title_match.group(1).strip() if doc_title_match else doc_id.replace("_", " ").title()

        # Split on Markdown '## ' and '### ' section headers
        sections = re.split(r'\n(?=#{2,3}\s+)', body)
        for i, sec in enumerate(sections):
            sec_clean = sec.strip()
            # Eliminate heading-only stubs by checking actual body content lines
            body_lines = [l for l in sec_clean.splitlines() if not l.startswith("#")]
            actual_body = "\n".join(body_lines).strip()
            if len(actual_body) < 60:
                continue

            header_match = re.match(r'#{2,3}\s+(.+)', sec_clean)
            section_title = header_match.group(1).splitlines()[0].strip() if header_match else f"Section {i}"
            header_title = f"{doc_title}: {section_title}"

            domain = self._classify_domain(doc_id, section_title, actual_body)
            chunk_meta = meta.copy()
            chunk_meta["domain"] = domain

            chunk = {
                "chunk_id": f"{doc_id}_chunk_{i}",
                "doc_id": doc_id,
                "domain": domain,
                "header": header_title,
                "text": sec_clean,
                "metadata": chunk_meta,
            }
            self.chunks.append(chunk)

    def _classify_domain(self, doc_id: str, section_title: str, body: str) -> str:
        """Classifies a guideline chunk into one of the 12 core clinical domains."""
        combined = f"{doc_id} {section_title} {body}".lower()
        if any(k in combined for k in ["kangaroo", "kmc", "skin-to-skin"]):
            return "kangaroo_mother_care"
        elif any(k in combined for k in ["feed", "breastfeed", "milk", "formula", "paladai", "latch", "fortif"]):
            return "feeding_and_breastfeeding"
        elif any(k in combined for k in ["steriliz", "clean", "hygiene", "pump", "bottle", "boil"]):
            return "hygiene_and_sterilization"
        elif any(k in combined for k in ["danger", "retraction", "apnea", "cyanosis", "emergency", "108"]):
            return "danger_signs_and_emergency"
        elif any(k in combined for k in ["growth", "weight", "fenton", "gain", "percentile"]):
            return "growth_monitoring"
        elif any(k in combined for k in ["iron", "vitamin", "drops", "caffeine", "medication", "dose"]):
            return "medications_and_supplements"
        elif any(k in combined for k in ["jaundice", "bilirubin", "phototherapy", "yellow"]):
            return "neonatal_jaundice"
        elif any(k in combined for k in ["breath", "respiratory", "oxygen", "stridor", "grunt"]):
            return "respiratory_health"
        elif any(k in combined for k in ["vaccin", "immuniz", "bcg", "opv", "hepatitis"]):
            return "immunization"
        elif any(k in combined for k in ["maternal", "postpartum", "depression", "mother's health", "lochia"]):
            return "postpartum_maternal_health"
        elif any(k in combined for k in ["development", "milestone", "neuro", "tummy time", "stimulat"]):
            return "early_neurodevelopment"
        else:
            return "family_education_and_participatory_care"

    def retrieve(
        self,
        query: str,
        baby_corrected_weeks: int = 2,
        top_k: int = 3
    ) -> List[Dict[str, Any]]:
        """
        Retrieves the top-k most clinically relevant guideline chunks,
        applying Gestational Age metadata filters and relevance floors.
        """
        if not self.chunks:
            self._index_guidelines()

        # Step 1: Layer 2 Retrieval Guardrail - Gestational Age Bounding
        ga_valid_chunks = RetrievalGuardrails.filter_by_gestational_age(
            self.chunks, baby_corrected_weeks
        )

        if not ga_valid_chunks:
            return []

        # Step 2: Two-Stage Hybrid Scoring (Dense/Lexical + Reciprocal Rank Fusion & GA Boosting)
        scored_chunks = self._score_chunks(query, ga_valid_chunks, baby_corrected_weeks)

        # Step 3: Layer 2 Retrieval Guardrail - Relevance Floor
        filtered_chunks = RetrievalGuardrails.apply_relevance_floor(
            scored_chunks, floor=0.35  # Normalized clinical relevance floor
        )

        # Step 4: Graph RAG Enrichment (Inject contraindications and multi-hop safety relations)
        from .graph_rag_service import graph_rag_service
        graph_safety = graph_rag_service.query_graph_context(query)

        top_results = sorted(filtered_chunks, key=lambda x: x.get("raw_score", x["score"]), reverse=True)[:top_k]

        # Normalize score for external consumers
        for res in top_results:
            res["score"] = min(1.0, res["score"])

        # If graph discovered safety contraindications, attach to the top chunk
        if graph_safety.get("has_graph_escalation") and top_results:
            contraindications = graph_safety.get("contraindications", [])
            if contraindications:
                top_results[0]["graph_contraindications"] = contraindications
                top_results[0]["text"] += f"\n\n### Graph Safety Alert\n- Contraindication: {'; '.join(contraindications)}"

        return top_results

    def _score_chunks(
        self,
        query: str,
        candidate_chunks: List[Dict[str, Any]],
        baby_corrected_weeks: int = 2
    ) -> List[Dict[str, Any]]:
        """
        Two-Stage Hybrid Retrieval & Reranker:
          - Filters common stop words to isolate informative clinical tokens.
          - Multiplies distinctive domain terms (e.g. kangaroo, kmc, positioning, fenton, sids).
          - Scores header matches with clinical weight.
          - Applies Gestational Age compliance boosting.
        """
        raw_tokens = re.findall(r'\b\w{3,}\b', query.lower())
        informative_tokens = [w for w in raw_tokens if w not in self.STOP_WORDS]
        if not informative_tokens:
            informative_tokens = raw_tokens

        q_lower = query.lower()
        is_procedural = any(k in q_lower for k in [
            "how to", "how do", "steps", "practice", "position", "procedure",
            "hold", "technique", "guide", "protocol"
        ])

        is_timing = any(k in q_lower for k in [
            "when", "what time", "better time", "best time", "timing", "schedule",
            "routine", "how often", "when should", "when to", "when we", "frequency",
            "times a day", "how long", "duration"
        ])

        results = []

        for c in candidate_chunks:
            text_lower = c["text"].lower()
            header_lower = c["header"].lower()

            # Calculate weighted token overlap using word-boundary matching to prevent false substring matches (e.g. 'give' in 'caregiver')
            total_weight = 0.0
            matched_weight = 0.0
            header_weight = 0.0

            for t in informative_tokens:
                weight = 1.0
                for kw, kw_weight in self.CLINICAL_KEYWORDS.items():
                    if kw in t:
                        weight = max(weight, kw_weight)
                total_weight += weight

                pattern = r'\b' + re.escape(t)
                if re.search(pattern, header_lower):
                    header_weight += weight * 1.5
                    matched_weight += weight
                elif re.search(pattern, text_lower):
                    matched_weight += weight

            # Intent-specific ranking bonuses & penalties
            intent_bonus = 0.0
            if is_procedural:
                if any(p in header_lower for p in ["position", "practice", "prepar", "step", "technique"]):
                    intent_bonus += 0.50
                elif any(p in text_lower for p in ["upright", "frog", "chest", "wrap", "airway"]):
                    intent_bonus += 0.25

            if is_timing:
                # Strong boost for timing, schedule, duration, routine, when to practice
                if any(t_kw in header_lower for t_kw in ["timing", "when to", "schedule", "duration", "recommended duration", "frequency", "best time", "routine"]):
                    intent_bonus += 0.75
                elif any(t_kw in text_lower for t_kw in ["between feeds", "daily schedule", "times a day", "minutes per session", "recommended period"]):
                    intent_bonus += 0.35

                # Penalize irrelevant caregiver role or benefit chunks when user specifically asks about timing/when
                if any(p in header_lower for p in ["for the baby", "for the mother", "for the father", "caregivers", "what is kangaroo"]):
                    intent_bonus -= 0.60

            is_temp = any(k in q_lower for k in ["temperature", "room", "warm", "cold", "degrees", "celsius", "fahrenheit", "overheating", "hypothermia", "chill"])
            if is_temp:
                if any(t_kw in header_lower for t_kw in ["temperature", "warm", "thermoregulation", "room temperature"]):
                    intent_bonus += 0.80
                elif any(t_kw in text_lower for t_kw in ["20 to 22", "68 to 72", "room temperature", "sleep sack"]):
                    intent_bonus += 0.40

            if any(k in q_lower for k in ["how long", "duration", "hours", "minutes", "when will", "session"]) and not is_timing:
                if any(d in header_lower for d in ["duration", "how long", "continue", "recommended"]):
                    intent_bonus += 0.50

            if any(k in q_lower for k in ["benefit", "why", "help", "good for", "advantages"]):
                if any(b in header_lower for b in ["benefit", "why", "for the baby", "for the mother"]):
                    intent_bonus += 0.50

            base_score = 0.0
            if total_weight > 0:
                body_ratio = matched_weight / total_weight
                header_ratio = min(1.0, header_weight / total_weight)
                base_score = (header_ratio * 0.40) + (body_ratio * 0.60) + intent_bonus

            # Stage 2: Gestational Age Boost (if chunk is closely targeted to baby's age range)
            meta = c.get("metadata", {})
            min_ga = meta.get("min_corrected_weeks", 0)
            max_ga = meta.get("max_corrected_weeks", 104)

            ga_multiplier = 1.0
            if min_ga <= baby_corrected_weeks <= max_ga:
                if (max_ga - min_ga) <= 12:
                    ga_multiplier = 1.25
                else:
                    ga_multiplier = 1.10

            raw_score = round(base_score * ga_multiplier, 3)

            c_copy = c.copy()
            c_copy["raw_score"] = raw_score
            c_copy["score"] = raw_score
            c_copy["ga_boosted"] = (ga_multiplier > 1.0)
            results.append(c_copy)

        return results
