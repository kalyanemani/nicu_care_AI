"""
Node 6: Wiki Curator Agent
Background memory updater. Extracts durable facts from the completed turn
and writes patches to the Baby Health Wiki.
"""

from typing import Dict, Any
from ..state import NICUAgentState
from ..llm_wiki_curator import LLMWikiCurator

wiki_curator = LLMWikiCurator()


def wiki_curator_node(state: NICUAgentState) -> Dict[str, Any]:
    baby_id = state["baby_id"]
    query = state["raw_query"]
    ext_knowledge = state.get("external_search_results")

    # Analyze conversation turn and patch wiki if relevant durable facts or external knowledge exist
    patch_res = wiki_curator.extract_and_patch_wiki(
        baby_id=baby_id,
        conversation_turn=query,
        external_knowledge=ext_knowledge
    )

    return {
        "wiki_updated": patch_res["success"],
        "wiki_patches": patch_res.get("patches_applied", [])
    }
