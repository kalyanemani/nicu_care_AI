"""
Pydantic schemas for Agent interaction (Text & Voice requests and responses).
"""

from typing import Optional, List
from pydantic import BaseModel, Field


class TextQueryRequest(BaseModel):
    baby_id: str = Field(..., description="Unique baby ID, e.g. 'baby_liam_01'")
    text: str = Field(..., min_length=1, description="Mother's query or care log statement")
    language: str = Field(default="en-US", description="Language code")
    model: Optional[str] = Field(default=None, description="Optional override model (e.g. 'medgemma1.5', 'llama3.1:8b')")


class VoiceQueryResponse(BaseModel):
    model_config = {"protected_namespaces": ()}

    text_card: str = Field(..., description="Markdown-formatted card for display on screen")
    voice_summary: str = Field(..., description="Concise 1-2 sentence soothing script for TTS")
    is_emergency: bool = Field(default=False, description="True if red-flag symptoms are present")
    detected_language: str = Field(default="en-US")
    intent: str = Field(default="CLINICAL_QA")
    wiki_updated: bool = Field(default=False)
    next_reminder_minutes: Optional[int] = Field(default=None)
    audio_base64: Optional[str] = Field(default=None, description="Base64 encoded MP3 audio (optional)")
    requires_hitl: bool = Field(default=False, description="True if human clinician review is required")
    hitl_ticket_id: Optional[str] = Field(default=None, description="HITL ticket ID if escalated")
    hitl_reasons: List[str] = Field(default_factory=list, description="Reasons for HITL escalation")
    hitl_urgency: Optional[str] = Field(default=None, description="Urgency of HITL review (LOW, MEDIUM, HIGH, CRITICAL)")
    model_used: Optional[str] = Field(default=None, description="Name of the model used to generate response")
