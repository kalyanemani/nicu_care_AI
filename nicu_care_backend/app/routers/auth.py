"""
Authentication and Memory Management API Router.

Provides endpoints for:
- User registration and JWT login
- Current session and RBAC profile
- Real-time Multi-Modal Storage Architecture inspection
- Agentic Memory inspection (Short-Term, Long-Term, Episodic)
- Episodic Memory recording and timeline querying
"""
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException, Depends, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from ..models.auth import (
    UserRegister,
    UserLogin,
    UserResponse,
    AuthSessionResponse,
    StorageArchitectureSummary,
    AgenticMemorySummary,
    EpisodicEvent,
    EpisodicEventCreate,
)
from ..services.auth_service import auth_service
from ..services.db_architecture_service import db_architecture_service
from ..memory.episodic_memory import episodic_memory

router = APIRouter(prefix="/api/v1/auth", tags=["Authentication & Agentic Architecture"])
memory_router = APIRouter(prefix="/api/v1/memory", tags=["Agentic Memory Management"])

security = HTTPBearer(auto_error=False)


def get_current_user(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)) -> UserResponse:
    """Dependency to extract and validate current authenticated user from Bearer JWT."""
    if not credentials:
        raise HTTPException(status_code=401, detail="Authentication credentials required.")
    token = credentials.credentials
    try:
        payload = auth_service.verify_jwt_token(token)
        user = auth_service.get_user_by_id(payload.get("sub"))
        if not user:
            raise HTTPException(status_code=401, detail="User account not found.")
        return user
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))


@router.post("/register", response_model=UserResponse)
def register(user_in: UserRegister):
    """Registers a new parent or clinician account."""
    try:
        return auth_service.register_user(user_in)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/login", response_model=AuthSessionResponse)
def login(creds: UserLogin):
    """
    Authenticates user and returns:
    - JWT Access Token
    - User Profile & RBAC role
    - Multi-Modal Database Architecture (Structured, Semi-Structured, Unstructured)
    - Three-Tier Agentic Memory Architecture (Short-Term, Long-Term, Episodic)
    """
    try:
        return auth_service.login_user(creds)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))


@router.get("/me")
def get_profile(current_user: UserResponse = Depends(get_current_user)):
    """Returns current user profile with their active baby storage overview."""
    from ..services.wiki_service import WikiService
    wiki = WikiService()
    primary_baby = current_user.assigned_baby_ids[0] if current_user.assigned_baby_ids else None
    baby = wiki.load_baby_profile_json(primary_baby) if primary_baby else None
    storage_arch = db_architecture_service.get_storage_architecture(primary_baby or "baby_default")
    memory_arch = db_architecture_service.get_agentic_memory_summary(primary_baby or "baby_default")
    return {
        "user": current_user,
        "baby": baby.model_dump(mode="json") if baby else {"baby_id": primary_baby or "baby_default", "name": current_user.baby_name or "Baby"},
        "storage_architecture": storage_arch,
        "agentic_memory_architecture": memory_arch,
    }


@router.put("/update-baby")
def update_baby(payload: Dict[str, str], current_user: UserResponse = Depends(get_current_user)):
    """Updates the user's registered baby name and profile."""
    baby_name = payload.get("baby_name", "").strip()
    if not baby_name:
        raise HTTPException(status_code=400, detail="Baby name is required.")
    try:
        updated_user = auth_service.update_user_baby_name(current_user.id, baby_name)
        from ..services.wiki_service import WikiService
        wiki = WikiService()
        primary_baby = updated_user.assigned_baby_ids[0] if updated_user.assigned_baby_ids else None
        baby = wiki.load_baby_profile_json(primary_baby) if primary_baby else None
        return {
            "user": updated_user,
            "baby": baby.model_dump(mode="json") if baby else {"baby_id": primary_baby or "baby_default", "name": updated_user.baby_name or baby_name},
            "status": "success",
            "message": f"Baby name successfully updated to {baby_name}."
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/storage-and-memory-status")
def get_architecture_status(baby_id: str = "baby_liam_01"):
    """
    Inspects live storage systems and agentic memory tiers:
    - Structured: Neo4j Knowledge Graph, Relational Care Logs, User Records
    - Semi-Structured: Living Patient Wiki, Obsidian Vault, Timelines & Telemetry
    - Unstructured: Clinical Guidelines Corpus, Audio Speech Payloads, Transcripts
    - Short-Term Memory: Redis/In-memory cache, turn buffer, scratchpads
    - Long-Term Memory: Living LLM Wiki (~350 tokens), persistent alerts
    - Episodic Memory: Longitudinal clinical episodes, milestones, acute alerts
    """
    return {
        "baby_id": baby_id,
        "storage_architecture": db_architecture_service.get_storage_architecture(baby_id),
        "agentic_memory_architecture": db_architecture_service.get_agentic_memory_summary(baby_id),
    }


# ── Episodic Memory Endpoints ─────────────────────────────────────────

@memory_router.get("/episodes/{baby_id}", response_model=List[Dict[str, Any]])
def list_episodes(
    baby_id: str,
    episode_type: Optional[str] = None,
    severity: Optional[str] = None,
    limit: int = 50,
):
    """Retrieves chronological clinical episodes from episodic memory."""
    return episodic_memory.get_episodes(baby_id, episode_type=episode_type, severity=severity, limit=limit)


@memory_router.post("/episodes/{baby_id}", response_model=EpisodicEvent)
def record_clinical_episode(baby_id: str, episode_in: EpisodicEventCreate):
    """Records a new discrete clinical episode and mirrors it to Obsidian Vault Daily Care Logs."""
    return episodic_memory.record_episode(
        baby_id=baby_id,
        episode_type=episode_in.episode_type,
        title=episode_in.title,
        description=episode_in.description,
        severity=episode_in.severity,
        clinical_data=episode_in.clinical_data,
        resolved=episode_in.resolved,
        resolution_notes=episode_in.resolution_notes,
        tags=episode_in.tags,
    )


@memory_router.get("/episodes/{baby_id}/summary")
def get_episodic_summary(baby_id: str):
    """Provides high-level aggregate summary of recorded clinical episodes."""
    return episodic_memory.get_summary(baby_id)


@memory_router.get("/episodes/{baby_id}/search")
def search_episodes(baby_id: str, query: str):
    """Semantic and keyword search over historical clinical episodes."""
    return episodic_memory.search_episodes(baby_id, query)
