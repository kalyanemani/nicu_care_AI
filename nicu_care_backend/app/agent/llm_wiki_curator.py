"""
LLM Baby Health Wiki Curator:
An asynchronous LLM agent that reads conversation turns, care entries, and
clinical reports to surgically extract durable facts and maintain the Baby Health Wiki.

Wiki Files Maintained:
- profile.md          -> Birth stats, gestational age, discharge weights
- active_regimen.md   -> Caloric fortifier ratios, target daily volumes, meds
- clinical_alerts.md  -> Chronic complications (BPD, IVH, reflux, allergies)
- rolling_log_summary.md -> 48-hour compressed care overview
"""

import json
import re
from datetime import datetime
from typing import Dict, Any, Optional

from ..services.wiki_service import WikiService
from ..services.obsidian_service import obsidian_service


class LLMWikiCurator:
    """
    Curates and evolves the Baby Health Wiki using structured fact extraction.
    Ensures long-term memory remains concise, high-density, and grounded.
    """

    def __init__(self):
        self.wiki_service = WikiService()

    def extract_and_patch_wiki(
        self,
        baby_id: str,
        conversation_turn: str,
        detected_entities: Optional[Dict[str, Any]] = None,
        external_knowledge: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Analyzes a conversation turn and any retrieved external knowledge for durable facts,
        patches the Baby Health Wiki, and synchronizes to the Obsidian Knowledge Vault.
        """
        text = conversation_turn.strip()
        text_lower = text.lower()
        patches_applied = []

        # 1. Regimen Changes (Fortifier ratios, feed volume targets, new medications)
        regimen_keywords = [
            "prescribe", "prescribed", "dose", "dosage", "fortifier",
            "kcal/oz", "iron", "vitamin", "caffeine", "increase", "decrease",
            "stop giving", "start giving", "formula"
        ]
        if any(term in text_lower for term in regimen_keywords):
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
            patch_content = f"- [{timestamp}] Regimen Update: {text}"
            self.wiki_service.patch_section(baby_id, "active_regimen", patch_content)
            patches_applied.append("active_regimen")

        # 2. Clinical Alerts (Allergies, reflux episodes, diagnoses)
        if any(term in text_lower for term in ["diagnosed", "allergic", "allergy", "reflux", "apnea episode", "bradycardia"]):
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
            patch_content = f"- [{timestamp}] Clinical Note: {text}"
            self.wiki_service.patch_section(baby_id, "clinical_alerts", patch_content)
            patches_applied.append("clinical_alerts")

        # 3. New Weight or Growth Milestone
        weight_match = re.search(r'(\d{3,4})\s*(g|grams|kg)', text_lower)
        if weight_match and "weigh" in text_lower:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
            patch_content = f"- [{timestamp}] Weight Check: {text}"
            self.wiki_service.patch_section(baby_id, "profile", patch_content)
            patches_applied.append("profile")

        # 4. External Clinical Knowledge Ingestion & Obsidian Vault Sync
        if external_knowledge and external_knowledge.get("has_external_knowledge"):
            q_topic = external_knowledge.get("query", text)
            guidance = external_knowledge.get("synthesized_guidance", "")
            recs = external_knowledge.get("key_recommendations", [])
            citations = external_knowledge.get("citations", [])
            authority = external_knowledge.get("source_authority", "External Clinical Literature")

            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
            ext_patch = (
                f"- [{timestamp}] External Evidence ({authority}):\n"
                f"  Query: \"{q_topic}\"\n"
                f"  Summary: {guidance}\n"
                f"  Recommendations: {'; '.join(recs)}"
            )
            self.wiki_service.patch_section(baby_id, "clinical_alerts", ext_patch)
            patches_applied.append("clinical_alerts_external_guidance")

            # Create / Put structured note in Obsidian Vault
            clean_title = re.sub(r'[^\w\s-]', '', q_topic).strip()[:40].replace(" ", "_") or "Clinical_Guideline"
            note_content = (
                f"# 🌐 {q_topic.title()}\n\n"
                f"### Clinical Synthesis\n"
                f"{guidance}\n\n"
                f"### Key Recommendations\n" +
                "\n".join(f"- {r}" for r in recs) + "\n\n"
                f"### Authoritative Citations & References\n" +
                "\n".join(f"- {c}" for c in citations) + "\n\n"
                f"### Patient Context\n"
                f"- Associated Patient: [[{baby_id}]]\n"
                f"- Curated by: NICU HomeCare AI / LLM Wiki Curator\n"
            )
            obsidian_service.put_note(
                note_title=clean_title,
                content=note_content,
                folder="Clinical_Knowledge",
                tags=["#nicu", "#clinical_guideline", "#evidence_based", f"#{baby_id}"],
                baby_id=baby_id
            )
            patches_applied.append(f"obsidian_vault_{clean_title}")

        # Synchronize any patched wiki sections to Obsidian vault under Baby_Profiles
        for sec in ["active_regimen", "profile", "clinical_alerts"]:
            if sec in patches_applied:
                sec_content = self.wiki_service.read_section(baby_id, sec)
                if sec_content:
                    obsidian_service.put_note(
                        note_title=f"{baby_id}_{sec}",
                        content=sec_content,
                        folder="Baby_Profiles",
                        tags=["#baby_profile", f"#{baby_id}", "#living_memory"],
                        baby_id=baby_id
                    )

        return {
            "baby_id": baby_id,
            "patches_applied": patches_applied,
            "success": len(patches_applied) > 0,
            "timestamp": datetime.now().isoformat()
        }

    def compile_full_context_for_llm(self, baby_id: str) -> str:
        """
        Compiles the relevant wiki sections into a compact, high-density
        prompt context (~300-400 tokens) to supply to generative models.
        """
        sections = self.wiki_service.read_all_sections(baby_id)

        profile_text = sections.get("profile") or "Profile: Not configured"
        regimen_text = sections.get("active_regimen") or "Regimen: Standard discharge"
        alerts_text = sections.get("clinical_alerts") or "Alerts: None"
        summary_text = sections.get("rolling_log_summary") or "Logs: No recent entries"

        compiled = f"""=== BABY HEALTH LIVING WIKI MEMORY ===
[BABY PROFILE]
{profile_text.strip()}

[ACTIVE REGIMEN]
{regimen_text.strip()}

[CLINICAL ALERTS]
{alerts_text.strip()}

[ROLLING 48H SUMMARY]
{summary_text.strip()}
======================================="""
        return compiled
