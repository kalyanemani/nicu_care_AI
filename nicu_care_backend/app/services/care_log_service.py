"""
Care log service: JSON-based time-series persistence for feedings,
diapers, and medications, plus 48-hour rolling summary generation.
"""

import json
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional

from ..config import settings
from ..models.care_log import FeedingEntry, DiaperEntry, MedicationEntry, CareSummary
from ..services.wiki_service import WikiService


class CareLogService:
    """Manages routine care logs and aggregates 48h clinical summaries."""

    def __init__(self):
        self.base_dir = settings.logs_dir
        self.wiki_service = WikiService()

    def _baby_log_dir(self, baby_id: str) -> Path:
        p = self.base_dir / baby_id
        p.mkdir(parents=True, exist_ok=True)
        return p

    def _file_path(self, baby_id: str, log_type: str) -> Path:
        return self._baby_log_dir(baby_id) / f"{log_type}.json"

    def _load_entries(self, baby_id: str, log_type: str) -> List[dict]:
        from .firestore_service import firestore_service
        if firestore_service.is_connected:
            fs_entries = firestore_service.get_care_logs(baby_id, log_type)
            if fs_entries is not None and len(fs_entries) > 0:
                return fs_entries

        path = self._file_path(baby_id, log_type)
        if not path.exists():
            return []
        try:
            entries = json.loads(path.read_text(encoding="utf-8"))
            if firestore_service.is_connected and entries:
                firestore_service.save_care_logs(baby_id, log_type, entries)
            return entries
        except Exception:
            return []

    def _save_entries(self, baby_id: str, log_type: str, entries: List[dict]):
        try:
            path = self._file_path(baby_id, log_type)
            path.write_text(json.dumps(entries, default=str, indent=2), encoding="utf-8")
        except Exception:
            pass
        from .firestore_service import firestore_service
        if firestore_service.is_connected:
            firestore_service.save_care_logs(baby_id, log_type, entries)

    # ── Feedings ────────────────────────────────────────────────────────
    def log_feed(self, entry: FeedingEntry) -> FeedingEntry:
        if not entry.entry_id:
            entry.entry_id = f"feed_{uuid.uuid4().hex[:8]}"
        entries = self._load_entries(entry.baby_id, "feeds")
        entries.append(entry.model_dump(mode="json"))
        self._save_entries(entry.baby_id, "feeds", entries)
        self._refresh_wiki_summary(entry.baby_id)
        return entry

    def get_feeds(self, baby_id: str, since_hours: Optional[int] = None) -> List[FeedingEntry]:
        raw = self._load_entries(baby_id, "feeds")
        feeds = [FeedingEntry(**e) for e in raw]
        for f in feeds:
            if f.timestamp and f.timestamp.tzinfo:
                f.timestamp = f.timestamp.replace(tzinfo=None)
        if since_hours is not None:
            cutoff = datetime.now() - timedelta(hours=since_hours)
            feeds = [f for f in feeds if f.timestamp >= cutoff]
        return sorted(feeds, key=lambda x: x.timestamp, reverse=True)

    # ── Diapers ─────────────────────────────────────────────────────────
    def log_diaper(self, entry: DiaperEntry) -> DiaperEntry:
        if not entry.entry_id:
            entry.entry_id = f"diaper_{uuid.uuid4().hex[:8]}"
        entries = self._load_entries(entry.baby_id, "diapers")
        entries.append(entry.model_dump(mode="json"))
        self._save_entries(entry.baby_id, "diapers", entries)
        self._refresh_wiki_summary(entry.baby_id)
        return entry

    def get_diapers(self, baby_id: str, since_hours: Optional[int] = None) -> List[DiaperEntry]:
        raw = self._load_entries(baby_id, "diapers")
        diapers = [DiaperEntry(**e) for e in raw]
        for d in diapers:
            if d.timestamp and d.timestamp.tzinfo:
                d.timestamp = d.timestamp.replace(tzinfo=None)
        if since_hours is not None:
            cutoff = datetime.now() - timedelta(hours=since_hours)
            diapers = [d for d in diapers if d.timestamp >= cutoff]
        return sorted(diapers, key=lambda x: x.timestamp, reverse=True)

    # ── Medications ─────────────────────────────────────────────────────
    def log_medication(self, entry: MedicationEntry) -> MedicationEntry:
        if not entry.entry_id:
            entry.entry_id = f"med_{uuid.uuid4().hex[:8]}"
        entries = self._load_entries(entry.baby_id, "medications")
        entries.append(entry.model_dump(mode="json"))
        self._save_entries(entry.baby_id, "medications", entries)
        return entry

    def get_medications(self, baby_id: str, since_hours: Optional[int] = None) -> List[MedicationEntry]:
        raw = self._load_entries(baby_id, "medications")
        meds = [MedicationEntry(**e) for e in raw]
        for m in meds:
            if m.timestamp and m.timestamp.tzinfo:
                m.timestamp = m.timestamp.replace(tzinfo=None)
        if since_hours is not None:
            cutoff = datetime.now() - timedelta(hours=since_hours)
            meds = [m for m in meds if m.timestamp >= cutoff]
        return sorted(meds, key=lambda x: x.timestamp, reverse=True)

    # ── 48-Hour Rolling Clinical Summary ────────────────────────────────
    def generate_48h_summary(self, baby_id: str) -> CareSummary:
        feeds = self.get_feeds(baby_id, since_hours=48)
        diapers = self.get_diapers(baby_id, since_hours=48)

        total_feeds = len(feeds)
        total_vol = sum(f.volume_ml for f in feeds)
        avg_vol = round(total_vol / total_feeds, 1) if total_feeds > 0 else 0.0
        daily_avg = round(total_vol / 2.0, 1)

        wet_count = sum(1 for d in diapers if d.wet)
        soiled_count = sum(1 for d in diapers if d.soiled)
        has_spitup = any(not f.tolerated for f in feeds)

        # Clinical stool screening
        concerning_colors = {"green", "black", "red_blood"}
        detected_concerning = [
            d.stool_color for d in diapers if d.stool_color in concerning_colors
        ]
        has_concerning_stool = len(detected_concerning) > 0

        # Load baby weight to calculate target
        profile = self.wiki_service.load_baby_profile_json(baby_id)
        weight_kg = (profile.discharge_weight_grams / 1000.0) if profile else 2.0
        min_daily_target = weight_kg * 150

        if daily_avg >= min_daily_target:
            intake_status = "adequate"
        elif daily_avg >= (min_daily_target * 0.85):
            intake_status = "borderline"
        else:
            intake_status = "low"

        flags = []
        if intake_status == "low":
            flags.append(f"Low daily intake ({daily_avg} mL vs min {min_daily_target:.0f} mL)")
        if wet_count < 8:  # 4/day min over 48h
            flags.append(f"Low wet diapers ({wet_count} in 48h; target >= 10-12)")
        if has_concerning_stool:
            flags.append(f"Concerning stool color reported: {set(detected_concerning)}")
        if has_spitup:
            flags.append("Feed intolerance / spit-up observed")

        summary_text = (
            f"Past 48h: {total_feeds} feeds logged totaling {total_vol:.0f} mL (avg {avg_vol} mL/feed, {daily_avg} mL/day). "
            f"Hydration status: {wet_count} wet diapers and {soiled_count} dirty diapers. "
            f"Intake status is {intake_status}."
        )

        return CareSummary(
            baby_id=baby_id,
            period_hours=48,
            total_feeds=total_feeds,
            total_volume_ml=total_vol,
            avg_volume_per_feed_ml=avg_vol,
            daily_avg_volume_ml=daily_avg,
            intake_target_status=intake_status,
            wet_diaper_count=wet_count,
            soiled_diaper_count=soiled_count,
            has_spitup_or_vomit=has_spitup,
            has_concerning_stool=has_concerning_stool,
            concerning_stool_colors=list(set(detected_concerning)),
            clinical_flags=flags,
            summary_paragraph=summary_text,
        )

    def _refresh_wiki_summary(self, baby_id: str):
        """Refreshes the rolling_log_summary.md file in the Baby Health Wiki."""
        summary = self.generate_48h_summary(baby_id)
        flags_text = "\n".join(f"- ⚠️ {f}" for f in summary.clinical_flags) if summary.clinical_flags else "- None (Routine parameters normal)"
        md_content = f"""# Rolling Care Log Summary (Last 48 Hours)
*Updated: {datetime.now().strftime('%Y-%m-%d %H:%M')}*

## Feeding Summary
- **Total Feeds Logged:** {summary.total_feeds}
- **Total Intake:** {summary.total_volume_ml:.0f} mL
- **Average Per Feed:** {summary.avg_volume_per_feed_ml:.1f} mL
- **Daily Average:** {summary.daily_avg_volume_ml:.1f} mL/day
- **Intake Evaluation:** {summary.intake_target_status.upper()}

## Diaper & Hydration
- **Wet Diapers:** {summary.wet_diaper_count} (Normal is >= 5-6 daily)
- **Soiled Diapers:** {summary.soiled_diaper_count}

## Clinical Alerts & Flags
{flags_text}

## Overview Note
{summary.summary_paragraph}
"""
        self.wiki_service.write_section(baby_id, "rolling_log_summary", md_content.strip())
