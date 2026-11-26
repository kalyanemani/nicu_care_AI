"""
Wiki (Baby Health Living Memory) API endpoints.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional

from ..services.wiki_service import WikiService, VALID_SECTIONS

router = APIRouter(prefix="/api/v1/baby", tags=["Baby Health Wiki"])

wiki_service = WikiService()


class WikiPatchRequest(BaseModel):
    """Request body for patching a wiki section."""
    content: str = Field(..., description="New content or patch text to append")
    mode: str = Field(
        default="overwrite",
        description="'overwrite' replaces the section; 'append' adds a timestamped entry"
    )


class WikiSectionResponse(BaseModel):
    """Response containing a wiki section."""
    baby_id: str
    section: str
    content: Optional[str]
    available_sections: list = VALID_SECTIONS


@router.get("/{baby_id}/wiki/{section}", response_model=WikiSectionResponse)
def read_wiki_section(baby_id: str, section: str):
    """
    Reads a Baby Health Wiki section.

    Valid sections: profile, active_regimen, clinical_alerts, rolling_log_summary
    """
    if section not in VALID_SECTIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid section '{section}'. Must be one of {VALID_SECTIONS}"
        )

    content = wiki_service.read_section(baby_id, section)
    return WikiSectionResponse(
        baby_id=baby_id,
        section=section,
        content=content,
    )


@router.patch("/{baby_id}/wiki/{section}", response_model=WikiSectionResponse)
def update_wiki_section(baby_id: str, section: str, body: WikiPatchRequest):
    """
    Updates a Baby Health Wiki section.

    - mode='overwrite': Replaces the entire section content.
    - mode='append': Appends a timestamped entry to the existing content.
    """
    if section not in VALID_SECTIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid section '{section}'. Must be one of {VALID_SECTIONS}"
        )

    if body.mode == "append":
        content = wiki_service.patch_section(baby_id, section, body.content)
    else:
        content = wiki_service.write_section(baby_id, section, body.content)

    return WikiSectionResponse(
        baby_id=baby_id,
        section=section,
        content=content,
    )


@router.get("/{baby_id}/wiki")
def read_all_wiki_sections(baby_id: str):
    """Reads all wiki sections for a baby."""
    sections = wiki_service.read_all_sections(baby_id)
    return {
        "baby_id": baby_id,
        "sections": sections,
    }
