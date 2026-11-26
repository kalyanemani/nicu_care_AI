"""
FastAPI Router for Interval Reminders and Multi-Channel Notifications.
Exposes endpoints to view/update contact preferences, trigger test reminders,
evaluate interval schedules, and inspect delivery audit history.
"""
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Query, Path

from ..models.reminder import (
    NotificationPreferences,
    NotificationRecord,
    SendTestReminderRequest,
    SendTestReminderResponse,
    ReminderCategory,
    NotificationChannel
)
from ..services.notification_service import notification_service
from ..services.reminder_scheduler import reminder_scheduler

router = APIRouter(prefix="/api/v1/reminders", tags=["Reminders & Notifications"])


@router.get("/preferences/{user_id}", response_model=NotificationPreferences)
def get_preferences(user_id: str = Path(..., description="User ID, e.g. usr_mother_01")):
    """Retrieves registered email, phone number, and reminder intervals."""
    return notification_service.get_preferences(user_id)


@router.put("/preferences/{user_id}", response_model=NotificationPreferences)
def update_preferences(user_id: str, prefs: NotificationPreferences):
    """Updates registered email address, mobile number, feeding interval, and notification toggles."""
    if prefs.user_id != user_id:
        prefs.user_id = user_id
    return notification_service.update_preferences(prefs)


@router.post("/send-test", response_model=SendTestReminderResponse)
def send_test_reminder(req: SendTestReminderRequest):
    """
    Triggers an immediate test notification via Email and/or SMS
    to verify parent contact delivery and show template previews.
    """
    rec = notification_service.send_notification(
        category=req.category,
        baby_id=req.baby_id,
        user_id=req.user_id,
        channel=req.channel,
        recipient_email=req.recipient_email,
        recipient_phone=req.recipient_phone,
        details={
            "custom_note": req.custom_note,
            "target_volume_ml": req.target_volume_ml or 50.0,
            "feeding_volume_range": req.feeding_volume_range or "45-54 mL"
        }
    )

    meta = rec.metadata or {}
    return SendTestReminderResponse(
        success=rec.status != "FAILED",
        notification_id=rec.id,
        category=rec.category.value,
        channel=rec.channel.value,
        email_status=meta.get("email_delivery", "N/A"),
        sms_status=meta.get("sms_delivery", "N/A"),
        recipient_email=rec.recipient_email or "None",
        recipient_phone=rec.recipient_phone or "None",
        preview_sms=rec.message_sms,
        preview_html=rec.message_html,
        timestamp=rec.timestamp
    )


@router.post("/trigger-check")
def trigger_interval_check(baby_id: str = Query("baby_liam_01")):
    """Immediately evaluates interval timers (feeding, KMC, medications) and dispatches any overdue alerts."""
    return reminder_scheduler.trigger_check_now(baby_id=baby_id)


@router.get("/history/{baby_id}", response_model=List[NotificationRecord])
def get_notification_history(baby_id: str, limit: int = Query(50, ge=1, le=200)):
    """Retrieves delivery audit history of all sent/simulated reminders for the given baby."""
    return notification_service.get_history(baby_id=baby_id, limit=limit)


@router.get("/status")
def get_scheduler_status():
    """Returns background reminder worker status, check frequency, and dispatch metrics."""
    sched_status = reminder_scheduler.get_status()
    notif_stats = notification_service.get_stats()
    return {
        "scheduler": sched_status,
        "delivery_stats": notif_stats
    }
