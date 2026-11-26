"""
Episodic Memory Management Service for Post-NICU Infant Care.

Captures, queries, and consolidates discrete longitudinal clinical episodes:
- Acute events (e.g. desaturation pauses, regurgitation, green vomit alerts)
- Milestone achievements (e.g. 2000g milestone, direct breastfeeding transitions)
- Regimen adjustments (e.g. fortifier calibration, multivitamin titrations)
- Feeding tolerance events and Kangaroo Mother Care sessions
"""
import os
import json
import time
import uuid
from typing import List, Dict, Any, Optional
from pathlib import Path

from ..models.auth import EpisodicEvent, EpisodeType, EpisodeSeverity

MEMORY_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "memory"
MEMORY_DIR.mkdir(parents=True, exist_ok=True)

VAULT_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "obsidian_vault" / "Daily_Care_Logs"
VAULT_DIR.mkdir(parents=True, exist_ok=True)


class EpisodicMemoryService:
    """
    Manages longitudinal episodic clinical memories:
    Distinct from working short-term memory (chat turns) and persistent long-term semantic wiki,
    episodic memory stores timestamped clinical episodes with clinical severity, vitals snapshots,
    and resolution status.
    """

    def __init__(self, memory_dir: Optional[Path] = None):
        self.memory_dir = memory_dir or MEMORY_DIR
        self.memory_dir.mkdir(parents=True, exist_ok=True)

    def _get_episodes_file(self, baby_id: str) -> Path:
        return self.memory_dir / f"{baby_id}_episodes.json"

    def _load_episodes(self, baby_id: str) -> List[Dict[str, Any]]:
        file_path = self._get_episodes_file(baby_id)
        if not file_path.exists():
            # Seed foundational discharge episode for Liam
            initial_episodes = self._seed_default_episodes(baby_id)
            self._save_episodes(baby_id, initial_episodes)
            return initial_episodes
        try:
            return json.loads(file_path.read_text(encoding="utf-8"))
        except Exception:
            return []

    def _save_episodes(self, baby_id: str, episodes: List[Dict[str, Any]]) -> None:
        file_path = self._get_episodes_file(baby_id)
        file_path.write_text(json.dumps(episodes, indent=2), encoding="utf-8")

    def _seed_default_episodes(self, baby_id: str) -> List[Dict[str, Any]]:
        now = time.time()
        discharge_time = now - (21 * 86400)
        kmc_time = now - (14 * 86400)
        weight_time = now - (7 * 86400)

        return [
            {
                "episode_id": "ep_discharge_001",
                "baby_id": baby_id,
                "timestamp": discharge_time,
                "date": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(discharge_time)),
                "episode_type": EpisodeType.CLINICAL_CHECKUP.value,
                "title": "Hospital Discharge from Rainbow Vijayawada NICU",
                "description": "Graduated NICU at 1820g on full oral feeding (fortified mother's milk, 22 kcal/oz). Physiological stability demonstrated in room air.",
                "severity": EpisodeSeverity.INFO.value,
                "clinical_data": {
                    "discharge_weight_grams": 1820,
                    "gestational_age_at_birth": "29w+2d",
                    "discharge_hospital": "BirthRight by Rainbow Children's Hospital, Vijayawada",
                    "neonatologist": "Dr. K. Rao"
                },
                "resolved": True,
                "resolution_notes": "All discharge criteria met; outpatient follow-up scheduled.",
                "tags": ["discharge", "nicu_graduate", "milestone"]
            },
            {
                "episode_id": "ep_kmc_002",
                "baby_id": baby_id,
                "timestamp": kmc_time,
                "date": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(kmc_time)),
                "episode_type": EpisodeType.KMC_SESSION.value,
                "title": "Extended 3-Hour Continuous Kangaroo Care Milestone",
                "description": "Mother completed continuous 3h skin-to-skin session. Infant demonstrated deep restorative sleep with stable axillary temperature (36.8°C).",
                "severity": EpisodeSeverity.INFO.value,
                "clinical_data": {
                    "duration_minutes": 180,
                    "temperature_celsius": 36.8,
                    "tolerated": True
                },
                "resolved": True,
                "resolution_notes": "Excellent thermal stability maintained without sweating or cold extremities.",
                "tags": ["kmc", "skin_to_skin", "thermoregulation", "milestone"]
            },
            {
                "episode_id": "ep_weight_003",
                "baby_id": baby_id,
                "timestamp": weight_time,
                "date": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(weight_time)),
                "episode_type": EpisodeType.MILESTONE.value,
                "title": "Weight Milestone: Crossed 2,000 Grams Threshold",
                "description": "Weekly weigh-in confirmed weight of 2,120g (+300g since discharge, ~25g/day average velocity, within WHO optimal target 20-30g/day).",
                "severity": EpisodeSeverity.INFO.value,
                "clinical_data": {
                    "weight_grams": 2120,
                    "growth_velocity_g_day": 25.0,
                    "who_percentile_trajectory": "normal_catchup"
                },
                "resolved": True,
                "resolution_notes": "Growth trajectory on track for corrected gestational age.",
                "tags": ["weight_gain", "growth", "milestone"]
            }
        ]

    def record_episode(
        self,
        baby_id: str,
        episode_type: EpisodeType,
        title: str,
        description: str,
        severity: EpisodeSeverity = EpisodeSeverity.INFO,
        clinical_data: Optional[Dict[str, Any]] = None,
        resolved: bool = True,
        resolution_notes: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> EpisodicEvent:
        """Records a new discrete clinical episode."""
        now = time.time()
        episode = EpisodicEvent(
            episode_id=f"ep_{uuid.uuid4().hex[:8]}",
            baby_id=baby_id,
            timestamp=now,
            date=time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(now)),
            episode_type=episode_type,
            title=title,
            description=description,
            severity=severity,
            clinical_data=clinical_data or {},
            resolved=resolved,
            resolution_notes=resolution_notes,
            tags=tags or []
        )

        episodes = self._load_episodes(baby_id)
        episodes.append(episode.dict())
        self._save_episodes(baby_id, episodes)

        # Mirror note to Obsidian Vault Daily Care Logs
        self._mirror_to_obsidian_vault(episode)

        return episode

    def _mirror_to_obsidian_vault(self, ep: EpisodicEvent) -> None:
        """Saves a structured Obsidian markdown note with YAML frontmatter."""
        try:
            sanitized_title = "".join(c for c in ep.title if c.isalnum() or c in (" ", "_", "-")).rstrip()
            date_prefix = time.strftime("%Y-%m-%d", time.localtime(ep.timestamp))
            filename = f"{date_prefix}_{ep.episode_type.value}_{sanitized_title.replace(' ', '_')[:40]}.md"
            note_path = VAULT_DIR / filename

            frontmatter = (
                f"---\n"
                f"episode_id: \"{ep.episode_id}\"\n"
                f"baby_id: \"{ep.baby_id}\"\n"
                f"date: \"{ep.date}\"\n"
                f"type: \"{ep.episode_type.value}\"\n"
                f"severity: \"{ep.severity.value}\"\n"
                f"resolved: {str(ep.resolved).lower()}\n"
                f"tags:\n"
                f"  - nicu_episodic_memory\n"
                f"  - {ep.episode_type.value.lower()}\n"
            )
            for t in ep.tags:
                frontmatter += f"  - {t}\n"
            frontmatter += "---\n\n"

            body = (
                f"# Episode: {ep.title}\n\n"
                f"**Subject:** [[{ep.baby_id}]] | **Timestamp:** `{ep.date}` | **Severity:** `{ep.severity.value}`\n\n"
                f"### Clinical Description\n{ep.description}\n\n"
            )

            if ep.clinical_data:
                body += "### Quantitative Telemetry Snapshot\n```json\n"
                body += json.dumps(ep.clinical_data, indent=2)
                body += "\n```\n\n"

            if ep.resolution_notes:
                body += f"### Resolution Notes\n{ep.resolution_notes}\n\n"

            body += f"*(Recorded automatically by NICU HomeCare AI Episodic Memory System)*\n"

            note_path.write_text(frontmatter + body, encoding="utf-8")
        except Exception:
            pass

    def get_episodes(
        self,
        baby_id: str,
        episode_type: Optional[str] = None,
        severity: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Retrieves episodes matching filters, ordered latest first."""
        episodes = self._load_episodes(baby_id)
        filtered = episodes
        if episode_type:
            filtered = [e for e in filtered if e.get("episode_type") == episode_type]
        if severity:
            filtered = [e for e in filtered if e.get("severity") == severity]

        # Return latest first
        return list(reversed(filtered))[:limit]

    def search_episodes(self, baby_id: str, query_str: str) -> List[Dict[str, Any]]:
        """Semantic/keyword search across historical clinical episodes."""
        episodes = self._load_episodes(baby_id)
        tokens = query_str.lower().split()
        results = []
        for ep in episodes:
            searchable = f"{ep.get('title', '')} {ep.get('description', '')} {' '.join(ep.get('tags', []))}".lower()
            if any(t in searchable for t in tokens):
                results.append(ep)
        return list(reversed(results))

    def get_summary(self, baby_id: str) -> Dict[str, Any]:
        """Provides high-level episodic memory summary for telemetry & dashboards."""
        episodes = self._load_episodes(baby_id)
        type_counts: Dict[str, int] = {}
        severity_counts: Dict[str, int] = {}
        acute_unresolved = 0

        for ep in episodes:
            t = ep.get("episode_type", "OTHER")
            s = ep.get("severity", "INFO")
            type_counts[t] = type_counts.get(t, 0) + 1
            severity_counts[s] = severity_counts.get(s, 0) + 1
            if not ep.get("resolved", True) and s in (EpisodeSeverity.MODERATE.value, EpisodeSeverity.CRITICAL.value):
                acute_unresolved += 1

        return {
            "baby_id": baby_id,
            "total_episodes_recorded": len(episodes),
            "episodes_by_type": type_counts,
            "episodes_by_severity": severity_counts,
            "unresolved_critical_episodes": acute_unresolved,
            "latest_episode": episodes[-1] if episodes else None,
        }


# Global Singleton instance
episodic_memory = EpisodicMemoryService()
