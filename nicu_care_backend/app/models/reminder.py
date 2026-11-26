"""
Reminder and Notification Models for NICU HomeCare AI.
Defines notification channels, preferences, delivery audit logs, and trigger payloads.
"""
from enum import Enum
from typing import List, Dict, Any, Optional
from datetime import datetime
from pydantic import BaseModel, EmailStr, Field


class NotificationChannel(str, Enum):
    EMAIL = "email"
    SMS = "sms"
    BOTH = "both"


class ReminderCategory(str, Enum):
    FEEDING = "FEEDING"
    KMC = "KMC_SESSION"
    MEDICATION = "MEDICATION"
    HYGIENE = "HYGIENE"
    MILESTONE = "MILESTONE"
    SYSTEM_TEST = "SYSTEM_TEST"


class NotificationStatus(str, Enum):
    SENT = "SENT"
    SIMULATED = "SIMULATED"
    FAILED = "FAILED"


class NotificationPreferences(BaseModel):
    user_id: str = "usr_mother_01"
    baby_id: str = "baby_liam_01"
    email: EmailStr = "mother_liam@example.com"
    phone_number: str = "+919876543210"
    email_enabled: bool = True
    sms_enabled: bool = True
    feeding_interval_hours: float = Field(default=3.0, ge=0.5, le=6.0, description="Interval between feeds in hours (supports 1.0h hourly alerts up to 6.0h)")
    feeding_volume_range: str = Field(default="45-54 mL", description="Configured feeding volume range or manual volume target")
    target_volume_ml: float = Field(default=50.0, description="Manual or baseline volume in mL")
    kmc_interval_hours: float = Field(default=4.0, ge=1.0, le=12.0, description="Interval between Kangaroo Mother Care sessions")
    medication_reminder_enabled: bool = True
    medication_times: List[str] = Field(default_factory=lambda: ["10:00 AM", "06:00 PM"])
    hourly_updates_enabled: bool = Field(default=False, description="Whether to send proactive hourly care check updates")
    quiet_hours_enabled: bool = False
    quiet_hours_start: str = "23:00"
    quiet_hours_end: str = "06:00"
    last_updated: str = Field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))


class NotificationRecord(BaseModel):
    id: str
    timestamp: str = Field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    baby_id: str
    user_id: str
    recipient_email: Optional[str] = None
    recipient_phone: Optional[str] = None
    channel: NotificationChannel
    category: ReminderCategory
    title: str
    message_sms: str
    message_html: str
    status: NotificationStatus
    metadata: Dict[str, Any] = Field(default_factory=dict)


class SendTestReminderRequest(BaseModel):
    user_id: str = "usr_mother_01"
    baby_id: str = "baby_liam_01"
    category: ReminderCategory = ReminderCategory.FEEDING
    recipient_email: Optional[str] = None
    recipient_phone: Optional[str] = None
    channel: NotificationChannel = NotificationChannel.BOTH
    custom_note: Optional[str] = None
    feeding_volume_range: Optional[str] = "45-54 mL"
    target_volume_ml: Optional[float] = 50.0


class SendTestReminderResponse(BaseModel):
    success: bool
    notification_id: str
    category: str
    channel: str
    email_status: str
    sms_status: str
    recipient_email: str
    recipient_phone: str
    preview_sms: str
    preview_html: str
    timestamp: str
