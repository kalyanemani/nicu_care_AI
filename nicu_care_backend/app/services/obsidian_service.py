"""
Obsidian Vault Integration Service:
Full CRUD lifecycle (PUT, MODIFY, UPDATE, DELETE, READ, LIST) for Obsidian Markdown vaults.
Features:
- Dual-mode: Local file-based vault management + Obsidian Local REST API client
- Standard Obsidian YAML frontmatter (aliases, tags, date, baby_id, author)
- Automatic Wikilinks generation ([[baby_liam_01]], [[active_regimen]], [[clinical_guideline]])
- Safe deletion with .trash / Archive folder retention
- Section-level patching and modification
"""

import os
import re
import json
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List, Any
import requests

from ..config import settings


class ObsidianVaultService:
    """
    Manages clinical knowledge, baby care notes, and external guideline records
    within an Obsidian vault.
    """

    def __init__(self, vault_path: Optional[Path] = None):
        self.vault_path = vault_path or settings.obsidian_vault_dir or (settings.data_dir / "obsidian_vault")
        self.api_url = getattr(settings, "obsidian_api_url", "http://127.0.0.1:27124")
        self.api_key = getattr(settings, "obsidian_api_key", None)
        self._ensure_vault_initialized()

    def _ensure_vault_initialized(self):
        """Creates vault directories, .obsidian folder, and an index README note."""
        self.vault_path.mkdir(parents=True, exist_ok=True)
        (self.vault_path / ".obsidian").mkdir(exist_ok=True)
        (self.vault_path / "Clinical_Knowledge").mkdir(exist_ok=True)
        (self.vault_path / "Baby_Profiles").mkdir(exist_ok=True)
        (self.vault_path / "Daily_Care_Logs").mkdir(exist_ok=True)
        (self.vault_path / "Archive").mkdir(exist_ok=True)

        readme_file = self.vault_path / "README.md"
        if not readme_file.exists():
            readme_content = (
                "---\n"
                "title: NICU HomeCare AI Obsidian Vault\n"
                "created: " + datetime.now().strftime("%Y-%m-%d") + "\n"
                "tags: [nicu, homecare, obsidian, clinical_wiki]\n"
                "---\n\n"
                "# 👶 NICU HomeCare AI — Living Clinical & Patient Vault\n\n"
                "Welcome to the **NICU HomeCare AI** Obsidian vault.\n\n"
                "### Vault Structure\n"
                "- **`Clinical_Knowledge/`**: Authoritative WHO, AAP, and externally searched clinical guidelines.\n"
                "- **`Baby_Profiles/`**: Living medical memory and profiles for enrolled preterm infants (e.g., [[baby_liam_01]]).\n"
                "- **`Daily_Care_Logs/`**: Feeding schedules, KMC milestones, and growth tracking.\n"
                "- **`Archive/`**: Safely deleted/archived clinical notes.\n\n"
                "Connected to NICU Multi-Agent MCP Gateway.\n"
            )
            readme_file.write_text(readme_content, encoding="utf-8")

    def _format_frontmatter(self, meta: Dict[str, Any]) -> str:
        """Formats dictionary metadata into YAML frontmatter string."""
        lines = ["---"]
        for k, v in meta.items():
            if isinstance(v, list):
                val_str = "[" + ", ".join(f'"{item}"' if " " in str(item) else str(item) for item in v) + "]"
                lines.append(f"{k}: {val_str}")
            elif isinstance(v, (int, float, bool)):
                lines.append(f"{k}: {v}")
            else:
                lines.append(f'{k}: "{v}"')
        lines.append("---\n")
        return "\n".join(lines)

    def _parse_frontmatter(self, text: str) -> tuple[Dict[str, Any], str]:
        """Parses YAML frontmatter and returns (metadata_dict, body_text)."""
        if text.startswith("---"):
            parts = text.split("---", 2)
            if len(parts) >= 3:
                frontmatter_raw = parts[1]
                body = parts[2].lstrip("\n")
                meta: Dict[str, Any] = {}
                for line in frontmatter_raw.splitlines():
                    if ":" in line:
                        k, v = line.split(":", 1)
                        k, v = k.strip(), v.strip().strip('"\'')
                        if v.startswith("[") and v.endswith("]"):
                            # Simple list parsing
                            items = [i.strip(" '\"") for i in v[1:-1].split(",") if i.strip()]
                            meta[k] = items
                        else:
                            meta[k] = v
                return meta, body
        return {}, text

    def _resolve_note_path(self, note_title: str, folder: Optional[str] = None) -> Path:
        """Resolves target .md file path in the vault."""
        clean_name = re.sub(r'[\\/*?:"<>|]', "", note_title).strip()
        if not clean_name.endswith(".md"):
            clean_name += ".md"

        if folder:
            target_dir = self.vault_path / folder
            target_dir.mkdir(parents=True, exist_ok=True)
            return target_dir / clean_name

        # Search existing note across all folders
        for match in self.vault_path.rglob(clean_name):
            if match.is_file():
                return match

        # Default folder
        return self.vault_path / "Clinical_Knowledge" / clean_name

    # ── 1. PUT: Create or Completely Overwrite a Note ─────────────────────────
    def put_note(
        self,
        note_title: str,
        content: str,
        folder: str = "Clinical_Knowledge",
        tags: Optional[List[str]] = None,
        frontmatter: Optional[Dict[str, Any]] = None,
        baby_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        PUT operation: Creates or replaces an Obsidian note with standardized
        YAML frontmatter, wikilinks, and tags.
        """
        tags = tags or ["#nicu", "#clinical_guideline"]
        # Normalize tags (strip leading # for YAML array)
        clean_tags = [t.lstrip("#") for t in tags]

        now_str = datetime.now().isoformat()
        date_str = datetime.now().strftime("%Y-%m-%d")

        meta: Dict[str, Any] = {
            "title": note_title,
            "created": date_str,
            "last_modified": now_str,
            "tags": clean_tags,
            "source": "NICU HomeCare AI / MCP External Search",
        }
        if baby_id:
            meta["baby_id"] = baby_id
        if frontmatter:
            meta.update(frontmatter)

        # Inject wikilinks if baby_id present
        body_content = content
        if baby_id and f"[[{baby_id}]]" not in body_content:
            body_content += f"\n\n---\n**Related Notes:** [[{baby_id}]], [[Clinical_Guidelines]], [[active_regimen]]"

        full_note_text = self._format_frontmatter(meta) + "\n" + body_content.strip() + "\n"

        target_path = self._resolve_note_path(note_title, folder=folder)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text(full_note_text, encoding="utf-8")

        # Try sync to Obsidian REST API if configured
        self._sync_rest_api("PUT", target_path.relative_to(self.vault_path).as_posix(), full_note_text)

        return {
            "action": "put",
            "success": True,
            "note_title": note_title,
            "relative_path": target_path.relative_to(self.vault_path).as_posix(),
            "absolute_path": str(target_path),
            "size_bytes": len(full_note_text),
            "timestamp": now_str,
        }

    # ── 2. MODIFY / PATCH: Append or Edit Note Sections ───────────────────────
    def modify_note(
        self,
        note_title: str,
        patch_content: str,
        mode: str = "append",
        folder: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        MODIFY operation: Appends or prepends content to an existing note,
        or creates it if missing, updating 'last_modified' in frontmatter.
        """
        target_path = self._resolve_note_path(note_title, folder=folder)

        if not target_path.exists():
            return self.put_note(note_title, patch_content, folder=folder or "Clinical_Knowledge")

        existing_text = target_path.read_text(encoding="utf-8")
        meta, body = self._parse_frontmatter(existing_text)

        meta["last_modified"] = datetime.now().isoformat()
        timestamp_header = f"\n\n### Update ({datetime.now().strftime('%Y-%m-%d %H:%M')})\n"

        if mode == "append":
            new_body = body.rstrip() + timestamp_header + patch_content.strip() + "\n"
        elif mode == "prepend":
            new_body = timestamp_header + patch_content.strip() + "\n\n" + body.lstrip()
        elif mode == "replace_section":
            # If patch has a section header, replace that header block
            header_match = re.search(r'^(#{1,3}\s+.+)$', patch_content, flags=re.MULTILINE)
            if header_match:
                header = header_match.group(1).strip()
                escaped_header = re.escape(header)
                new_body = re.sub(
                    rf"{escaped_header}.*?(?=\n#{1,3}\s+|\Z)",
                    patch_content.strip(),
                    body,
                    flags=re.DOTALL
                )
            else:
                new_body = body.rstrip() + timestamp_header + patch_content.strip() + "\n"
        else:
            new_body = body.rstrip() + timestamp_header + patch_content.strip() + "\n"

        full_text = self._format_frontmatter(meta) + "\n" + new_body
        target_path.write_text(full_text, encoding="utf-8")

        self._sync_rest_api("PATCH", target_path.relative_to(self.vault_path).as_posix(), patch_content)

        return {
            "action": "modify",
            "success": True,
            "mode": mode,
            "note_title": note_title,
            "relative_path": target_path.relative_to(self.vault_path).as_posix(),
            "timestamp": meta["last_modified"],
        }

    # ── 3. UPDATE: Overwrite Existing Note Content ───────────────────────────
    def update_note(
        self,
        note_title: str,
        content: str,
        folder: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        UPDATE operation: Replaces body content of existing note,
        preserving and refreshing metadata frontmatter.
        """
        target_path = self._resolve_note_path(note_title, folder=folder)
        if not target_path.exists():
            return self.put_note(note_title, content, folder=folder or "Clinical_Knowledge")

        existing_text = target_path.read_text(encoding="utf-8")
        meta, _ = self._parse_frontmatter(existing_text)
        meta["last_modified"] = datetime.now().isoformat()

        full_text = self._format_frontmatter(meta) + "\n" + content.strip() + "\n"
        target_path.write_text(full_text, encoding="utf-8")

        self._sync_rest_api("PUT", target_path.relative_to(self.vault_path).as_posix(), full_text)

        return {
            "action": "update",
            "success": True,
            "note_title": note_title,
            "relative_path": target_path.relative_to(self.vault_path).as_posix(),
            "timestamp": meta["last_modified"],
        }

    # ── 4. DELETE: Safe Archive or Removal of Note ───────────────────────────
    def delete_note(
        self,
        note_title: str,
        folder: Optional[str] = None,
        permanent: bool = False,
    ) -> Dict[str, Any]:
        """
        DELETE operation: Safely moves note to 'Archive/' (or permanently deletes
        if permanent=True), in accordance with Obsidian best practices.
        """
        target_path = self._resolve_note_path(note_title, folder=folder)
        if not target_path.exists():
            return {
                "action": "delete",
                "success": False,
                "error": f"Note '{note_title}' not found in vault.",
            }

        if permanent:
            target_path.unlink()
            self._sync_rest_api("DELETE", target_path.relative_to(self.vault_path).as_posix())
            return {
                "action": "delete",
                "success": True,
                "permanent": True,
                "note_title": note_title,
            }
        else:
            # Safe Archive move
            archive_dir = self.vault_path / "Archive"
            archive_dir.mkdir(parents=True, exist_ok=True)
            archive_path = archive_dir / f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{target_path.name}"
            target_path.rename(archive_path)
            return {
                "action": "delete",
                "success": True,
                "permanent": False,
                "archived_to": archive_path.relative_to(self.vault_path).as_posix(),
                "note_title": note_title,
            }

    # ── 5. READ: Retrieve Note Content & Metadata ────────────────────────────
    def read_note(self, note_title: str, folder: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        READ operation: Returns note content, frontmatter, and file stats.
        """
        target_path = self._resolve_note_path(note_title, folder=folder)
        if not target_path.exists():
            return None

        text = target_path.read_text(encoding="utf-8")
        meta, body = self._parse_frontmatter(text)

        stat = target_path.stat()
        return {
            "note_title": target_path.stem,
            "relative_path": target_path.relative_to(self.vault_path).as_posix(),
            "frontmatter": meta,
            "content": body,
            "full_text": text,
            "modified_time": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            "size_bytes": stat.st_size,
        }

    # ── 6. LIST: Query and Filter Notes in Vault ─────────────────────────────
    def list_notes(self, folder: Optional[str] = None, tag_filter: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        LIST operation: Enumerates notes in the vault, optionally filtered by folder or tag.
        """
        base_dir = (self.vault_path / folder) if folder else self.vault_path
        if not base_dir.exists():
            return []

        results = []
        for file in base_dir.rglob("*.md"):
            if ".obsidian" in file.parts or "Archive" in file.parts:
                continue

            try:
                text = file.read_text(encoding="utf-8")
                meta, _ = self._parse_frontmatter(text)
                tags = meta.get("tags", [])
                if isinstance(tags, str):
                    tags = [tags]

                if tag_filter:
                    clean_tag = tag_filter.lstrip("#")
                    if clean_tag not in tags:
                        continue

                results.append({
                    "title": file.stem,
                    "relative_path": file.relative_to(self.vault_path).as_posix(),
                    "folder": file.parent.relative_to(self.vault_path).as_posix(),
                    "tags": tags,
                    "last_modified": meta.get("last_modified", ""),
                    "size_bytes": file.stat().st_size,
                })
            except Exception:
                pass

        return results

    # ── 7. Obsidian Local REST API Sync ──────────────────────────────────────
    def _sync_rest_api(self, method: str, rel_path: str, data: Optional[str] = None):
        """Optionally syncs changes to Obsidian Local REST API plugin if active."""
        if not self.api_key:
            return
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "text/markdown",
        }
        url = f"{self.api_url.rstrip('/')}/vault/{rel_path}"
        try:
            if method == "PUT":
                requests.put(url, data=data.encode("utf-8"), headers=headers, timeout=2)
            elif method == "PATCH":
                requests.patch(url, data=data.encode("utf-8"), headers=headers, timeout=2)
            elif method == "DELETE":
                requests.delete(url, headers=headers, timeout=2)
        except Exception:
            # Silently fallback to local filesystem mode
            pass


# Singleton instance
obsidian_service = ObsidianVaultService()
