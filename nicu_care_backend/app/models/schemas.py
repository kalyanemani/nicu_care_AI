from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any

class HospitalSearchRequest(BaseModel):
    query: str = Field(..., description="Hospital name or location, e.g., 'BirthRight by Rainbow Hospital Vijayawada'")
    latitude: Optional[float] = None
    longitude: Optional[float] = None

class HospitalEmergencyContact(BaseModel):
    hospital_name: str
    branch_location: str
    emergency_phone: str
    nicu_helpline: Optional[str] = None
    ambulance_phone: Optional[str] = None
    full_address: str
    google_maps_url: str
    is_verified: bool = True

class VoiceQueryResponse(BaseModel):
    text_card: str
    voice_summary: str
    is_emergency: bool
    detected_language: str
    audio_base64: Optional[str] = None

