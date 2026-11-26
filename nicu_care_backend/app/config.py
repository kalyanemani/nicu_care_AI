import os
from pathlib import Path
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """
    Application configuration. Values are loaded from environment variables
    or the .env file. All have sensible local-dev defaults so the app runs
    out of the box without any external services.
    """

    # ── App Identity ──────────────────────────────────────────────────
    app_name: str = "NICU Care Backend"
    app_version: str = "1.0.0"
    debug: bool = True

    # ── Paths (local file-based storage, emulates Firestore) ─────────
    project_root: Path = Path(__file__).resolve().parent.parent
    data_dir: Path = project_root / "data"
    wiki_dir: Path = data_dir / "wiki"
    logs_dir: Path = data_dir / "logs"
    knowledge_dir: Path = Path(__file__).resolve().parent / "knowledge" / "guidelines"

    # ── API Keys (optional — only needed when using cloud services) ───
    gemini_api_key: Optional[str] = None
    google_maps_api_key: Optional[str] = None

    # ── Feature Flags ─────────────────────────────────────────────────
    use_cloud_firestore: bool = False   # False = local files, True = Firestore
    use_cloud_speech: bool = False      # False = text-only, True = GCP STT/TTS
    use_redis_cache: bool = False       # False = in-memory dict, True = Upstash Redis

    # ── Neo4j Aura Cloud Property Graph ──────────────────────────────
    neo4j_uri: Optional[str] = None
    neo4j_user: Optional[str] = None
    neo4j_password: Optional[str] = None

    # ── Obsidian Vault & Knowledge Integration ─────────────────────────
    obsidian_vault_dir: Optional[Path] = None
    obsidian_api_url: str = "http://127.0.0.1:27124"
    obsidian_api_key: Optional[str] = None

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


# Singleton settings instance used throughout the app
settings = Settings()

# Ensure local storage directories exist on startup
settings.wiki_dir.mkdir(parents=True, exist_ok=True)
settings.logs_dir.mkdir(parents=True, exist_ok=True)
