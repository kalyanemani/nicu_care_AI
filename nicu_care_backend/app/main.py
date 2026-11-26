"""
NICU Care Backend — FastAPI Application Entry Point

Registers all routers and configures middleware.
Run locally: python -m uvicorn app.main:app --reload --port 8000
"""

import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .routers import baby, wiki, care_logs, hospitals, agent, telemetry, mcp, timeline, obsidian, auth, neonatal_bert, reminders

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=(
        "Backend service for the Post-NICU Baby Care Companion. "
        "Provides baby profile management, corrected age calculation, "
        "clinical care logging, hospital emergency lookup, "
        "LangGraph multi-agent voice/text reasoning, and regular interval reminders."
    ),
)

@app.on_event("startup")
def startup_event():
    """Starts the autonomous background reminder scheduler."""
    if os.getenv("TESTING", "false").lower() != "true":
        from .services.reminder_scheduler import reminder_scheduler
        reminder_scheduler.start()

@app.on_event("shutdown")
def shutdown_event():
    """Stops the autonomous background reminder scheduler."""
    if os.getenv("TESTING", "false").lower() != "true":
        from .services.reminder_scheduler import reminder_scheduler
        reminder_scheduler.stop()

# CORS — configured for local development and production cloud deployment
allowed_origins_env = os.getenv("ALLOWED_ORIGINS")
allowed_origins = [o.strip() for o in allowed_origins_env.split(",")] if allowed_origins_env else ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=["*"],
)

# ── Register Routers ─────────────────────────────────────────────────
app.include_router(baby.router)
app.include_router(wiki.router)
app.include_router(care_logs.router)
app.include_router(hospitals.router)
app.include_router(agent.router)
app.include_router(telemetry.router)
app.include_router(mcp.router)
app.include_router(timeline.router)
app.include_router(obsidian.router)
app.include_router(auth.router)
app.include_router(auth.memory_router)
app.include_router(neonatal_bert.router)
app.include_router(reminders.router)


# ── Health Check ─────────────────────────────────────────────────────
@app.get("/", tags=["Health"])
@app.get("/health", tags=["Health"])
def root():
    return {
        "status": "online",
        "service": settings.app_name,
        "version": settings.app_version,
        "features": {
            "cloud_firestore": settings.use_cloud_firestore,
            "cloud_speech": settings.use_cloud_speech,
            "redis_cache": settings.use_redis_cache,
            "langgraph_agent": True,
        },
        "endpoints": [
            "/api/v1/baby/register",
            "/api/v1/baby/{baby_id}/profile",
            "/api/v1/baby/{baby_id}/corrected-age",
            "/api/v1/baby/{baby_id}/feeding-targets",
            "/api/v1/baby/{baby_id}/feeds",
            "/api/v1/baby/{baby_id}/diapers",
            "/api/v1/baby/{baby_id}/summary/48h",
            "/api/v1/baby/{baby_id}/wiki/{section}",
            "/api/v1/hospitals/search",
            "/api/v1/agent/text-query",
            "/api/v1/agent/voice-query",
            "/docs",
        ],
    }
