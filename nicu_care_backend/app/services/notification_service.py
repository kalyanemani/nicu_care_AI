"""
Notification Service for NICU HomeCare AI.
Dispatches clinical reminders to parents' registered email addresses and mobile numbers.
Supports:
- Professional medical-grade HTML email templates with AAP/WHO clinical guidance
- Concise, urgent mobile SMS alerts
- Real SMTP / Twilio integrations when configured, with seamless offline sandbox simulation
- Persistent delivery audit logging and notification history
"""
import os
import json
import smtplib
import uuid
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

from ..models.reminder import (
    NotificationChannel,
    ReminderCategory,
    NotificationStatus,
    NotificationPreferences,
    NotificationRecord,
    SendTestReminderResponse
)

PREFS_FILE = Path(__file__).resolve().parent.parent.parent / "data" / "notification_preferences.json"
LOGS_FILE = Path(__file__).resolve().parent.parent.parent / "data" / "notifications_log.json"
PREFS_FILE.parent.mkdir(parents=True, exist_ok=True)


class NotificationService:
    """Manages reminder templates, multi-channel dispatch, and delivery audit logs."""

    def __init__(self):
        self.prefs_file = PREFS_FILE
        self.logs_file = LOGS_FILE
        self._ensure_default_preferences()

    # ── 1. Preferences Management ───────────────────────────────────────
    def _load_prefs(self) -> Dict[str, Dict[str, Any]]:
        if not self.prefs_file.exists():
            return {}
        try:
            return json.loads(self.prefs_file.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def _save_prefs(self, prefs: Dict[str, Dict[str, Any]]) -> None:
        self.prefs_file.write_text(json.dumps(prefs, indent=2), encoding="utf-8")

    def _ensure_default_preferences(self) -> None:
        prefs = self._load_prefs()
        if "usr_mother_01" not in prefs:
            prefs["usr_mother_01"] = {
                "user_id": "usr_mother_01",
                "baby_id": "baby_liam_01",
                "email": "mother_liam@example.com",
                "phone_number": "+919876543210",
                "email_enabled": True,
                "sms_enabled": True,
                "feeding_interval_hours": 3.0,
                "kmc_interval_hours": 4.0,
                "medication_reminder_enabled": True,
                "medication_times": ["10:00 AM", "06:00 PM"],
                "quiet_hours_enabled": False,
                "quiet_hours_start": "23:00",
                "quiet_hours_end": "06:00",
                "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            self._save_prefs(prefs)

    def get_preferences(self, user_id: str = "usr_mother_01") -> NotificationPreferences:
        prefs = self._load_prefs()
        user_pref = prefs.get(user_id)
        if not user_pref:
            # Fallback or default
            return NotificationPreferences(user_id=user_id)
        return NotificationPreferences(**user_pref)

    def update_preferences(self, preferences: NotificationPreferences) -> NotificationPreferences:
        prefs = self._load_prefs()
        preferences.last_updated = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        prefs[preferences.user_id] = preferences.model_dump()
        self._save_prefs(prefs)
        return preferences

    # ── 2. Audit Log Management ─────────────────────────────────────────
    def _load_logs(self) -> List[Dict[str, Any]]:
        if not self.logs_file.exists():
            return []
        try:
            return json.loads(self.logs_file.read_text(encoding="utf-8"))
        except Exception:
            return []

    def _save_logs(self, logs: List[Dict[str, Any]]) -> None:
        self.logs_file.write_text(json.dumps(logs[-300:], indent=2), encoding="utf-8")

    def get_history(self, baby_id: Optional[str] = None, limit: int = 50) -> List[NotificationRecord]:
        logs = self._load_logs()
        if baby_id:
            logs = [r for r in logs if r.get("baby_id") == baby_id]
        logs = sorted(logs, key=lambda x: x.get("timestamp", ""), reverse=True)
        return [NotificationRecord(**r) for r in logs[:limit]]

    def get_stats(self) -> Dict[str, Any]:
        logs = self._load_logs()
        return {
            "total_dispatched": len(logs),
            "sent_count": sum(1 for r in logs if r.get("status") == "SENT"),
            "simulated_count": sum(1 for r in logs if r.get("status") == "SIMULATED"),
            "failed_count": sum(1 for r in logs if r.get("status") == "FAILED"),
            "categories": {
                "FEEDING": sum(1 for r in logs if r.get("category") == "FEEDING"),
                "KMC_SESSION": sum(1 for r in logs if r.get("category") == "KMC_SESSION"),
                "MEDICATION": sum(1 for r in logs if r.get("category") == "MEDICATION"),
                "SYSTEM_TEST": sum(1 for r in logs if r.get("category") == "SYSTEM_TEST"),
            }
        }

    # ── 3. Template Generation ──────────────────────────────────────────
    def generate_templates(
        self,
        category: ReminderCategory,
        baby_name: str = "Your Baby",
        details: Optional[Dict[str, Any]] = None
    ) -> Dict[str, str]:
        """Generates clinically grounded Subject, SMS text, and HTML email body."""
        raw_name = (baby_name or "Your Baby").strip()
        # Prevent awkward "Baby Baby X" or "Baby Your baby's"
        if raw_name.lower().startswith("baby "):
            display_name = raw_name
        elif raw_name.lower() in ["your baby", "the baby", "infant"]:
            display_name = "Your Baby"
        else:
            display_name = f"Baby {raw_name.capitalize()}"

        short_name = raw_name.replace("Baby ", "").replace("baby ", "").capitalize()
        details = details or {}
        time_now = datetime.now().strftime("%I:%M %p")

        if category == ReminderCategory.FEEDING:
            vol_range = details.get("feeding_volume_range") or (f"{details.get('target_volume_ml', 50):.0f} mL" if isinstance(details.get("target_volume_ml"), (int, float)) else str(details.get("target_volume_ml", "45–54 mL")))
            subject = f"🍼 [NICU Care Alert] Time for {display_name}'s Scheduled Feed ({vol_range})"
            sms = (
                f"[NICU Alert] Time for {display_name}'s {time_now} Feed! "
                f"Target: {vol_range} fortified breast milk. Paced upright feed, burp frequently. "
                f"24/7 NICU Helpline: 040-49694969"
            )
            html = f"""<!DOCTYPE html>
<html>
<head>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 0; padding: 20px; background-color: #f8fafc; color: #1e293b; }}
  .card {{ max-width: 580px; margin: auto; background: #ffffff; border-radius: 12px; overflow: hidden; border: 1px solid #e2e8f0; box-shadow: 0 4px 12px rgba(0,0,0,0.05); }}
  .header {{ background: linear-gradient(135deg, #0284c7, #0369a1); color: white; padding: 24px; text-align: center; }}
  .header h2 {{ margin: 0; font-size: 22px; font-weight: 700; }}
  .header p {{ margin: 6px 0 0 0; opacity: 0.9; font-size: 13px; letter-spacing: 0.5px; }}
  .content {{ padding: 24px; }}
  .alert-pill {{ display: inline-block; background: #e0f2fe; color: #0369a1; padding: 6px 14px; border-radius: 20px; font-size: 13px; font-weight: 600; margin-bottom: 16px; }}
  .box {{ background: #f0f9ff; border-left: 4px solid #0284c7; padding: 14px 16px; border-radius: 4px; margin: 16px 0; }}
  .stat-grid {{ display: flex; gap: 12px; margin: 16px 0; }}
  .stat {{ flex: 1; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 12px; text-align: center; }}
  .stat-val {{ font-size: 20px; font-weight: 700; color: #0284c7; }}
  .stat-lbl {{ font-size: 11px; color: #64748b; text-transform: uppercase; margin-top: 4px; }}
  ul {{ padding-left: 20px; line-height: 1.6; color: #334155; }}
  .footer {{ background: #f1f5f9; padding: 16px; text-align: center; font-size: 12px; color: #64748b; border-top: 1px solid #e2e8f0; }}
  .btn {{ display: inline-block; background: #0284c7; color: white; text-decoration: none; padding: 10px 20px; border-radius: 6px; font-weight: 600; margin-top: 10px; }}
</style>
</head>
<body>
<div class="card">
  <div class="header">
    <h2>🍼 Scheduled Feeding Reminder</h2>
    <p>NICU HOMECARE AI • PRETERM CLINICAL COMPANION</p>
  </div>
  <div class="content">
    <div class="alert-pill">⏰ Interval Target ({time_now})</div>
    <p>Hello, it is time for <strong>{display_name}'s</strong> scheduled feeding.</p>
    
    <div class="box">
      <strong>Recommended Feed Volume Target:</strong> <span style="font-size: 18px; color: #0284c7; font-weight: bold;">{vol_range}</span> fortified breast milk (24 kcal/oz).
    </div>

    <h3>Clinical Care Instructions (AAP / WHO Protocol):</h3>
    <ul>
      <li><strong>Paced Bottle Feeding:</strong> Hold baby in a semi-upright position with the bottle horizontal to prevent swallowing air or gulping.</li>
      <li><strong>Mid-Feed Burping:</strong> Gently burp after every 15–20 mL to relieve trapped gastric air.</li>
      <li><strong>Satiety Cues:</strong> If baby pushes bottle away, slows sucking, or falls into calm sleep, do not force them to finish.</li>
      <li><strong>Safe Sleep Post-Feed:</strong> Keep baby upright for 15 minutes before placing Back to Sleep in an empty crib.</li>
    </ul>

    <div style="text-align: center; margin: 20px 0;">
      <a href="tel:04049694969" class="btn">🚨 24/7 NICU Helpline: 040-49694969</a>
    </div>
  </div>
  <div class="footer">
    Sent automatically by NICU HomeCare AI • Dedicated to {display_name}'s Growth & Thermal Stability
  </div>
</div>
</body>
</html>"""

        elif category == ReminderCategory.KMC:
            subject = f"🦘 [NICU Care Alert] Kangaroo Mother Care (Skin-to-Skin) Session for {display_name}"
            sms = (
                f"[NICU Alert] Time for {display_name}'s Skin-to-Skin KMC Session! "
                f"WHO recommends min 60 continuous minutes upright on bare chest. "
                f"Keep room at 22-24°C. Helpline: 040-49694969"
            )
            html = f"""<!DOCTYPE html>
<html>
<head>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 0; padding: 20px; background-color: #f8fafc; color: #1e293b; }}
  .card {{ max-width: 580px; margin: auto; background: #ffffff; border-radius: 12px; overflow: hidden; border: 1px solid #e2e8f0; }}
  .header {{ background: linear-gradient(135deg, #059669, #047857); color: white; padding: 24px; text-align: center; }}
  .content {{ padding: 24px; }}
  .box {{ background: #ecfdf5; border-left: 4px solid #059669; padding: 14px 16px; border-radius: 4px; margin: 16px 0; }}
  ul {{ padding-left: 20px; line-height: 1.6; color: #334155; }}
  .footer {{ background: #f1f5f9; padding: 16px; text-align: center; font-size: 12px; color: #64748b; }}
</style>
</head>
<body>
<div class="card">
  <div class="header">
    <h2>🦘 Kangaroo Mother Care (KMC) Time</h2>
    <p>RAINBOW CHILDREN'S HOSPITAL • THERMAL CARE</p>
  </div>
  <div class="content">
    <p>Hello, it is time for <strong>{display_name}'s</strong> daily Kangaroo Mother Care session.</p>
    <div class="box">
      <strong>Target Duration:</strong> Minimum 60 continuous minutes (WHO Clinical Standard).
    </div>
    <h3>KMC Best Practice Checklist:</h3>
    <ul>
      <li>Place baby diapered and upright against your bare chest in the frog-leg position.</li>
      <li>Turn baby's head gently to one side with airway completely open and clear.</li>
      <li>Cover baby with a warm cotton wrap or blanket. Ensure nursery room is comfortably warm (22°C to 24°C).</li>
      <li>Skin-to-skin stabilizes preterm heart rate, oxygenation, and accelerates neurodevelopment.</li>
    </ul>
  </div>
  <div class="footer">NICU HomeCare AI • Safe Thermal & Kangaroo Care Protocol</div>
</div>
</body>
</html>"""

        elif category == ReminderCategory.MEDICATION:
            med_name = details.get("med_name", "Vitamin D3 Drops (400 IU)")
            dose = details.get("dose", "1.0 mL oral syringe")
            subject = f"💊 [NICU Care Alert] Prescribed Medication Reminder: {med_name} for {display_name}"
            sms = (
                f"[NICU Alert] Medication Due for {display_name}: {med_name} ({dose}). "
                f"Administer with measured oral syringe. Do not mix into hot milk. "
                f"Questions? Call NICU: 040-49694969"
            )
            html = f"""<!DOCTYPE html>
<html>
<head>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, sans-serif; background: #f8fafc; padding: 20px; }}
  .card {{ max-width: 580px; margin: auto; background: white; border-radius: 12px; border: 1px solid #e2e8f0; }}
  .header {{ background: #7c3aed; color: white; padding: 20px; text-align: center; border-radius: 12px 12px 0 0; }}
  .content {{ padding: 24px; }}
  .box {{ background: #f5f3ff; border-left: 4px solid #7c3aed; padding: 12px 16px; margin: 16px 0; }}
</style>
</head>
<body>
<div class="card">
  <div class="header">
    <h2>💊 Prescribed Medication Due</h2>
    <p>RAINBOW CHILDREN'S HOSPITAL • DISCHARGE PHARMACOTHERAPY</p>
  </div>
  <div class="content">
    <div class="box">
      <strong>Patient:</strong> {display_name}<br>
      <strong>Medication:</strong> {med_name}<br>
      <strong>Prescribed Dose:</strong> {dose}
    </div>
    <p>Administer between feeds using the dedicated oral syringe. Do not double doses if delayed.</p>
  </div>
</div>
</body>
</html>"""

        else:  # SYSTEM_TEST or GENERAL
            subject = f"🔔 [NICU Companion] Test Reminder Notification for {display_name}"
            sms = (
                f"[NICU Alert] Test Notification for {display_name}! "
                f"Your registered email & mobile are connected and receiving interval care alerts. "
                f"Rainbow NICU Helpline: 040-49694969"
            )
            html = f"""<!DOCTYPE html>
<html>
<head>
<style>
  body {{ font-family: sans-serif; background: #f8fafc; padding: 20px; }}
  .card {{ max-width: 580px; margin: auto; background: white; border-radius: 12px; border: 1px solid #e2e8f0; padding: 24px; }}
  .header {{ color: #0284c7; text-align: center; }}
</style>
</head>
<body>
<div class="card">
  <div class="header">
    <h2>🔔 NICU HomeCare Notification Test Successful</h2>
  </div>
  <p>Hello,</p>
  <p>This is a confirmed test of the NICU Care Companion interval reminder system for <strong>{display_name}</strong>.</p>
  <p>You will receive automated reminders at regular intervals for:</p>
  <ul>
    <li>Scheduled feeds (every 2.5–3 hours)</li>
    <li>Kangaroo Mother Care sessions</li>
    <li>Prescribed morning & evening vitamins/iron drops</li>
  </ul>
  <p>Stay assured—our 24/7 NICU Clinical Helpline is always active at <strong>040-49694969</strong>.</p>
</div>
</body>
</html>"""

        return {
            "title": subject,
            "sms": sms,
            "html": html
        }

    # ── 4. Multi-Channel Dispatcher ──────────────────────────────────────
    def send_notification(
        self,
        category: ReminderCategory,
        baby_id: str = "baby_default",
        user_id: str = "usr_mother_01",
        channel: NotificationChannel = NotificationChannel.BOTH,
        recipient_email: Optional[str] = None,
        recipient_phone: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        baby_name: Optional[str] = None,
    ) -> NotificationRecord:
        """
        Dispatches notification via Email and/or SMS.
        Uses real SMTP / Twilio / Fast2SMS gateway if credentials exist; otherwise executes
        high-fidelity offline sandbox simulation with full delivery audit trail.
        """
        prefs = self.get_preferences(user_id)
        email = recipient_email or prefs.email
        phone = recipient_phone or prefs.phone_number

        # Dynamically resolve real baby name
        resolved_name = (baby_name or "").strip()
        if not resolved_name or resolved_name.lower() in ["your baby", "baby", "liam"]:
            try:
                from .wiki_service import WikiService
                wiki = WikiService()
                prof = wiki.load_baby_profile_json(baby_id)
                if prof and prof.name:
                    resolved_name = prof.name
            except Exception:
                pass

        if not resolved_name or resolved_name.lower() in ["your baby", "baby", "liam"]:
            try:
                from .auth_service import auth_service
                u = auth_service.get_user_by_id(user_id)
                if u and u.baby_name:
                    resolved_name = u.baby_name
            except Exception:
                pass

        if not resolved_name:
            resolved_name = "Your Baby"

        templates = self.generate_templates(category, baby_name=resolved_name, details=details)

        email_status = "SKIPPED"
        sms_status = "SKIPPED"

        # A. Email Dispatch
        if channel in [NotificationChannel.EMAIL, NotificationChannel.BOTH] and prefs.email_enabled:
            smtp_host = os.getenv("SMTP_HOST")
            if smtp_host:
                try:
                    port = int(os.getenv("SMTP_PORT", 587))
                    user = os.getenv("SMTP_USER", "")
                    pw = os.getenv("SMTP_PASSWORD", "")
                    msg = MIMEMultipart("alternative")
                    msg["Subject"] = templates["title"]
                    msg["From"] = user or "nicu-companion@rainbow.org"
                    msg["To"] = email
                    msg.attach(MIMEText(templates["sms"], "plain"))
                    msg.attach(MIMEText(templates["html"], "html"))

                    with smtplib.SMTP(smtp_host, port, timeout=5) as server:
                        if os.getenv("SMTP_USE_TLS", "true").lower() == "true":
                            server.starttls()
                        if user and pw:
                            server.login(user, pw)
                        server.sendmail(msg["From"], [email], msg.as_string())
                    email_status = "SENT"
                except Exception as e:
                    email_status = f"FAILED: {str(e)[:60]}"
            else:
                email_status = "SIMULATED"

        # B. SMS Dispatch
        if channel in [NotificationChannel.SMS, NotificationChannel.BOTH] and prefs.sms_enabled:
            twilio_sid = os.getenv("TWILIO_ACCOUNT_SID")
            fast2sms_key = os.getenv("FAST2SMS_API_KEY")
            raw_phone = str(phone or "").strip()

            if twilio_sid and raw_phone:
                try:
                    import requests
                    auth_token = os.getenv("TWILIO_AUTH_TOKEN")
                    from_num = os.getenv("TWILIO_PHONE_NUMBER")
                    # Ensure E.164 international format
                    target_phone = raw_phone if raw_phone.startswith("+") else f"+{raw_phone}"
                    url = f"https://api.twilio.com/2010-04-01/Accounts/{twilio_sid}/Messages.json"
                    r = requests.post(
                        url,
                        data={"From": from_num, "To": target_phone, "Body": templates["sms"]},
                        auth=(twilio_sid, auth_token),
                        timeout=5
                    )
                    sms_status = "SENT" if r.status_code in [200, 201] else f"FAILED: {r.status_code} ({r.text[:60]})"
                except Exception as e:
                    sms_status = f"FAILED: {str(e)[:60]}"
            elif fast2sms_key and raw_phone:
                try:
                    import requests
                    clean_phone = re.sub(r'[^0-9]', '', raw_phone)
                    if clean_phone.startswith("91") and len(clean_phone) > 10:
                        clean_phone = clean_phone[2:]
                    url = "https://www.fast2sms.com/dev/bulkV2"
                    payload = {
                        "route": "q",
                        "message": templates["sms"],
                        "language": "english",
                        "flash": 0,
                        "numbers": clean_phone,
                    }
                    headers = {
                        "authorization": fast2sms_key,
                        "Content-Type": "application/x-www-form-urlencoded"
                    }
                    r = requests.post(url, data=payload, headers=headers, timeout=5)
                    sms_status = "SENT" if (r.status_code == 200 and r.json().get("return") is True) else f"FAILED: {r.text[:50]}"
                except Exception as e:
                    sms_status = f"FAILED: {str(e)[:60]}"
            else:
                sms_status = "SIMULATED"

        overall_status = NotificationStatus.SENT if (email_status == "SENT" or sms_status == "SENT") else NotificationStatus.SIMULATED

        record = NotificationRecord(
            id=f"notif_{uuid.uuid4().hex[:10]}",
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            baby_id=baby_id,
            user_id=user_id,
            recipient_email=email,
            recipient_phone=phone,
            channel=channel,
            category=category,
            title=templates["title"],
            message_sms=templates["sms"],
            message_html=templates["html"],
            status=overall_status,
            metadata={
                "email_delivery": email_status,
                "sms_delivery": sms_status,
                "details": details or {}
            }
        )

        logs = self._load_logs()
        logs.append(record.model_dump())
        self._save_logs(logs)

        return record


# Global Singleton Notification Service
notification_service = NotificationService()
