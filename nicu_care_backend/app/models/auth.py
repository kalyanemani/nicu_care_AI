"""
Authentication, Multi-Modal Database Architecture, and Agentic Memory Models.
"""
from enum import Enum
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, EmailStr, Field
import datetime


class UserRole(str, Enum):
    PARENT = "parent"
    CLINICIAN = "clinician"
    ADMIN = "admin"


class UserBase(BaseModel):
    email: EmailStr
    full_name: str
    phone_number: Optional[str] = "+919876543210"
    role: UserRole = UserRole.PARENT
    assigned_baby_ids: List[str] = Field(default_factory=lambda: ["baby_liam_01"])
    baby_name: Optional[str] = "Liam"


class UserRegister(UserBase):
    password: str
    baby_name: Optional[str] = "Liam"


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserResponse(UserBase):
    id: str
    created_at: str
    last_login: Optional[str] = None
    baby_name: Optional[str] = "Liam"


class StorageCategory(str, Enum):
    STRUCTURED = "structured"
    SEMI_STRUCTURED = "semi_structured"
    UNSTRUCTURED = "unstructured"


class StorageComponent(BaseModel):
    name: str
    category: StorageCategory
    engine: str
    location: str
    description: str
    schema_or_entities: List[str]
    item_count: int
    status: str = "active"


class MemoryTier(str, Enum):
    SHORT_TERM = "short_term"
    LONG_TERM = "long_term"
    EPISODIC = "episodic"


class MemoryComponent(BaseModel):
    tier: MemoryTier
    name: str
    management_strategy: str
    storage_engine: str
    description: str
    key_metrics: Dict[str, Any]


class StorageArchitectureSummary(BaseModel):
    structured: List[StorageComponent]
    semi_structured: List[StorageComponent]
    unstructured: List[StorageComponent]


class AgenticMemorySummary(BaseModel):
    short_term: MemoryComponent
    long_term: MemoryComponent
    episodic: MemoryComponent


class AuthSessionResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse
    storage_architecture: StorageArchitectureSummary
    agentic_memory_architecture: AgenticMemorySummary


class EpisodeType(str, Enum):
    ACUTE_EVENT = "ACUTE_EVENT"
    MILESTONE = "MILESTONE"
    REGIMEN_CHANGE = "REGIMEN_CHANGE"
    FEEDING_TOLERANCE = "FEEDING_TOLERANCE"
    KMC_SESSION = "KMC_SESSION"
    CLINICAL_CHECKUP = "CLINICAL_CHECKUP"


class EpisodeSeverity(str, Enum):
    INFO = "INFO"
    MILD = "MILD"
    MODERATE = "MODERATE"
    CRITICAL = "CRITICAL"


class EpisodicEvent(BaseModel):
    episode_id: str
    baby_id: str
    timestamp: float
    date: str
    episode_type: EpisodeType
    title: str
    description: str
    severity: EpisodeSeverity = EpisodeSeverity.INFO
    clinical_data: Dict[str, Any] = Field(default_factory=dict)
    resolved: bool = True
    resolution_notes: Optional[str] = None
    tags: List[str] = Field(default_factory=list)


class EpisodicEventCreate(BaseModel):
    episode_type: EpisodeType
    title: str
    description: str
    severity: EpisodeSeverity = EpisodeSeverity.INFO
    clinical_data: Dict[str, Any] = Field(default_factory=dict)
    resolved: bool = True
    resolution_notes: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
