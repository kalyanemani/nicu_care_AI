"""
Pydantic schemas for Hospital Emergency Contacts and Search Requests.
"""

from typing import Optional
from pydantic import BaseModel, Field


class HospitalSearchRequest(BaseModel):
    query: str = Field(..., description="Hospital name or location, e.g. 'BirthRight by Rainbow Hospital Vijayawada'")
    latitude: Optional[float] = None
    longitude: Optional[float] = None


class HospitalEmergencyContact(BaseModel):
    hospital_name: str = Field(..., description="Official hospital name")
    branch_location: str = Field(..., description="Branch or neighborhood location")
    emergency_phone: str = Field(..., description="24/7 general emergency contact")
    nicu_helpline: Optional[str] = Field(default=None, description="Dedicated NICU / Pediatric emergency line")
    ambulance_phone: Optional[str] = Field(default=None, description="Direct hospital ambulance line")
    full_address: str = Field(..., description="Physical street address")
    google_maps_url: str = Field(..., description="Direct Google Maps navigation URL")
    is_verified: bool = Field(default=True, description="True if verified in curated directory or official Places API")
