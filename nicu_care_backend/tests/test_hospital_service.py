"""
Unit tests for HospitalEmergencyService.
"""

import pytest
from app.services.hospital_service import HospitalEmergencyService


@pytest.fixture
def hospital_service():
    return HospitalEmergencyService()


def test_rainbow_vijayawada_lookup(hospital_service):
    contact = hospital_service.search_hospital_emergency("BirthRight by Rainbow Hospital Vijayawada")

    assert contact.is_verified is True
    assert "Rainbow" in contact.hospital_name
    assert "Vijayawada" in contact.branch_location
    assert contact.emergency_phone == "+91 866 666 9000"
    assert contact.nicu_helpline == "+91 866 669 0000"
    assert contact.ambulance_phone == "0866-2459999"
    assert "Currency Nagar" in contact.full_address


def test_rainbow_hyderabad_lookup(hospital_service):
    contact = hospital_service.search_hospital_emergency("Rainbow Hospital Banjara Hills Hyderabad")

    assert contact.is_verified is True
    assert "Hyderabad" in contact.branch_location
    assert contact.emergency_phone == "+91 40 4466 5555"
    assert contact.nicu_helpline == "+91 40 4466 5500"


def test_fernandez_hyderabad_lookup(hospital_service):
    contact = hospital_service.search_hospital_emergency("Fernandez Hospital Hyderabad")

    assert contact.is_verified is True
    assert "Fernandez" in contact.hospital_name
    assert "+91 40 4063 2000" in contact.emergency_phone


def test_cloudnine_bangalore_lookup(hospital_service):
    contact = hospital_service.search_hospital_emergency("Cloudnine Hospital Bangalore")

    assert contact.is_verified is True
    assert "Cloudnine" in contact.hospital_name
    assert "+91 80 6792 9999" in contact.emergency_phone


def test_unknown_hospital_fallback_to_national_emergency(hospital_service):
    # Unlisted hospital should safely fallback to 108/102 and generate Google Maps search link
    contact = hospital_service.search_hospital_emergency("St Marys Maternity Clinic Smalltown")

    assert contact.is_verified is False
    assert contact.emergency_phone == "108"
    assert contact.nicu_helpline == "102"
    assert contact.ambulance_phone == "108"
    assert "google.com/maps" in contact.google_maps_url
