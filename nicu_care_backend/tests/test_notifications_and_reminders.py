"""
Comprehensive Unit & Integration Tests for Proactive Reminders and Multi-Channel Notifications.
Verifies:
1. Contact registration and preferences persistence (Email & Mobile).
2. Clinically grounded Email HTML & Mobile SMS template generation.
3. Multi-channel dispatching (Email, SMS, Both) and delivery audit trail.
4. Autonomous interval reminder scheduler logic (feeding overdue detection & throttling).
5. FastAPI REST endpoints under /api/v1/reminders/*.
6. MCP tools: mcp_send_reminder and mcp_get_reminder_preferences.
"""
import json
import pytest
from datetime import datetime, timedelta
from app.models.reminder import (
    NotificationChannel,
    ReminderCategory,
    NotificationStatus,
    NotificationPreferences,
    SendTestReminderRequest
)
from app.services.notification_service import notification_service
from app.services.reminder_scheduler import reminder_scheduler
from app.mcp.mcp_server import mcp_server
from app.routers.reminders import (
    get_preferences,
    update_preferences,
    send_test_reminder,
    trigger_interval_check,
    get_notification_history,
    get_scheduler_status
)


def test_notification_preferences_get_and_update():
    # 1. Retrieve preferences
    prefs = notification_service.get_preferences("usr_mother_01")
    assert prefs.user_id == "usr_mother_01"
    assert "@" in prefs.email
    assert prefs.phone_number is not None
    assert prefs.feeding_interval_hours > 0

    # 2. Update preferences
    updated_prefs = NotificationPreferences(
        user_id="usr_mother_01",
        baby_id="baby_liam_01",
        email="ananya.sharma@example.org",
        phone_number="+919876500000",
        feeding_interval_hours=2.5,
        kmc_interval_hours=3.5,
        email_enabled=True,
        sms_enabled=True,
        medication_reminder_enabled=True
    )
    saved = notification_service.update_preferences(updated_prefs)
    assert saved.email == "ananya.sharma@example.org"
    assert saved.phone_number == "+919876500000"
    assert saved.feeding_interval_hours == 2.5

    # 3. Verify persistence
    reloaded = notification_service.get_preferences("usr_mother_01")
    assert reloaded.email == "ananya.sharma@example.org"
    assert reloaded.feeding_interval_hours == 2.5


def test_clinical_template_generation():
    # Feeding template
    feed_tpl = notification_service.generate_templates(
        category=ReminderCategory.FEEDING,
        baby_name="Liam",
        details={"target_volume_ml": 50.0}
    )
    assert "Scheduled Feed" in feed_tpl["title"]
    assert "50 mL" in feed_tpl["sms"]
    assert "040-49694969" in feed_tpl["sms"]
    assert "<!DOCTYPE html>" in feed_tpl["html"]
    assert "Paced Bottle Feeding" in feed_tpl["html"]

    # KMC template
    kmc_tpl = notification_service.generate_templates(
        category=ReminderCategory.KMC,
        baby_name="Liam"
    )
    assert "Skin-to-Skin" in kmc_tpl["title"] or "Kangaroo" in kmc_tpl["title"]
    assert "60 continuous minutes" in kmc_tpl["sms"]

    # Medication template
    med_tpl = notification_service.generate_templates(
        category=ReminderCategory.MEDICATION,
        baby_name="Liam",
        details={"med_name": "Vitamin D3 Drops", "dose": "400 IU (1 mL)"}
    )
    assert "Vitamin D3" in med_tpl["title"]
    assert "oral syringe" in med_tpl["sms"]


def test_notification_dispatch_and_audit_log():
    # Dispatch test notification
    rec = notification_service.send_notification(
        category=ReminderCategory.FEEDING,
        baby_id="baby_liam_01",
        user_id="usr_mother_01",
        channel=NotificationChannel.BOTH,
        recipient_email="test_mother@example.com",
        recipient_phone="+919999988888",
        details={"target_volume_ml": 50.0}
    )
    assert rec.id.startswith("notif_")
    assert rec.category == ReminderCategory.FEEDING
    assert rec.recipient_email == "test_mother@example.com"
    assert rec.recipient_phone == "+919999988888"
    assert rec.status in [NotificationStatus.SENT, NotificationStatus.SIMULATED]

    # Check delivery audit log
    history = notification_service.get_history(baby_id="baby_liam_01", limit=10)
    assert len(history) > 0
    assert any(h.id == rec.id for h in history)

    # Check stats
    stats = notification_service.get_stats()
    assert stats["total_dispatched"] >= 1
    assert "FEEDING" in stats["categories"]


def test_reminder_scheduler_logic():
    # 1. Scheduler start and stop
    reminder_scheduler.start()
    assert reminder_scheduler.is_running is True

    # 2. Trigger check
    res = reminder_scheduler.trigger_check_now("baby_liam_01")
    assert res["status"] == "EVALUATED"
    assert "check_count" in res

    # 3. Status inspection
    status = reminder_scheduler.get_status()
    assert status["is_running"] is True
    assert status["check_interval_seconds"] == 60
    assert "registered_email" in status

    # 4. Clean stop
    reminder_scheduler.stop()
    assert reminder_scheduler.is_running is False


def test_fastapi_endpoints():
    # 1. GET preferences
    pref_res = get_preferences("usr_mother_01")
    assert pref_res.user_id == "usr_mother_01"

    # 2. POST send-test
    req = SendTestReminderRequest(
        user_id="usr_mother_01",
        baby_id="baby_liam_01",
        category=ReminderCategory.SYSTEM_TEST,
        channel=NotificationChannel.BOTH
    )
    test_res = send_test_reminder(req)
    assert test_res.success is True
    assert test_res.notification_id.startswith("notif_")
    assert test_res.email_status in ["SENT", "SIMULATED"]
    assert test_res.sms_status in ["SENT", "SIMULATED"]

    # 3. POST trigger-check
    eval_res = trigger_interval_check("baby_liam_01")
    assert eval_res["status"] == "EVALUATED"

    # 4. GET history
    hist_res = get_notification_history("baby_liam_01", limit=5)
    assert isinstance(hist_res, list)

    # 5. GET status
    stat_res = get_scheduler_status()
    assert "scheduler" in stat_res
    assert "delivery_stats" in stat_res


def test_mcp_reminder_tools():
    # 1. mcp_get_reminder_preferences
    res_prefs = mcp_server.call_tool("mcp_get_reminder_preferences", {"user_id": "usr_mother_01"})
    content_prefs = json.loads(res_prefs["content"][0]["text"])
    assert content_prefs["user_id"] == "usr_mother_01"
    assert "feeding_interval_hours" in content_prefs

    # 2. mcp_send_reminder
    res_send = mcp_server.call_tool("mcp_send_reminder", {
        "category": "KMC_SESSION",
        "baby_id": "baby_liam_01",
        "channel": "both",
        "custom_note": "Agentic reminder for afternoon skin-to-skin session."
    })
    content_send = json.loads(res_send["content"][0]["text"])
    assert content_send["id"].startswith("notif_")
    assert content_send["category"] == "KMC_SESSION"
