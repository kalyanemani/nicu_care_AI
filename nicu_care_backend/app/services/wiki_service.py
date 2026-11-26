"""
Wiki service: manages the Baby Health Wiki (living memory) stored as
Markdown files on the local filesystem.

In production, this will be swapped to Cloud Firestore by toggling
the USE_CLOUD_FIRESTORE feature flag in config.py.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List

from ..config import settings
from ..models.baby import BabyProfile


VALID_SECTIONS = ["profile", "active_regimen", "clinical_alerts", "rolling_log_summary"]


class WikiService:
    """Read/write Baby Health Wiki sections as local Markdown files."""

    def __init__(self):
        self.base_dir = settings.wiki_dir

    def _baby_dir(self, baby_id: str) -> Path:
        """Returns the wiki directory for a specific baby."""
        p = self.base_dir / baby_id
        p.mkdir(parents=True, exist_ok=True)
        return p

    def read_section(self, baby_id: str, section: str) -> Optional[str]:
        if section not in VALID_SECTIONS:
            raise ValueError(f"Invalid section '{section}'. Must be one of {VALID_SECTIONS}")

        from .firestore_service import firestore_service
        if firestore_service.is_connected:
            content = firestore_service.get_wiki_section(baby_id, section)
            if content:
                return content

        filepath = self._baby_dir(baby_id) / f"{section}.md"
        if filepath.exists():
            text = filepath.read_text(encoding="utf-8")
            if firestore_service.is_connected and text:
                firestore_service.save_wiki_section(baby_id, section, text)
            return text
        return None

    def write_section(self, baby_id: str, section: str, content: str) -> str:
        if section not in VALID_SECTIONS:
            raise ValueError(f"Invalid section '{section}'. Must be one of {VALID_SECTIONS}")

        try:
            filepath = self._baby_dir(baby_id) / f"{section}.md"
            filepath.write_text(content, encoding="utf-8")
        except Exception:
            pass

        from .firestore_service import firestore_service
        if firestore_service.is_connected:
            firestore_service.save_wiki_section(baby_id, section, content)

        return content

    def patch_section(self, baby_id: str, section: str, patch_text: str) -> str:
        """
        Appends a timestamped patch entry to an existing wiki section.
        Creates the section if it doesn't exist.
        Deduplicates repeated entries so the wiki does not bloat uncontrollably.
        """
        existing = self.read_section(baby_id, section) or ""
        
        # Deduplication check: if core text of patch is already present in existing, skip re-appending
        patch_clean = patch_text.strip()
        lines = [line.strip("- *#").strip() for line in patch_clean.splitlines() if line.strip()]
        if lines:
            core_line = lines[0]
            # Strip timestamp prefixes like [2026-11-24 20:00] Regimen Update: ...
            import re
            cleaned_core = re.sub(r"^\[\d{4}-\d{2}-\d{2}[^\]]*\]\s*", "", core_line).strip()
            if cleaned_core and cleaned_core in existing:
                return existing

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        patched = f"{existing}\n\n---\n*Updated {timestamp}*\n{patch_text}"
        return self.write_section(baby_id, section, patched.strip())

    def deduplicate_and_compact_section(self, baby_id: str, section: str) -> str:
        """
        Deduplicates recurring update blocks and keeps only the latest distinct updates.
        """
        content = self.read_section(baby_id, section)
        if not content:
            return ""
        
        blocks = content.split("\n\n---\n")
        header = blocks[0]
        seen_payloads = set()
        unique_blocks = []

        import re
        for b in blocks[1:]:
            # Extract content lines ignoring timestamp
            lines = [l for l in b.splitlines() if not l.startswith("*Updated")]
            payload = "\n".join(lines).strip()
            # Normalize dates/timestamps in payload to detect true semantic duplicates
            normalized_payload = re.sub(r"\[\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}\]", "[DATE]", payload)
            if normalized_payload not in seen_payloads and payload:
                seen_payloads.add(normalized_payload)
                unique_blocks.append(b.strip())
        
        # Keep at most 5 most recent distinct updates
        compacted = header.strip()
        if unique_blocks:
            recent_blocks = unique_blocks[-5:]
            compacted += "\n\n---\n" + "\n\n---\n".join(recent_blocks)
        
        return self.write_section(baby_id, section, compacted)

    def read_all_sections(self, baby_id: str) -> Dict[str, Optional[str]]:
        """Reads all wiki sections for a baby. Returns a dict of section → content."""
        return {
            section: self.read_section(baby_id, section)
            for section in VALID_SECTIONS
        }

    def load_all_wiki_files(self, baby_id: str) -> Dict[str, str]:
        """Loads all existing wiki markdown files for a baby."""
        sections = self.read_all_sections(baby_id)
        return {
            f"{sec}.md": content
            for sec, content in sections.items()
            if content is not None
        }

    def list_babies(self) -> List[str]:
        """Returns a list of all baby IDs that have wiki directories."""
        if not self.base_dir.exists():
            return []
        return [
            d.name for d in self.base_dir.iterdir()
            if d.is_dir() and not d.name.startswith(".")
        ]

    def create_profile_from_baby(self, baby: BabyProfile) -> str:
        """
        Generates and writes the initial profile.md from a BabyProfile model.
        """
        from ..services.pediatric_math_service import PediatricMathService

        math_svc = PediatricMathService()
        corrected = math_svc.calculate_corrected_age(baby)
        volume = math_svc.calculate_daily_volume_target(baby.discharge_weight_grams)

        content = f"""# Baby Profile: {baby.name}

