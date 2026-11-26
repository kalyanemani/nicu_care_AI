"""
User Authentication and Identity Service for NICU HomeCare AI.

Manages:
- Secure PBKDF2 password hashing with salt
- JWT session token generation and verification
- Persistent user store (data/users.json) with RBAC (Parent, Clinician, Admin)
- Post-login session initialization delivering live Database Architecture and Agentic Memory status
"""
import os
import json
import time
import uuid
import hashlib
import hmac
from pathlib import Path
from typing import Dict, Any, List, Optional
import jwt

from ..models.auth import (
    UserRole,
    UserBase,
    UserRegister,
    UserLogin,
    UserResponse,
    AuthSessionResponse,
)
from .db_architecture_service import db_architecture_service

USERS_FILE = Path(__file__).resolve().parent.parent.parent / "data" / "users.json"
USERS_FILE.parent.mkdir(parents=True, exist_ok=True)

SECRET_KEY = os.getenv("JWT_SECRET_KEY", "nicu-homecare-ai-super-secure-jwt-secret-key-2026")
ALGORITHM = "HS256"
TOKEN_EXPIRY_SECONDS = 86400 * 7  # 7 days


class AuthService:
    """Authentication and Session Management Service."""

    def __init__(self, users_file: Optional[Path] = None):
        self.users_file = users_file or USERS_FILE
        self._ensure_default_users()

    def _hash_password(self, password: str, salt: Optional[str] = None) -> str:
        """PBKDF2-HMAC-SHA256 password hasher."""
        if not salt:
            salt = uuid.uuid4().hex[:16]
        key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 100000)
        return f"{salt}${key.hex()}"

    def _verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verifies password against stored PBKDF2 hash."""
        try:
            salt, stored_hash = hashed_password.split("$", 1)
            key = hashlib.pbkdf2_hmac("sha256", plain_password.encode("utf-8"), salt.encode("utf-8"), 100000)
            return hmac.compare_digest(key.hex(), stored_hash)
        except Exception:
            return False

    def _load_users(self) -> Dict[str, Dict[str, Any]]:
        from .firestore_service import firestore_service
        if firestore_service.is_connected:
            fs_users = firestore_service.get_all_users()
            if fs_users:
                return fs_users

        if not self.users_file.exists():
            return {}
        try:
            users = json.loads(self.users_file.read_text(encoding="utf-8"))
            if firestore_service.is_connected and users:
                firestore_service.batch_save_users(users)
            return users
        except Exception:
            return {}

    def _save_users(self, users: Dict[str, Dict[str, Any]]) -> None:
        try:
            self.users_file.write_text(json.dumps(users, indent=2), encoding="utf-8")
        except Exception:
            pass
        from .firestore_service import firestore_service
        if firestore_service.is_connected:
            firestore_service.batch_save_users(users)

    def _ensure_default_users(self) -> None:
        """Seeds default clinical, parent, and admin accounts if not present."""
        users = self._load_users()
        defaults = [
            {
                "id": "usr_mother_01",
                "email": "mother_liam@example.com",
                "password": "password123",
                "full_name": "Ananya Sharma (Liam's Mother)",
                "role": UserRole.PARENT.value,
                "assigned_baby_ids": ["baby_liam_01"],
            },
            {
                "id": "usr_dr_sharma_01",
                "email": "dr_sharma@rainbow.com",
                "password": "doctor123",
                "full_name": "Dr. K. Rao (Consultant Neonatologist)",
                "role": UserRole.CLINICIAN.value,
                "assigned_baby_ids": ["baby_liam_01", "vochetu1"],
            },
            {
                "id": "usr_admin_01",
                "email": "admin@nicucare.org",
                "password": "admin123",
                "full_name": "NICU Care System Administrator",
                "role": UserRole.ADMIN.value,
                "assigned_baby_ids": ["baby_liam_01", "vochetu1"],
            },
        ]

        changed = False
        for d in defaults:
            email_lower = d["email"].lower()
            if email_lower not in users:
                now_str = time.strftime("%Y-%m-%d %H:%M:%S")
                users[email_lower] = {
                    "id": d["id"],
                    "email": email_lower,
                    "password_hash": self._hash_password(d["password"]),
                    "full_name": d["full_name"],
                    "role": d["role"],
                    "assigned_baby_ids": d["assigned_baby_ids"],
                    "created_at": now_str,
                    "last_login": None,
                }
                changed = True

        if changed or not self.users_file.exists():
            self._save_users(users)

    def register_user(self, reg: UserRegister) -> UserResponse:
        """Registers a new user and associates their registered baby."""
        users = self._load_users()
        email_lower = reg.email.lower()
        if email_lower in users:
            raise ValueError(f"User with email '{reg.email}' already exists.")

        user_id = f"usr_{uuid.uuid4().hex[:8]}"
        now_str = time.strftime("%Y-%m-%d %H:%M:%S")

        phone = reg.phone_number or "+919876543210"
        registered_baby_name = (reg.baby_name or "Liam").strip()
        clean_slug = "".join(c for c in registered_baby_name.lower() if c.isalnum() or c == "_") or "baby"
        baby_id = f"baby_{clean_slug}_{uuid.uuid4().hex[:4]}"

        # Create and persist the BabyProfile with the user's actual registered baby name
        try:
            from .wiki_service import WikiService
            from ..models.baby import BabyProfile
            import datetime
            wiki = WikiService()
            b_profile = BabyProfile(
                baby_id=baby_id,
                name=registered_baby_name,
                date_of_birth=datetime.date.today() - datetime.timedelta(days=35),
                gestational_age_weeks=32,
                gestational_age_days=0,
                sex="male",
                birth_weight_grams=1800,
                discharge_weight_grams=2400,
                discharge_date=datetime.date.today() - datetime.timedelta(days=3),
                discharge_hospital="Post-NICU Pediatric Care Center",
                pediatrician_name="Dr. V. Sharma, Neonatologist",
                mother_preferred_language="en-US"
            )
            wiki.save_baby_profile_json(b_profile)
            wiki.create_profile_from_baby(b_profile)
        except Exception:
            pass

        assigned_babies = [baby_id]

        users[email_lower] = {
            "id": user_id,
            "email": email_lower,
            "password_hash": self._hash_password(reg.password),
            "full_name": reg.full_name,
            "phone_number": phone,
            "role": reg.role.value,
            "baby_name": registered_baby_name,
            "assigned_baby_ids": assigned_babies,
            "created_at": now_str,
            "last_login": None,
        }
        self._save_users(users)

        # Automatically tie registered email & mobile to proactive interval reminders
        try:
            from .notification_service import notification_service
            from ..models.reminder import NotificationPreferences
            notification_service.update_preferences(NotificationPreferences(
                user_id=user_id,
                baby_id=baby_id,
                email=reg.email,
                phone_number=phone,
                email_enabled=True,
                sms_enabled=True,
                feeding_interval_hours=1.0,
                feeding_volume_range="45–54 mL"
            ))
        except Exception:
            pass

        return UserResponse(
            id=user_id,
            email=reg.email,
            full_name=reg.full_name,
            phone_number=phone,
            role=reg.role,
            baby_name=registered_baby_name,
            assigned_baby_ids=assigned_babies,
            created_at=now_str,
            last_login=None,
        )

    def create_jwt_token(self, user_dict: Dict[str, Any]) -> str:
        """Generates a signed JWT access token."""
        payload = {
            "sub": user_dict["id"],
            "email": user_dict["email"],
            "role": user_dict["role"],
            "assigned_baby_ids": user_dict.get("assigned_baby_ids", []),
            "iat": int(time.time()),
            "exp": int(time.time()) + TOKEN_EXPIRY_SECONDS,
        }
        return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

    def verify_jwt_token(self, token: str) -> Dict[str, Any]:
        """Decodes and validates a JWT token."""
        try:
            return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        except jwt.ExpiredSignatureError:
            raise ValueError("Session token has expired. Please log in again.")
        except jwt.PyJWTError:
            raise ValueError("Invalid session token.")

    def login_user(self, creds: UserLogin) -> AuthSessionResponse:
        """
        Authenticates a user and delivers:
        1. Access Token and User profile
        2. Complete breakdown of Structured, Semi-Structured, and Unstructured Databases
        3. Real-time Agentic Memory status (Short, Long, Episodic)
        """
        users = self._load_users()
        email_lower = creds.email.lower()
        user_record = users.get(email_lower)

        if not user_record or not self._verify_password(creds.password, user_record["password_hash"]):
            raise ValueError("Invalid email or password.")

        # Update last login
        now_str = time.strftime("%Y-%m-%d %H:%M:%S")
        user_record["last_login"] = now_str
        users[email_lower] = user_record
        self._save_users(users)

        token = self.create_jwt_token(user_record)

        user_resp = UserResponse(
            id=user_record["id"],
            email=user_record["email"],
            full_name=user_record["full_name"],
            phone_number=user_record.get("phone_number", "+919876543210"),
            role=UserRole(user_record["role"]),
            baby_name=user_record.get("baby_name") or "Liam",
            assigned_baby_ids=user_record.get("assigned_baby_ids", ["baby_liam_01"]),
            created_at=user_record.get("created_at", now_str),
            last_login=now_str,
        )

        primary_baby = user_resp.assigned_baby_ids[0] if user_resp.assigned_baby_ids else "baby_liam_01"

        # Capture storage and agentic memory architecture
        storage_arch = db_architecture_service.get_storage_architecture(primary_baby)
        memory_arch = db_architecture_service.get_agentic_memory_summary(primary_baby)

        return AuthSessionResponse(
            access_token=token,
            token_type="bearer",
            user=user_resp,
            storage_architecture=storage_arch,
            agentic_memory_architecture=memory_arch,
        )

    def get_user_by_id(self, user_id: str) -> Optional[UserResponse]:
        """Finds user by ID."""
        users = self._load_users()
        for u in users.values():
            if u["id"] == user_id:
                return UserResponse(
                    id=u["id"],
                    email=u["email"],
                    full_name=u["full_name"],
                    phone_number=u.get("phone_number", "+919876543210"),
                    role=UserRole(u["role"]),
                    baby_name=u.get("baby_name") or "Liam",
                    assigned_baby_ids=u.get("assigned_baby_ids", []),
                    created_at=u.get("created_at", ""),
                    last_login=u.get("last_login"),
                )
        return None


# Global Singleton instance
auth_service = AuthService()
