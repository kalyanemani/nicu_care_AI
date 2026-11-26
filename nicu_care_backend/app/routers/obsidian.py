"""
FastAPI Router for Obsidian Vault CRUD & Knowledge Integration:
Endpoints:
  - GET    /api/v1/obsidian/notes           -> List notes in vault with filters
  - GET    /api/v1/obsidian/notes/{title}   -> Read note content and frontmatter
  - POST   /api/v1/obsidian/notes           -> PUT / Create new note in vault
  - PUT    /api/v1/obsidian/notes/{title}   -> Overwrite / Update existing note
  - PATCH  /api/v1/obsidian/notes/{title}   -> Modify / Append section to note
  - DELETE /api/v1/obsidian/notes/{title}   -> Safe Archive / Delete note
"""

from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from ..services.obsidian_service import obsidian_service

router = APIRouter(prefix="/api/v1/obsidian", tags=["Obsidian Vault & Knowledge Management"])


class PutNoteRequest(BaseModel):
    note_title: str = Field(..., description="Title of the note (filename)")
    content: str = Field(..., description="Markdown body content")
    folder: str = Field(default="Clinical_Knowledge", description="Vault folder")
    tags: Optional[List[str]] = Field(default_factory=lambda: ["#nicu", "#clinical_guideline"])
    frontmatter: Optional[Dict[str, Any]] = None
    baby_id: Optional[str] = Field(default="baby_liam_01", description="Associated baby ID for wikilinks")


class ModifyNoteRequest(BaseModel):
    patch_content: str = Field(..., description="Text to append or patch")
    mode: str = Field(default="append", description="append, prepend, or replace_section")
    folder: Optional[str] = None


class UpdateNoteRequest(BaseModel):
    content: str = Field(..., description="Full updated content")
    folder: Optional[str] = None


@router.get("/notes", response_model=List[Dict[str, Any]])
def list_notes(
    folder: Optional[str] = Query(None, description="Subfolder filter"),
    tag: Optional[str] = Query(None, description="Tag filter, e.g. 'nicu' or '#clinical_guideline'")
):
    """Lists all markdown notes in the Obsidian vault."""
    return obsidian_service.list_notes(folder=folder, tag_filter=tag)


@router.get("/notes/{note_title}", response_model=Dict[str, Any])
def read_note(
    note_title: str,
    folder: Optional[str] = Query(None, description="Subfolder in vault")
):
    """Reads a note's content and YAML frontmatter from the Obsidian vault."""
    note = obsidian_service.read_note(note_title, folder=folder)
    if not note:
        raise HTTPException(status_code=404, detail=f"Note '{note_title}' not found in Obsidian vault.")
    return note


@router.post("/notes", response_model=Dict[str, Any])
def create_or_put_note(req: PutNoteRequest):
    """Creates (PUT) a new note in the Obsidian vault with frontmatter and wikilinks."""
    return obsidian_service.put_note(
        note_title=req.note_title,
        content=req.content,
        folder=req.folder,
        tags=req.tags,
        frontmatter=req.frontmatter,
        baby_id=req.baby_id
    )


@router.put("/notes/{note_title}", response_model=Dict[str, Any])
def update_note(note_title: str, req: UpdateNoteRequest):
    """Updates whole content of an existing note while updating last_modified timestamp."""
    return obsidian_service.update_note(
        note_title=note_title,
        content=req.content,
        folder=req.folder
    )


@router.patch("/notes/{note_title}", response_model=Dict[str, Any])
def modify_note(note_title: str, req: ModifyNoteRequest):
    """Modifies/patches an existing note (appends, prepends, or updates section)."""
    return obsidian_service.modify_note(
        note_title=note_title,
        patch_content=req.patch_content,
        mode=req.mode,
        folder=req.folder
    )


@router.delete("/notes/{note_title}", response_model=Dict[str, Any])
def delete_note(
    note_title: str,
    folder: Optional[str] = Query(None, description="Subfolder in vault"),
    permanent: bool = Query(False, description="True for permanent unlink, False for safe Archive move")
):
    """Deletes or safely archives a note in the Obsidian vault."""
    res = obsidian_service.delete_note(note_title, folder=folder, permanent=permanent)
    if not res.get("success"):
        raise HTTPException(status_code=404, detail=res.get("error", "Note not found"))
    return res
