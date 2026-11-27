"""
Autonomous Regular-Interval Reminder Scheduler for NICU HomeCare AI.
Monitors care timelines, feeding intervals, KMC sessions, and medication routines in the background.
Dispatches proactive alerts to parents' registered email and mobile numbers when activities are due.
"""
import threading
import time
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

from .notification_service import notification_service
from .care_log_service import CareLogService
from .timeline_service import TimelineService
from ..models.reminder import ReminderCategory, NotificationChannel


class ReminderScheduler:
    """Background worker that continuously evaluates interval schedules and dispatches reminders."""

    def __init__(self, check_interval_seconds: int = 60):
        self.check_interval_seconds = check_interval_seconds
        self.care_log_service = CareLogService()
        self.timeline_service = TimelineService()
        self.is_running = False
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self.last_check_time: Optional[datetime] = None
        self.check_count = 0
        self.last_dispatched: Dict[str, datetime] = {}

    def start(self) -> None:
        """Starts the background evaluation thread."""
        if self.is_running:
            return
        self.is_running = True
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, daemon=True, name="NICUReminderScheduler")
        self._thread.start()

    def stop(self) -> None:
        """Stops the background evaluation thread."""
        if not self.is_running:
            return
        self.is_running = False
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)

    def _run_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                self.evaluate_schedules()
            except Exception as e:
                import logging
                logging.getLogger("reminder_scheduler").error(f"Error in reminder loop: {e}")
            self._stop_event.wait(self.check_interval_seconds)

    def evaluate_schedules(self, force_baby_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Evaluates interval rules for active babies:
        1. Feeding interval: if time since last feed >= feeding_interval_hours
        2. KMC interval: if KMC is incomplete and >4 hours since last session
        3. Scheduled medications: matching current hour/minute
        """
        now = datetime.now()
        self.last_check_time = now
        self.check_count += 1
        dispatched_events = []

        # Dynamically discover all active babies and parents from registered users
        from .auth_service import auth_service
        all_users = auth_service.get_all_users()
        active_targets = []
        if force_baby_id:
            active_targets.append({"baby_id": force_baby_id, "user_id": "usr_mother_01"})
        else:
            for u in all_users.values():
                b_ids = u.get("assigned_baby_ids") or []
                for bid in b_ids:
                    active_targets.append({"baby_id": bid, "user_id": u.get("id", "usr_mother_01")})

        if not active_targets:
            active_targets = [{"baby_id": "baby_liam_01", "user_id": "usr_mother_01"}]

        for target in active_targets:
            baby_id = target["baby_id"]
            user_id = target["user_id"]
            prefs = notification_service.get_preferences(user_id=user_id)
            if not (prefs.email_enabled or prefs.sms_enabled):
                continue

            # ── 1. Feeding Interval Check ────────────────────────────────────
            feed_interval = prefs.feeding_interval_hours
            recent_feeds = self.care_log_service.get_feeds(baby_id, since_hours=24)
            needs_feed_reminder = False
            last_feed_time_str = "None recorded today"

            if recent_feeds:
                latest_feed = max(recent_feeds, key=lambda f: f.timestamp)
                last_feed_time_str = latest_feed.timestamp.strftime("%I:%M %p")
                hours_since_feed = (now - latest_feed.timestamp).total_seconds() / 3600.0
                if hours_since_feed >= feed_interval:
                    needs_feed_reminder = True
            else:
                # No feeds logged in 24 hours
                needs_feed_reminder = True

            # Dynamic Throttle: allow hourly reminders if interval <= 1.0 hour (30 min throttle)
            feed_throttle_key = f"{baby_id}_FEEDING"
            last_feed_notif = self.last_dispatched.get(feed_throttle_key)
            throttle_seconds = 1800 if feed_interval <= 1.0 else 2700
            vol_range = getattr(prefs, "feeding_volume_range", None) or f"{getattr(prefs, 'target_volume_ml', 50):.0f} mL"

            if needs_feed_reminder and (not last_feed_notif or (now - last_feed_notif).total_seconds() >= throttle_seconds):
                rec = notification_service.send_notification(
                    category=ReminderCategory.FEEDING,
                    baby_id=baby_id,
                    user_id=prefs.user_id,
                    channel=NotificationChannel.BOTH,
                    details={
                        "target_volume_ml": getattr(prefs, "target_volume_ml", 50.0),
                        "feeding_volume_range": vol_range,
                        "last_feed_time": last_feed_time_str
                    }
                )
                self.last_dispatched[feed_throttle_key] = now
                dispatched_events.append({
                    "baby_id": baby_id,
                    "category": "FEEDING",
                    "notification_id": rec.id,
                    "reason": f"Feed interval ({feed_interval}h) elapsed with target {vol_range}"
                })

            # ── 2. Kangaroo Mother Care (KMC) Interval Check ─────────────────
            kmc_interval = getattr(prefs, "kmc_interval_hours", 3.0)
            kmc_summary = self.timeline_service.get_daily_kmc_summary(baby_id)
            recent_kmc = self.timeline_service.get_kmc_sessions(baby_id)
            needs_kmc_reminder = False
            last_kmc_time_str = "None today"

            if recent_kmc:
                latest_kmc = max(recent_kmc, key=lambda k: k.timestamp)
                last_kmc_time_str = latest_kmc.timestamp.strftime("%I:%M %p")
                hours_since_kmc = (now - latest_kmc.timestamp).total_seconds() / 3600.0
                if hours_since_kmc >= kmc_interval and kmc_summary.get("remaining_hours", 0) > 0:
                    needs_kmc_reminder = True
            elif kmc_summary.get("remaining_hours", 0) > 0:
                needs_kmc_reminder = True

            kmc_throttle_key = f"{baby_id}_KMC"
            last_kmc_notif = self.last_dispatched.get(kmc_throttle_key)
            kmc_throttle_seconds = 1800 if kmc_interval <= 1.0 else 2700

            if needs_kmc_reminder and (not last_kmc_notif or (now - last_kmc_notif).total_seconds() >= kmc_throttle_seconds):
                rec = notification_service.send_notification(
                    category=ReminderCategory.KMC_SESSION,
                    baby_id=baby_id,
                    user_id=prefs.user_id,
                    channel=NotificationChannel.BOTH,
                    details={
                        "target_minutes": 60,
                        "last_kmc_time": last_kmc_time_str,
                        "remaining_hours": kmc_summary.get("remaining_hours", 2.0)
                    }
                )
                self.last_dispatched[kmc_throttle_key] = now
                dispatched_events.append({
                    "baby_id": baby_id,
                    "category": "KMC_SESSION",
                    "notification_id": rec.id,
                    "reason": f"KMC interval ({kmc_interval}h) elapsed (Last session: {last_kmc_time_str})"
                })

            # ── 3. Medication Routine Check ──────────────────────────────────
            if prefs.medication_reminder_enabled:
                current_time_str = now.strftime("%I:%M %p")
                for med_time in prefs.medication_times:
                    # Match hour/minute ignoring exact seconds
                    med_throttle_key = f"{baby_id}_MED_{now.strftime('%Y-%m-%d')}_{med_time}"
                    if med_throttle_key not in self.last_dispatched:
                        # Check if within 5-minute window of med_time
                        try:
                            t_parsed = datetime.strptime(med_time, "%I:%M %p").time()
                            t_now = now.time()
                            if t_parsed.hour == t_now.hour and abs(t_parsed.minute - t_now.minute) <= 3:
                                rec = notification_service.send_notification(
                                    category=ReminderCategory.MEDICATION,
                                    baby_id=baby_id,
                                    user_id=prefs.user_id,
                                    channel=NotificationChannel.BOTH,
                                    details={"med_name": "Vitamin D3 Drops (400 IU)", "dose": "1.0 mL oral syringe"}
                                )
                                self.last_dispatched[med_throttle_key] = now
                                dispatched_events.append({
                                    "baby_id": baby_id,
                                    "category": "MEDICATION",
                                    "notification_id": rec.id,
                                    "reason": f"Scheduled medication time {med_time} reached"
                                })
                        except Exception:
                            pass

        return {
            "status": "EVALUATED",
            "timestamp": now.strftime("%Y-%m-%d %H:%M:%S"),
            "check_count": self.check_count,
            "dispatched_count": len(dispatched_events),
            "dispatched_events": dispatched_events
        }

    def trigger_check_now(self, baby_id: str = "baby_liam_01") -> Dict[str, Any]:
        """Manually triggers an immediate interval schedule evaluation."""
        return self.evaluate_schedules(force_baby_id=baby_id)

    def get_status(self) -> Dict[str, Any]:
        """Returns scheduler operational health and configuration."""
        prefs = notification_service.get_preferences("usr_mother_01")
        return {
            "is_running": self.is_running,
            "check_interval_seconds": self.check_interval_seconds,
            "last_check_time": self.last_check_time.strftime("%Y-%m-%d %H:%M:%S") if self.last_check_time else "Never",
            "total_evaluations": self.check_count,
            "active_feeding_interval_hours": prefs.feeding_interval_hours,
            "registered_email": prefs.email,
            "registered_phone": prefs.phone_number,
            "channels_active": {
                "email": prefs.email_enabled,
                "sms": prefs.sms_enabled
            },
            "last_dispatched": {k: v.strftime("%I:%M %p") for k, v in self.last_dispatched.items()}
        }


# Global Singleton Scheduler
reminder_scheduler = ReminderScheduler(check_interval_seconds=60)
