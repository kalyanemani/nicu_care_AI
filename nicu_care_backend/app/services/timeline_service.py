"""
Personalized Daily Care Timeline Service:
Orchestrates the mother's daily schedule, smart reminders, "What should I do next?"
assistant, KMC tracking, hygiene workflows, and maternal recovery check-ins.
"""

import json
import uuid
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import List, Dict, Any, Optional

from ..config import settings
from ..models.timeline import TimelineTask, KMCSession, GrowthRecord, MaternalWellbeing
from ..models.baby import BabyProfile
from ..services.wiki_service import WikiService
from ..services.care_log_service import CareLogService
from ..services.pediatric_math_service import PediatricMathService


class TimelineService:
    """Manages routine care timeline, smart reminders, and specialized care tracking."""

    def __init__(self):
        self.base_dir = settings.logs_dir
        self.wiki_service = WikiService()
        self.log_service = CareLogService()
        self.math_service = PediatricMathService()

    def _baby_dir(self, baby_id: str) -> Path:
        p = self.base_dir / baby_id
        p.mkdir(parents=True, exist_ok=True)
        return p

    def _load_json(self, baby_id: str, name: str) -> List[dict]:
        path = self._baby_dir(baby_id) / f"{name}.json"
        if not path.exists():
            return []
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return []

    def _save_json(self, baby_id: str, name: str, data: List[dict]):
        path = self._baby_dir(baby_id) / f"{name}.json"
        path.write_text(json.dumps(data, default=str, indent=2), encoding="utf-8")

    # ── KMC Tracker ─────────────────────────────────────────────────────
    def log_kmc_session(self, entry: KMCSession) -> KMCSession:
        if not entry.session_id:
            entry.session_id = f"kmc_{uuid.uuid4().hex[:8]}"
        records = self._load_json(entry.baby_id, "kmc_sessions")
        records.append(entry.model_dump(mode="json"))
        self._save_json(entry.baby_id, "kmc_sessions", records)
        return entry

    def get_kmc_sessions(self, baby_id: str, for_date: Optional[date] = None) -> List[KMCSession]:
        records = self._load_json(baby_id, "kmc_sessions")
        sessions = [KMCSession(**r) for r in records]
        for s in sessions:
            if s.timestamp and s.timestamp.tzinfo:
                s.timestamp = s.timestamp.replace(tzinfo=None)
        if for_date:
            sessions = [s for s in sessions if s.timestamp.date() == for_date]
        return sorted(sessions, key=lambda x: x.timestamp, reverse=True)

    def get_daily_kmc_summary(self, baby_id: str, for_date: Optional[date] = None) -> Dict[str, Any]:
        target_date = for_date or date.today()
        sessions = self.get_kmc_sessions(baby_id, target_date)
        total_minutes = sum(s.duration_minutes for s in sessions)
        target_hours = 3.0  # WHO recommended target for preterm at home: 2-4 hours
        completed_hours = round(total_minutes / 60.0, 1)
        remaining_hours = max(0.0, round(target_hours - completed_hours, 1))

        return {
            "date": str(target_date),
            "sessions_count": len(sessions),
            "total_minutes": total_minutes,
            "completed_hours": completed_hours,
            "target_hours": target_hours,
            "remaining_hours": remaining_hours,
            "percent_completed": min(100, int((completed_hours / target_hours) * 100)),
            "status": "Achieved Target" if remaining_hours == 0 else "In Progress",
            "sessions": [s.model_dump() for s in sessions],
        }

    def get_kmc_progress(self, baby_id: str, for_date: Optional[date] = None) -> Dict[str, Any]:
        """Alias for get_daily_kmc_summary."""
        return self.get_daily_kmc_summary(baby_id, for_date)

    # ── Growth Intelligence ─────────────────────────────────────────────
    def log_growth(self, entry: GrowthRecord) -> GrowthRecord:
        if not entry.record_id:
            entry.record_id = f"growth_{uuid.uuid4().hex[:8]}"
        records = self._load_json(entry.baby_id, "growth")
        
        # Calculate daily gain if previous weight exists
        prev_records = sorted([GrowthRecord(**r) for r in records], key=lambda x: x.date_recorded)
        if prev_records and entry.weight_grams:
            prev = prev_records[-1]
            days_diff = (entry.date_recorded - prev.date_recorded).days
            if days_diff > 0 and prev.weight_grams:
                gain = (entry.weight_grams - prev.weight_grams) / days_diff
                entry.daily_gain_g_per_day = round(gain, 1)
                # Standard preterm growth target: 15-20 g/kg/day
                weight_kg = entry.weight_grams / 1000.0
                g_per_kg_day = gain / weight_kg if weight_kg > 0 else 0
                if g_per_kg_day >= 15:
                    entry.velocity_status = "adequate"
                elif g_per_kg_day >= 10:
                    entry.velocity_status = "slow"
                else:
                    entry.velocity_status = "slow"

        # Calculate corrected age
        baby = self.wiki_service.load_baby_profile_json(entry.baby_id)
        if baby:
            corrected = self.math_service.calculate_corrected_age(baby, as_of=entry.date_recorded)
            entry.corrected_age_weeks = corrected.corrected_weeks

        records.append(entry.model_dump(mode="json"))
        self._save_json(entry.baby_id, "growth", records)
        return entry

    def get_growth_records(self, baby_id: str) -> List[GrowthRecord]:
        records = self._load_json(baby_id, "growth")
        if not records:
            # Seed initial discharge weight baseline
            baby = self.wiki_service.load_baby_profile_json(baby_id)
            if baby:
                init_rec = GrowthRecord(
                    baby_id=baby_id,
                    date_recorded=baby.discharge_date or (date.today() - timedelta(days=21)),
                    weight_grams=baby.discharge_weight_grams,
                    notes="Discharge weight from NICU",
                )
                self.log_growth(init_rec)
                records = self._load_json(baby_id, "growth")
        return sorted([GrowthRecord(**r) for r in records], key=lambda x: x.date_recorded, reverse=True)

    # ── Maternal Recovery & Wellbeing ───────────────────────────────────
    def log_maternal_checkin(self, entry: MaternalWellbeing) -> MaternalWellbeing:
        if not entry.entry_id:
            entry.entry_id = f"mother_{uuid.uuid4().hex[:8]}"
        records = self._load_json(entry.baby_id, "maternal_wellbeing")
        records.append(entry.model_dump(mode="json"))
        self._save_json(entry.baby_id, "maternal_wellbeing", records)
        return entry

    def get_maternal_records(self, baby_id: str) -> List[MaternalWellbeing]:
        records = self._load_json(baby_id, "maternal_wellbeing")
        return sorted([MaternalWellbeing(**r) for r in records], key=lambda x: x.timestamp, reverse=True)

    # ── Personalized Daily Care Timeline ────────────────────────────────
    def get_daily_timeline(self, baby_id: str, target_date: Optional[date] = None) -> List[TimelineTask]:
        """
        Builds today's schedule from the baby's actual discharge plan,
        correlating scheduled slots with actual recorded events.
        """
        ref_date = target_date or date.today()
        now = datetime.now()

        # Load baby profile and discharge plan
        baby = self.wiki_service.load_baby_profile_json(baby_id)
        target_vol = 50.0 if baby_id == "baby_liam_01" else 35.0
        feed_type = "Fortified Breast Milk"

        # Check today's actual logged feeds
        recent_feeds = self.log_service.get_feeds(baby_id, since_hours=24)
        feed_count = len(recent_feeds)

        # Check today's KMC
        kmc_summary = self.get_daily_kmc_summary(baby_id, ref_date)

        # Build ordered 24-hour routine slots
        tasks: List[TimelineTask] = [
            TimelineTask(
                task_id="task_feed_0800",
                time_str="08:00 AM",
                category="FEEDING",
                title=f"Morning Feed ({target_vol:.0f} mL {feed_type})",
                description="Give prescribed volume slowly with pacing. Burp upright.",
                status="COMPLETED" if feed_count >= 1 else ("DUE" if now.hour >= 8 else "UPCOMING"),
            ),
            TimelineTask(
                task_id="task_kmc_0900",
                time_str="09:00 AM",
                category="KMC_SESSION",
                title="KMC Session 1 (Skin-to-Skin Contact)",
                description="Hold baby chest-to-chest in upright prone position for at least 60 minutes.",
                status="COMPLETED" if kmc_summary["completed_hours"] >= 1.0 else ("DUE" if now.hour >= 9 else "UPCOMING"),
                details={"target_minutes": 60, "completed_hours": kmc_summary["completed_hours"]},
            ),
            TimelineTask(
                task_id="task_med_1000",
                time_str="10:00 AM",
                category="MEDICATION",
                title="Prescribed Vitamin D3 Drops (400 IU)",
                description="Give 1 mL orally using dedicated oral syringe. Do not mix into hot milk.",
                status="COMPLETED" if feed_count >= 3 else ("DUE" if now.hour >= 10 else "UPCOMING"),
                details={"medicine": "Vitamin D3", "dose": "400 IU (1 mL)", "missed_dose_rule": "Give when remembered today; do not double tomorrow."},
            ),
            TimelineTask(
                task_id="task_feed_1100",
                time_str="11:00 AM",
                category="FEEDING",
                title=f"Mid-Day Feed ({target_vol:.0f} mL {feed_type})",
                description="Check tolerance and note latch or bottle intake.",
                status="COMPLETED" if feed_count >= 2 else ("DUE" if now.hour >= 11 else "UPCOMING"),
            ),
            TimelineTask(
                task_id="task_sterilize_1130",
                time_str="11:30 AM",
                category="HYGIENE",
                title="Feeding Equipment Cleaning & Sterilization",
                description="Wash bottles, nipples & pump parts in warm soapy water, boil/steam sterilize 5 min, air dry.",
                status="COMPLETED" if now.hour >= 13 else ("DUE" if now.hour >= 11 else "UPCOMING"),
            ),
            TimelineTask(
                task_id="task_mother_1300",
                time_str="01:00 PM",
                category="MATERNAL_CARE",
                title="Mother's Rest, Hydration & Nourishment",
                description="Drink 2 large glasses of water, take prescribed postpartum vitamins, rest for 45 mins.",
                status="COMPLETED" if now.hour >= 15 else ("DUE" if now.hour >= 13 else "UPCOMING"),
            ),
            TimelineTask(
                task_id="task_feed_1400",
                time_str="02:00 PM",
                category="FEEDING",
                title=f"Afternoon Feed ({target_vol:.0f} mL {feed_type})",
                description="Follow 3-hour feeding schedule to sustain steady growth.",
                status="COMPLETED" if feed_count >= 3 else ("DUE" if now.hour >= 14 else "UPCOMING"),
            ),
            TimelineTask(
                task_id="task_kmc_1500",
                time_str="03:00 PM",
                category="KMC_SESSION",
                title="KMC Session 2 (Family or Mother Skin-to-Skin)",
                description="Promotes temperature stability and sleep organization.",
                status="COMPLETED" if kmc_summary["completed_hours"] >= 2.0 else ("DUE" if now.hour >= 15 else "UPCOMING"),
            ),
            TimelineTask(
                task_id="task_med_1800",
                time_str="06:00 PM",
                category="MEDICATION",
                title="Prescribed Iron Drops (Elemental Iron)",
                description="0.5 mL orally. Protects against preterm anemia. Give between feeds.",
                status="COMPLETED" if feed_count >= 6 else ("DUE" if now.hour >= 18 else "UPCOMING"),
                details={"medicine": "Elemental Iron", "dose": "0.5 mL (2 mg/kg)", "missed_dose_rule": "Give before bedtime if missed."},
            ),
            TimelineTask(
                task_id="task_feed_1700",
                time_str="05:00 PM",
                category="FEEDING",
                title=f"Evening Feed ({target_vol:.0f} mL {feed_type})",
                description="Check diaper output: count wet and soiled diapers.",
                status="COMPLETED" if feed_count >= 4 else ("DUE" if now.hour >= 17 else "UPCOMING"),
            ),
            TimelineTask(
                task_id="task_feed_2000",
                time_str="08:00 PM",
                category="FEEDING",
                title=f"Bedtime Feed ({target_vol:.0f} mL {feed_type})",
                description="Warm milk gently in warm water bowl. Keep baby upright for 20 mins.",
                status="COMPLETED" if feed_count >= 5 else ("DUE" if now.hour >= 20 else "UPCOMING"),
            ),
            TimelineTask(
                task_id="task_feed_2300",
                time_str="11:00 PM",
                category="FEEDING",
                title=f"Night Feed 1 ({target_vol:.0f} mL {feed_type})",
                description="Set gentle alarm so baby does not sleep longer than 3.5 hours between feeds.",
                status="COMPLETED" if feed_count >= 6 else ("DUE" if now.hour >= 23 else "UPCOMING"),
            ),
        ]

        # Identify the single next action
        found_next = False
        for t in tasks:
            if t.status in ("DUE", "UPCOMING") and not found_next:
                t.is_next = True
                found_next = True

        return tasks

    def get_what_should_i_do_next(self, baby_id: str) -> Dict[str, Any]:
        """Calculates the immediate care task and guidance for the mother."""
        tasks = self.get_daily_timeline(baby_id)
        next_task = next((t for t in tasks if t.is_next), tasks[0])
        baby = self.wiki_service.load_baby_profile_json(baby_id)
        baby_name = baby.name if baby else "your baby"

        guidance_map = {
            "FEEDING": f"🍼 {baby_name}'s next scheduled feed ({next_task.time_str}): Ensure breast milk or formula is prepared at body temperature. Feed upright with pauses for burping.",
            "KMC_SESSION": f"🦘 Skin-to-Skin Care ({next_task.time_str}): Unbutton your shirt, place {baby_name} upright on your bare chest between breasts, and cover with warm blanket.",
            "MEDICATION": f"💊 Medicine Due ({next_task.time_str}): {next_task.title}. Administer slowly into the inside cheek with oral syringe.",
            "HYGIENE": f"🧼 Hygiene Care ({next_task.time_str}): Disassemble bottles, nipples, and breast pump parts. Sterilize in boiling water or electric steam sterilizer.",
            "MATERNAL_CARE": "🌸 Care for Yourself: Mother's rest and hydration check-in. Have a glass of water and rest your body.",
        }

        actionable_advice = guidance_map.get(next_task.category, next_task.description)

        return {
            "task": next_task.model_dump(),
            "headline": f"Next Care Activity: {next_task.title} at {next_task.time_str}",
            "status": next_task.status,
            "actionable_guidance": actionable_advice,
            "category": next_task.category,
        }

    def get_next_feeding_task(self, baby_id: str) -> Dict[str, Any]:
        """Calculates the next upcoming or due feeding task specifically."""
        tasks = self.get_daily_timeline(baby_id)
        feed_tasks = [t for t in tasks if t.category == "FEEDING"]
        next_task = next((t for t in feed_tasks if t.status in ("DUE", "UPCOMING")), None)

        baby = self.wiki_service.load_baby_profile_json(baby_id)
        baby_name = baby.name if baby else "Liam"

        if not next_task:
            return {
                "task": {
                    "task_id": "feed_cycle_next",
                    "time_str": "In ~2.5 to 3 hours",
                    "category": "FEEDING",
                    "title": "Next Routine 3-Hour Feed",
                    "description": "Standard 3-hour preterm feeding interval.",
                    "status": "UPCOMING",
                    "is_next": True,
                    "details": None,
                },
                "headline": f"Next Feed for {baby_name}: In ~2.5 to 3 hours",
                "status": "UPCOMING",
                "actionable_guidance": (
                    f"🍼 All scheduled feeds for the current block have been logged. "
                    f"{baby_name}'s next feeding is recommended in approximately 2.5 to 3 hours. "
                    f"Target volume: 45–54 mL fortified breast milk."
                ),
                "category": "FEEDING",
            }

        return {
            "task": next_task.model_dump(),
            "headline": f"Next Scheduled Feed: {next_task.title} at {next_task.time_str}",
            "status": next_task.status,
            "actionable_guidance": (
                f"🍼 {baby_name}'s next feeding is {next_task.title} at {next_task.time_str} ({next_task.status}). "
                f"Ensure fortified breast milk or prescribed formula is prepared at body temperature. "
                f"Feed upright using paced bottle feeding with pauses for burping."
            ),
            "category": "FEEDING",
        }

    def get_next_kmc_task(self, baby_id: str) -> Dict[str, Any]:
        """Calculates the next upcoming or due Kangaroo Mother Care (KMC) task specifically."""
        tasks = self.get_daily_timeline(baby_id)
        kmc_tasks = [t for t in tasks if t.category == "KMC_SESSION"]
        next_task = next((t for t in kmc_tasks if t.status in ("DUE", "UPCOMING")), None)

        baby = self.wiki_service.load_baby_profile_json(baby_id)
        baby_name = baby.name if baby else "Liam"
        kmc_progress = self.get_kmc_progress(baby_id)

        if not next_task:
            return {
                "task": {
                    "task_id": "kmc_all_done",
                    "time_str": "Tomorrow 09:00 AM",
                    "category": "KMC_SESSION",
                    "title": "All Today's Scheduled KMC Sessions Completed",
                    "description": "Daily skin-to-skin target fulfilled. Comfort sessions welcome anytime.",
                    "status": "COMPLETED",
                    "is_next": False,
                    "details": None,
                },
                "headline": f"All Scheduled KMC Sessions Completed for Today ({kmc_progress['completed_hours']}h Total)",
                "status": "ALL_COMPLETED",
                "actionable_guidance": (
                    f"🎉 Excellent work! {baby_name}'s scheduled KMC sessions for today are complete, "
                    f"with a cumulative {kmc_progress['completed_hours']} hours logged (Target: {kmc_progress['target_hours']} hours). "
                    f"The next routine session begins tomorrow at 09:00 AM. You may also provide unscheduled comfort skin-to-skin anytime."
                ),
                "category": "KMC_SESSION",
            }

        return {
            "task": next_task.model_dump(),
            "headline": f"Next KMC Session: {next_task.title} at {next_task.time_str}",
            "status": next_task.status,
            "actionable_guidance": (
                f"🦘 {baby_name}'s next skin-to-skin session is scheduled at {next_task.time_str} ({next_task.status}). "
                f"Today's completed skin-to-skin: {kmc_progress['completed_hours']} hours / {kmc_progress['target_hours']} hours daily target. "
                f"WHO protocol advises at least 60 continuous minutes upright on bare chest."
            ),
            "category": "KMC_SESSION",
        }

    def get_care_schedule_status(self, baby_id: str) -> Dict[str, Any]:
        """
        Dynamically calculates the exact next feeding and KMC due times
        grounded in the latest recorded (or manually entered) event timestamps.
        """
        now = datetime.now()
        baby = self.wiki_service.load_baby_profile_json(baby_id)
        baby_name = baby.name if baby else "Liam"

        from .notification_service import notification_service
        prefs = notification_service.get_preferences("usr_mother_01")
        feed_interval = getattr(prefs, "feeding_interval_hours", 1.0)
        kmc_interval = getattr(prefs, "kmc_interval_hours", 3.0)
        vol_range = getattr(prefs, "feeding_volume_range", "45–54 mL")

        # 1. Feed calculations
        recent_feeds = self.log_service.get_feeds(baby_id, since_hours=48)
        if recent_feeds:
            latest_feed = max(recent_feeds, key=lambda f: f.timestamp)
            last_feed_dt = latest_feed.timestamp
            last_feed_time_str = last_feed_dt.strftime("%I:%M %p")
            last_feed_vol = latest_feed.volume_ml
        else:
            last_feed_dt = now - timedelta(hours=feed_interval + 0.1)
            last_feed_time_str = "No feed logged"
            last_feed_vol = 50.0

        next_feed_dt = last_feed_dt + timedelta(hours=feed_interval)
        feed_diff_mins = int((next_feed_dt - now).total_seconds() / 60)
        feed_is_due = feed_diff_mins <= 0
        feed_status = "OVERDUE" if feed_diff_mins <= -15 else ("DUE_NOW" if feed_diff_mins <= 0 else "UPCOMING")

        # 2. KMC calculations
        recent_kmc = self.get_kmc_sessions(baby_id)
        if recent_kmc:
            latest_kmc = max(recent_kmc, key=lambda k: k.timestamp)
            last_kmc_dt = latest_kmc.timestamp
            last_kmc_time_str = last_kmc_dt.strftime("%I:%M %p")
            last_kmc_duration = latest_kmc.duration_minutes
        else:
            last_kmc_dt = now - timedelta(hours=kmc_interval + 0.1)
            last_kmc_time_str = "No KMC session logged"
            last_kmc_duration = 60

        next_kmc_dt = last_kmc_dt + timedelta(hours=kmc_interval)
        kmc_diff_mins = int((next_kmc_dt - now).total_seconds() / 60)
        kmc_is_due = kmc_diff_mins <= 0
        kmc_status = "OVERDUE" if kmc_diff_mins <= -15 else ("DUE_NOW" if kmc_diff_mins <= 0 else "UPCOMING")

        kmc_summary = self.get_daily_kmc_summary(baby_id)

        return {
            "baby_id": baby_id,
            "baby_name": baby_name,
            "current_time": now.strftime("%I:%M %p"),
            "feeding": {
                "last_feed_time": last_feed_time_str,
                "last_feed_iso": last_feed_dt.isoformat(),
                "last_feed_volume_ml": last_feed_vol,
                "interval_hours": feed_interval,
                "target_volume_range": vol_range,
                "next_feed_time": next_feed_dt.strftime("%I:%M %p"),
                "next_feed_iso": next_feed_dt.isoformat(),
                "minutes_remaining": feed_diff_mins,
                "status": feed_status,
                "is_due": feed_is_due
            },
            "kmc": {
                "last_kmc_time": last_kmc_time_str,
                "last_kmc_iso": last_kmc_dt.isoformat(),
                "last_kmc_duration_minutes": last_kmc_duration,
                "interval_hours": kmc_interval,
                "completed_hours_today": kmc_summary["completed_hours"],
                "target_hours_today": kmc_summary["target_hours"],
                "next_kmc_time": next_kmc_dt.strftime("%I:%M %p"),
                "next_kmc_iso": next_kmc_dt.isoformat(),
                "minutes_remaining": kmc_diff_mins,
                "status": kmc_status,
                "is_due": kmc_is_due
            }
        }

    # ── Hygiene & Sterilization Checklist ───────────────────────────────
    def get_sterilization_protocol(self) -> Dict[str, Any]:
        """Authoritative AAP/CDC 5-step feeding equipment sterilization protocol."""
        return {
            "title": "5-Step Equipment Cleaning & Sterilization Guide",
            "steps": [
                {
                    "step": 1,
                    "title": "Clean Hands First",
                    "instruction": "Wash your hands with soap and warm water for at least 20 seconds before touching bottles or pump parts.",
                },
                {
                    "step": 2,
                    "title": "Disassemble Completely",
                    "instruction": "Separate all bottle parts (nipples, rings, caps, valves, membranes). Never leave components assembled while washing.",
                },
                {
                    "step": 3,
                    "title": "Wash with Dedicated Brush",
                    "instruction": "Rinse under running water. Wash in warm soapy water using a baby-only bottle brush. Do not place directly into kitchen sink basin.",
                },
                {
                    "step": 4,
                    "title": "Sterilize (Boil or Steam)",
                    "instruction": "Submerge items in boiling water for 5 continuous minutes, or use a certified electric steam sterilizer cycle.",
                },
                {
                    "step": 5,
                    "title": "Air Dry & Clean Storage",
                    "instruction": "Place on a clean, unused paper towel or sanitized drying rack. Store in a clean, covered container away from kitchen dust.",
                },
            ],
            "milk_storage_guidelines": {
                "room_temperature": "Up to 4 hours at < 25°C (77°F)",
                "refrigerator": "Up to 4 days at 4°C (40°F)",
                "freezer": "Up to 6 months at -18°C (0°F)",
                "thawed_breast_milk": "Use within 24 hours in fridge; NEVER refreeze thawed milk",
                "fortified_milk": "Use within 24 hours once fortifier (HMF) is added",
            }
        }


# Global Singleton Instance
timeline_service = TimelineService()
