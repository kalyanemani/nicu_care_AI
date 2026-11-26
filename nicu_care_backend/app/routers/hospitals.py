"""
API Router for Hospital Emergency Contact Retrieval.
"""

from fastapi import APIRouter, HTTPException, Query
from ..models.hospital import HospitalEmergencyContact
from ..services.hospital_service import HospitalEmergencyService

router = APIRouter(prefix="/api/v1/hospitals", tags=["Hospital Emergency Service"])

hospital_service = HospitalEmergencyService()


@router.get("/search", response_model=HospitalEmergencyContact)
def search_hospital_emergency(
    query: str = Query(..., min_length=2, description="e.g. 'BirthRight by Rainbow Hospital Vijayawada'")
):
    """
    Retrieves verified 24/7 emergency hotlines, NICU helpline,
    ambulance numbers, and Google Maps directions for the specified hospital.
    """
    if not query.strip():
        raise HTTPException(status_code=400, detail="Hospital search query cannot be empty.")

    contact = hospital_service.search_hospital_emergency(query)
    return contact
