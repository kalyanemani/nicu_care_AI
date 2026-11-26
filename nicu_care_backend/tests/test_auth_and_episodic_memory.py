"""
Unit and Integration Tests for User Authentication, Multi-Modal Database Architecture,
and Three-Tier Agentic Memory Management.
"""
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.auth_service import auth_service
from app.services.db_architecture_service import db_architecture_service
from app.memory.episodic_memory import episodic_memory, EpisodeType, EpisodeSeverity
from app.models.auth import UserLogin, UserRegister, UserRole

client = TestClient(app)


def test_auth_login_mother_success():
    """Verify mother login returns JWT and complete database + memory architecture."""
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": "mother_liam@example.com", "password": "password123"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["email"] == "mother_liam@example.com"
    assert data["user"]["role"] == "parent"

    # Verify structured databases present
    struct_dbs = data["storage_architecture"]["structured"]
    struct_names = [s["name"] for s in struct_dbs]
    assert any("Neo4j" in name for name in struct_names)
    assert any("Relational" in name for name in struct_names)
    assert any("User" in name for name in struct_names)

    # Verify semi-structured databases present
    semi_dbs = data["storage_architecture"]["semi_structured"]
    semi_names = [s["name"] for s in semi_dbs]
    assert any("Living Patient Health Wiki" in name for name in semi_names)
    assert any("Obsidian" in name for name in semi_names)

    # Verify unstructured databases present
    unstruct_dbs = data["storage_architecture"]["unstructured"]
    unstruct_names = [s["name"] for s in unstruct_dbs]
    assert any("Clinical Practice Guidelines" in name for name in unstruct_names)

    # Verify agentic memory management tiers present
    mem_arch = data["agentic_memory_architecture"]
    assert mem_arch["short_term"]["tier"] == "short_term"
    assert mem_arch["long_term"]["tier"] == "long_term"
    assert mem_arch["episodic"]["tier"] == "episodic"
    assert "token_savings_vs_transcripts" in mem_arch["long_term"]["key_metrics"]


def test_auth_login_clinician_success():
    """Verify neonatologist clinician login."""
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": "dr_sharma@rainbow.com", "password": "doctor123"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["user"]["role"] == "clinician"
    assert "baby_liam_01" in data["user"]["assigned_baby_ids"]


def test_auth_invalid_credentials():
    """Verify invalid password fails with 401."""
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": "mother_liam@example.com", "password": "wrong_password"},
    )
    assert resp.status_code == 401


def test_storage_and_memory_status_endpoint():
    """Verify public architecture inspection endpoint."""
    resp = client.get("/api/v1/auth/storage-and-memory-status?baby_id=baby_liam_01")
    assert resp.status_code == 200
    data = resp.json()
    assert data["baby_id"] == "baby_liam_01"
    assert len(data["storage_architecture"]["structured"]) >= 3
    assert len(data["storage_architecture"]["semi_structured"]) >= 3
    assert len(data["storage_architecture"]["unstructured"]) >= 3
    assert data["agentic_memory_architecture"]["episodic"]["name"] == "Longitudinal Clinical Episode Timeline"


def test_episodic_memory_lifecycle():
    """Verify recording and querying longitudinal clinical episodes."""
    # 1. Record an acute episode
    payload = {
        "episode_type": "ACUTE_EVENT",
        "title": "Mild Regurgitation Post-Feeding",
        "description": "Infant had 5 mL non-bilious regurgitation 20 minutes after 45 mL fortified feed. Vital signs normal, abdomen soft.",
        "severity": "MILD",
        "clinical_data": {
            "regurgitated_volume_ml": 5,
            "feed_volume_ml": 45,
            "bilious": False,
            "respiratory_rate": 44,
        },
        "resolved": True,
        "resolution_notes": "Burped upright in KMC position for 25 minutes; no further episodes.",
        "tags": ["reflux", "feeding_tolerance", "kmc"],
    }
    create_resp = client.post("/api/v1/memory/episodes/baby_liam_01", json=payload)
    assert create_resp.status_code == 200
    created = create_resp.json()
    assert created["title"] == "Mild Regurgitation Post-Feeding"
    assert created["severity"] == "MILD"
    assert created["episode_id"].startswith("ep_")

    # 2. Query episodes list
    list_resp = client.get("/api/v1/memory/episodes/baby_liam_01")
    assert list_resp.status_code == 200
    episodes = list_resp.json()
    assert len(episodes) >= 4  # Default 3 seeded + 1 newly added
    assert any(e["title"] == "Mild Regurgitation Post-Feeding" for e in episodes)

    # 3. Search episodes
    search_resp = client.get("/api/v1/memory/episodes/baby_liam_01/search?query=regurgitation")
    assert search_resp.status_code == 200
    results = search_resp.json()
    assert len(results) >= 1
    assert "regurgitation" in results[0]["title"].lower()

    # 4. Summary endpoint
    summary_resp = client.get("/api/v1/memory/episodes/baby_liam_01/summary")
    assert summary_resp.status_code == 200
    summary = summary_resp.json()
    assert summary["total_episodes_recorded"] >= 4
    assert "ACUTE_EVENT" in summary["episodes_by_type"]
