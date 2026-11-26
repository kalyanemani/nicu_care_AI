"""
Google Cloud Firestore Integration Service.
Provides persistent, serverless NoSQL storage for:
- User records & RBAC credentials ('users' collection)
- Baby profiles & clinical metadata ('babies' collection)
- Time-series feeding, diaper, and medication care logs ('babies/{baby_id}/logs' subcollections)
- Living Health Wiki sections ('babies/{baby_id}/wiki' subcollections)

Falls back safely to local disk files when Firestore client or credentials are not present.
"""

import os
import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional

logger = logging.getLogger("firestore_service")

# Check if google-cloud-firestore is installed
FIRESTORE_LIB_AVAILABLE = False
try:
    from google.cloud import firestore
    FIRESTORE_LIB_AVAILABLE = True
except ImportError:
    FIRESTORE_LIB_AVAILABLE = False


class FirestoreService:
    """Unified Cloud Firestore adapter with automated local file fallback."""

    def __init__(self, project_id: Optional[str] = None):
        self.project_id = project_id or os.getenv("GCP_PROJECT") or os.getenv("GOOGLE_CLOUD_PROJECT", "project-bd847704-1e76-422c-b26")
        self.db = None
        self._is_connected = False
        self._init_client()

    def _init_client(self):
        """Attempts to initialize the Firestore Native client."""
        if not FIRESTORE_LIB_AVAILABLE:
            logger.info("google-cloud-firestore package not installed. Running in local fallback mode.")
            return

        # Check if enabled by env
        use_firestore = os.getenv("USE_CLOUD_FIRESTORE", "false").lower() in ("true", "1", "yes")
        # In Cloud Run (K_SERVICE is set), automatically enable Firestore
        if os.getenv("K_SERVICE"):
            use_firestore = True

        if not use_firestore:
            logger.info("USE_CLOUD_FIRESTORE is false. Running in local fallback mode.")
            return

        try:
            self.db = firestore.Client(project=self.project_id)
            self._is_connected = True
            logger.info(f"Cloud Firestore successfully connected on project: {self.project_id}")
        except Exception as e:
            logger.warning(f"Could not connect to Cloud Firestore ({e}). Using local fallback.")
            self.db = None
            self._is_connected = False

    @property
    def is_connected(self) -> bool:
        return self._is_connected and self.db is not None

    # ── Users & Authentication ───────────────────────────────────────────

    def get_user(self, email: str) -> Optional[Dict[str, Any]]:
        """Retrieves user document by email lowercased."""
        if not self.is_connected:
            return None
        try:
            doc = self.db.collection("users").document(email.lower()).get()
            return doc.to_dict() if doc.exists else None
        except Exception as e:
            logger.warning(f"Firestore get_user error: {e}")
            return None

    def get_all_users(self) -> Dict[str, Dict[str, Any]]:
        """Retrieves all registered users as a dict keyed by email."""
        if not self.is_connected:
            return {}
        try:
            docs = self.db.collection("users").stream()
            users = {}
            for doc in docs:
                data = doc.to_dict()
                users[doc.id] = data
            return users
        except Exception as e:
            logger.warning(f"Firestore get_all_users error: {e}")
            return {}

    def save_user(self, email: str, user_data: Dict[str, Any]) -> bool:
        """Upserts a user document."""
        if not self.is_connected:
            return False
        try:
            self.db.collection("users").document(email.lower()).set(user_data, merge=True)
            return True
        except Exception as e:
            logger.warning(f"Firestore save_user error: {e}")
            return False

    def batch_save_users(self, users: Dict[str, Dict[str, Any]]) -> bool:
        """Batch saves users."""
        if not self.is_connected or not users:
            return False
        try:
            batch = self.db.batch()
            for email, data in users.items():
                ref = self.db.collection("users").document(email.lower())
                batch.set(ref, data, merge=True)
            batch.commit()
            return True
        except Exception as e:
            logger.warning(f"Firestore batch_save_users error: {e}")
            return False

    # ── Care Logs (Feeds, Diapers, Meds) ──────────────────────────────────

    def get_care_logs(self, baby_id: str, log_type: str) -> Optional[List[Dict[str, Any]]]:
        """Loads routine care logs for a baby."""
        if not self.is_connected:
            return None
        try:
            doc = self.db.collection("babies").document(baby_id).collection("care_logs").document(log_type).get()
            if doc.exists:
                return doc.to_dict().get("entries", [])
            return []
        except Exception as e:
            logger.warning(f"Firestore get_care_logs error: {e}")
            return None

    def save_care_logs(self, baby_id: str, log_type: str, entries: List[Dict[str, Any]]) -> bool:
        """Saves entire care log entries array."""
        if not self.is_connected:
            return False
        try:
            ref = self.db.collection("babies").document(baby_id).collection("care_logs").document(log_type)
            ref.set({"entries": entries, "updated_at": firestore.SERVER_TIMESTAMP}, merge=True)
            return True
        except Exception as e:
            logger.warning(f"Firestore save_care_logs error: {e}")
            return False

    # ── Living Baby Health Wiki & Profiles ───────────────────────────────

    def get_baby_profile(self, baby_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves structured baby profile."""
        if not self.is_connected:
            return None
        try:
            doc = self.db.collection("babies").document(baby_id).get()
            return doc.to_dict() if doc.exists else None
        except Exception as e:
            logger.warning(f"Firestore get_baby_profile error: {e}")
            return None

    def save_baby_profile(self, baby_id: str, profile_data: Dict[str, Any]) -> bool:
        """Saves structured baby profile."""
        if not self.is_connected:
            return False
        try:
            self.db.collection("babies").document(baby_id).set(profile_data, merge=True)
            return True
        except Exception as e:
            logger.warning(f"Firestore save_baby_profile error: {e}")
            return False

    def get_wiki_section(self, baby_id: str, section: str) -> Optional[str]:
        """Fetches markdown wiki section."""
        if not self.is_connected:
            return None
        try:
            doc = self.db.collection("babies").document(baby_id).collection("wiki").document(section).get()
            if doc.exists:
                return doc.to_dict().get("content")
            return None
        except Exception as e:
            logger.warning(f"Firestore get_wiki_section error: {e}")
            return None

    def save_wiki_section(self, baby_id: str, section: str, content: str) -> bool:
        """Stores markdown wiki section."""
        if not self.is_connected:
            return False
        try:
            ref = self.db.collection("babies").document(baby_id).collection("wiki").document(section)
            ref.set({"content": content, "updated_at": firestore.SERVER_TIMESTAMP}, merge=True)
            return True
        except Exception as e:
            logger.warning(f"Firestore save_wiki_section error: {e}")
            return False


# Global singleton
firestore_service = FirestoreService()