## Identity
- **Baby ID:** {baby.baby_id}
- **Date of Birth:** {baby.date_of_birth.isoformat()}
- **Sex:** {baby.sex.capitalize()}
- **Blood Type:** {baby.blood_type or "Not recorded"}

## Birth & Discharge
- **Gestational Age at Birth:** {baby.gestational_age_weeks} weeks, {baby.gestational_age_days} days
- **Birth Weight:** {baby.birth_weight_grams} g
- **Discharge Weight:** {baby.discharge_weight_grams} g
- **Discharge Date:** {baby.discharge_date.isoformat()}
- **Discharge Hospital:** {baby.discharge_hospital}

## Current Age (as of {corrected.date_calculated.isoformat()})
- **Chronological Age:** {corrected.chronological_weeks}w {corrected.chronological_remaining_days}d
- **Corrected Age:** {corrected.corrected_weeks}w {corrected.corrected_remaining_days}d
- **Weeks Born Early:** {corrected.weeks_born_early}

## Feeding Targets
- {volume['note']}

## Care Team
- **Pediatrician:** {baby.pediatrician_name or "Not assigned"}
- **Mother's Language:** {baby.mother_preferred_language}
"""
        return self.write_section(baby.baby_id, "profile", content.strip())

    def save_baby_profile_json(self, baby: BabyProfile) -> None:
        """Persists the BabyProfile as a JSON file and mirrors to Firestore."""
        try:
            filepath = self._baby_dir(baby.baby_id) / "baby_profile.json"
            filepath.write_text(baby.model_dump_json(indent=2), encoding="utf-8")
        except Exception:
            pass

        from .firestore_service import firestore_service
        if firestore_service.is_connected:
            firestore_service.save_baby_profile(baby.baby_id, baby.model_dump(mode="json"))

    def load_baby_profile_json(self, baby_id: str) -> Optional[BabyProfile]:
        """Loads a BabyProfile from Firestore or local JSON file."""
        from .firestore_service import firestore_service
        if firestore_service.is_connected:
            fs_profile = firestore_service.get_baby_profile(baby_id)
            if fs_profile:
                return BabyProfile(**fs_profile)

        filepath = self._baby_dir(baby_id) / "baby_profile.json"
        if not filepath.exists():
            return None
        data = json.loads(filepath.read_text(encoding="utf-8"))
        profile = BabyProfile(**data)
        if firestore_service.is_connected:
            firestore_service.save_baby_profile(baby_id, data)
        return profile
