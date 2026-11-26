"""
Unit tests for CareLogService and 48-Hour Rolling Summary Engine.
"""

import pytest
from datetime import datetime, timedelta
from app.models.care_log import FeedingEntry, DiaperEntry, MedicationEntry
from app.models.baby import BabyProfile
from app.services.care_log_service import CareLogService
from app.services.wiki_service import WikiService


@pytest.fixture
def clean_log_service(tmp_path, monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "logs_dir", tmp_path / "logs")
    monkeypatch.setattr(settings, "wiki_dir", tmp_path / "wiki")

    svc = CareLogService()
    svc.base_dir = tmp_path / "logs"
    svc.wiki_service.base_dir = tmp_path / "wiki"

    # Seed baby
    baby = BabyProfile(
        baby_id="test_baby_01",
        name="TestLiam",
        date_of_birth=datetime.now().date() - timedelta(days=56),
        gestational_age_weeks=29,
        gestational_age_days=2,
        sex="male",
        birth_weight_grams=1180,
        discharge_weight_grams=2000,
        discharge_date=datetime.now().date() - timedelta(days=20),
        discharge_hospital="Rainbow Vijayawada",
    )
    svc.wiki_service.save_baby_profile_json(baby)
    svc.wiki_service.create_profile_from_baby(baby)
    return svc


def test_log_feed_and_retrieve(clean_log_service):
    entry = FeedingEntry(
        baby_id="test_baby_01",
        volume_ml=45.0,
        feed_type="fortified_breast_milk",
        tolerated=True,
    )
    logged = clean_log_service.log_feed(entry)

    assert logged.entry_id is not None
    assert logged.volume_ml == 45.0

    feeds = clean_log_service.get_feeds("test_baby_01")
    assert len(feeds) == 1
    assert feeds[0].volume_ml == 45.0


def test_log_diaper_and_retrieve(clean_log_service):
    entry = DiaperEntry(
        baby_id="test_baby_01",
        wet=True,
        soiled=True,
        stool_color="yellow_seedy",
    )
    logged = clean_log_service.log_diaper(entry)

    assert logged.entry_id is not None
    diapers = clean_log_service.get_diapers("test_baby_01")
    assert len(diapers) == 1
    assert diapers[0].stool_color == "yellow_seedy"


def test_48h_summary_adequate_intake(clean_log_service):
    # 2kg baby requires min 300 mL/day -> 600 mL over 48h
    # Log 12 feeds of 55 mL = 660 mL
    for _ in range(12):
        clean_log_service.log_feed(FeedingEntry(
            baby_id="test_baby_01",
            volume_ml=55.0,
            feed_type="fortified_breast_milk",
            tolerated=True,
        ))

    # Log 10 wet diapers
    for _ in range(10):
        clean_log_service.log_diaper(DiaperEntry(
            baby_id="test_baby_01",
            wet=True,
            soiled=False,
        ))

    summary = clean_log_service.generate_48h_summary("test_baby_01")

    assert summary.total_feeds == 12
    assert summary.total_volume_ml == 660.0
    assert summary.daily_avg_volume_ml == 330.0
    assert summary.intake_target_status == "adequate"
    assert summary.wet_diaper_count == 10
    assert summary.has_concerning_stool is False
    assert len(summary.clinical_flags) == 0


def test_48h_summary_concerning_stool_flag(clean_log_service):
    # Log diaper with green/bilious stool
    clean_log_service.log_diaper(DiaperEntry(
        baby_id="test_baby_01",
        wet=True,
        soiled=True,
        stool_color="green",
    ))

    summary = clean_log_service.generate_48h_summary("test_baby_01")
    assert summary.has_concerning_stool is True
    assert "green" in summary.concerning_stool_colors
    assert any("stool color" in f.lower() for f in summary.clinical_flags)
