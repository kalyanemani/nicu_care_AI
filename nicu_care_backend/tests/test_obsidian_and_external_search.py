"""
Tests for Obsidian Vault CRUD Service, External Clinical Search Fallback,
and MCP External Knowledge Ingestion Pipeline.
"""

import pytest
import shutil
from pathlib import Path
from app.config import settings
from app.services.obsidian_service import ObsidianVaultService
from app.services.external_search_service import ExternalClinicalSearchService
from app.mcp.mcp_server import mcp_server
from app.routers.agent import process_text_query, TextQueryRequest


@pytest.fixture
def temp_vault(tmp_path):
    vault_dir = tmp_path / "test_obsidian_vault"
    service = ObsidianVaultService(vault_path=vault_dir)
    yield service
    if vault_dir.exists():
        shutil.rmtree(vault_dir, ignore_errors=True)


class TestObsidianVaultCRUD:
    """Tests full CRUD lifecycle on the Obsidian Markdown vault."""

    def test_put_and_read_note(self, temp_vault):
        res = temp_vault.put_note(
            note_title="KMC_Optimal_Timing",
            content="Kangaroo mother care is best practiced between feeds for at least 60 continuous minutes.",
            folder="Clinical_Knowledge",
            tags=["#nicu", "#kmc", "#who"],
            baby_id="baby_liam_01"
        )
        assert res["success"] is True
        assert "Clinical_Knowledge/KMC_Optimal_Timing.md" in res["relative_path"]

        note = temp_vault.read_note("KMC_Optimal_Timing", folder="Clinical_Knowledge")
        assert note is not None
        assert note["frontmatter"]["title"] == "KMC_Optimal_Timing"
        assert "kmc" in note["frontmatter"]["tags"]
        assert "[[baby_liam_01]]" in note["content"]
        assert "60 continuous minutes" in note["content"]

    def test_modify_note_append(self, temp_vault):
        temp_vault.put_note(
            note_title="Feeding_Regimen",
            content="Initial target: 150 mL/kg/day.",
            folder="Baby_Profiles",
            baby_id="baby_liam_01"
        )
        mod_res = temp_vault.modify_note(
            note_title="Feeding_Regimen",
            patch_content="Fortifier increased to 24 kcal/oz by neonatologist.",
            mode="append",
            folder="Baby_Profiles"
        )
        assert mod_res["success"] is True

        updated = temp_vault.read_note("Feeding_Regimen", folder="Baby_Profiles")
        assert "Initial target: 150 mL/kg/day" in updated["content"]
        assert "Fortifier increased to 24 kcal/oz" in updated["content"]

    def test_update_note_overwrite(self, temp_vault):
        temp_vault.put_note("Growth_Summary", "Week 1: 1820g", folder="Daily_Care_Logs")
        up_res = temp_vault.update_note("Growth_Summary", "Week 3: 2400g (strong velocity)", folder="Daily_Care_Logs")
        assert up_res["success"] is True

        read = temp_vault.read_note("Growth_Summary", folder="Daily_Care_Logs")
        assert "Week 3: 2400g" in read["content"]
        assert "Week 1: 1820g" not in read["content"]

    def test_safe_delete_archive(self, temp_vault):
        temp_vault.put_note("Temporary_Note", "Draft note", folder="Clinical_Knowledge")
        del_res = temp_vault.delete_note("Temporary_Note", folder="Clinical_Knowledge", permanent=False)
        assert del_res["success"] is True
        assert del_res["permanent"] is False
        assert "Archive" in del_res["archived_to"]

        # Note should no longer be in Clinical_Knowledge
        read = temp_vault.read_note("Temporary_Note", folder="Clinical_Knowledge")
        assert read is None

    def test_list_notes_with_filter(self, temp_vault):
        temp_vault.put_note("Guideline_1", "Text 1", folder="Clinical_Knowledge", tags=["#guideline", "#preterm"])
        temp_vault.put_note("Guideline_2", "Text 2", folder="Clinical_Knowledge", tags=["#guideline", "#formula"])
        temp_vault.put_note("Profile_1", "Profile Text", folder="Baby_Profiles", tags=["#profile"])

        all_notes = temp_vault.list_notes()
        assert len(all_notes) >= 3

        preterm_notes = temp_vault.list_notes(tag_filter="preterm")
        assert len(preterm_notes) == 1
        assert preterm_notes[0]["title"] == "Guideline_1"


class TestExternalClinicalSearch:
    """Tests external clinical literature search and evidence synthesis."""

    def test_search_clinical_knowledge(self):
        svc = ExternalClinicalSearchService()
        res = svc.search_clinical_knowledge("bronchopulmonary dysplasia preterm post discharge", top_k=2)
        assert res["has_external_knowledge"] is True
        assert len(res["sources"]) > 0
        assert len(res["synthesized_guidance"]) > 30
        assert len(res["citations"]) > 0


class TestMCPToolsIntegration:
    """Tests MCP tool schemas and execution for external search and Obsidian."""

    def test_mcp_tools_registered(self):
        tools = mcp_server.list_tools()
        names = [t["name"] for t in tools]
        assert "mcp_external_clinical_search" in names
        assert "mcp_obsidian_manager" in names

    def test_mcp_obsidian_manager_put_and_read(self):
        put_res = mcp_server.call_tool("mcp_obsidian_manager", {
            "action": "put",
            "note_title": "MCP_Test_Guideline",
            "content": "Supervised tummy time for 3-5 minutes 2-3 times daily.",
            "folder": "Clinical_Knowledge",
            "tags": ["#tummy_time", "#motor_development"],
            "baby_id": "baby_liam_01"
        })
        import json
        put_data = json.loads(put_res["content"][0]["text"])
        assert put_data["success"] is True

        read_res = mcp_server.call_tool("mcp_obsidian_manager", {
            "action": "read",
            "note_title": "MCP_Test_Guideline",
            "folder": "Clinical_Knowledge"
        })
        read_data = json.loads(read_res["content"][0]["text"])
        assert "tummy time" in read_data["content"]
        assert "[[baby_liam_01]]" in read_data["content"]

    def test_mcp_external_clinical_search(self):
        import json
        res = mcp_server.call_tool("mcp_external_clinical_search", {
            "query": "safe sleep preterm infant SIDS",
            "top_k": 2
        })
        data = json.loads(res["content"][0]["text"])
        assert data["has_external_knowledge"] is True
        assert len(data["citations"]) > 0


class TestKBMissEndToEndFlow:
    """Tests that a KB miss query invokes external search and curates into Obsidian."""

    def test_kb_miss_triggers_external_search_and_obsidian_sync(self):
        # Query on a specialized clinical topic not in local guidelines
        query = "What are the latest clinical recommendations for bronchopulmonary dysplasia chronic lung disease in preterm infants?"
        req = TextQueryRequest(baby_id="baby_liam_01", text=query)
        resp = process_text_query(req)

        assert resp is not None
        assert len(resp.text_card) > 50
        # Check that external research or guidelines were referenced
        assert any(term in resp.text_card.lower() for term in ["clinical", "guideline", "evidence", "preterm", "recommendations"])

        # Verify that an Obsidian note was curated into the vault
        from app.services.obsidian_service import obsidian_service
        notes = obsidian_service.list_notes(folder="Clinical_Knowledge")
        assert len(notes) > 0
