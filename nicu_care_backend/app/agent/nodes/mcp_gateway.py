"""
Node: MCP Gateway Agent
Centralized gateway for tool selection, parameter validation, and execution.
Acts as the bridge between LangGraph multi-agent orchestration and the Model Context Protocol (MCP) server.
"""

from typing import Dict, Any, List
import json
import logging
from ..state import NICUAgentState
from ...mcp.mcp_server import mcp_server
from ..guardrails.tool_guardrails import ToolGuardrails

logger = logging.getLogger("mcp_gateway")


def mcp_gateway_node(state: NICUAgentState) -> Dict[str, Any]:
    """
    Selects, validates, and executes the appropriate MCP tools based on user intent and entities.
    Stores structured outputs in state["tool_outputs"] and execution logs in state["mcp_execution_log"].
    """
    trace_id = state.get("trace_id")
    parent_span_id = state.get("parent_span_id")
    gw_span = None
    if trace_id and parent_span_id:
        from ...telemetry.tracer import tracer
        gw_span = tracer.start_span("agent.langgraph.mcp_gateway", trace_id=trace_id, parent_span_id=parent_span_id)
    intent = state.get("intent", "CLINICAL_QA")
    baby_id = state.get("baby_id", "baby_liam_01")
    raw_query = state.get("raw_query", "")

    selected_tools: List[str] = []
    tool_outputs: Dict[str, Any] = {}
    mcp_log: List[Dict[str, Any]] = []

    # ── 1. Tool Selection based on Intent and Context ─────────────────────
    if intent == "GROWTH_ANALYSIS":
        selected_tools.append("mcp_growth_intelligence")

    elif intent in ["FEEDING_INTELLIGENCE", "PEDIATRIC_MATH"]:
        selected_tools.append("mcp_pediatric_calculator")

    elif intent in ["TIMELINE_INSPECT", "KMC_SESSION", "HYGIENE_STERILIZATION", "MATERNAL_WELLBEING"]:
        selected_tools.append("mcp_care_timeline_inspector")

    elif intent == "HOSPITAL_LOOKUP":
        selected_tools.append("mcp_hospital_emergency_locator")

    elif intent == "WIKI_LOOKUP":
        selected_tools.append("mcp_wiki_memory_manager")

    elif intent == "CLINICAL_QA":
        # Always run guideline retrieval and safety graph traversal
        selected_tools.extend(["mcp_guideline_retriever", "mcp_graph_rag_traversal"])

    # Fallback / Multi-tool expansion if query specifically mentions weight or timeline
    q_lower = raw_query.lower()
    if "weight" in q_lower and "mcp_growth_intelligence" not in selected_tools:
        selected_tools.append("mcp_growth_intelligence")
    if ("next" in q_lower or "schedule" in q_lower) and "mcp_care_timeline_inspector" not in selected_tools:
        selected_tools.append("mcp_care_timeline_inspector")

    # ── 2. Tool Execution & Output Aggregation ────────────────────────────
    for tool_name in selected_tools:
        args: Dict[str, Any] = {}

        try:
            if tool_name == "mcp_growth_intelligence":
                args = {"baby_id": baby_id}

            elif tool_name == "mcp_pediatric_calculator":
                # Determine weight from state or query
                weight = 2400 if baby_id == "baby_liam_01" else 1800
                args = {"current_weight_grams": weight, "kcal_per_oz": 24}

            elif tool_name == "mcp_care_timeline_inspector":
                if any(w in q_lower for w in ["feed", "milk", "bottle"]) and any(w in q_lower for w in ["when", "next", "time", "due", "schedule"]):
                    qtype = "next_feed"
                elif any(w in q_lower for w in ["kmc", "kangaroo", "skin to skin", "skin-to-skin"]) and any(w in q_lower for w in ["when", "next", "time", "due", "schedule"]):
                    qtype = "next_kmc"
                elif intent == "KMC_SESSION":
                    qtype = "kmc_summary"
                elif "next" in q_lower or "do next" in q_lower:
                    qtype = "next_action"
                else:
                    qtype = "full_timeline"
                args = {"baby_id": baby_id, "query_type": qtype}

            elif tool_name == "mcp_hospital_emergency_locator":
                args = {"hospital_name": "Rainbow Hospital Vijayawada"}

            elif tool_name == "mcp_wiki_memory_manager":
                args = {"baby_id": baby_id, "action": "read", "section": "profile"}

            elif tool_name == "mcp_guideline_retriever":
                args = {"query": raw_query, "baby_corrected_weeks": 2, "top_k": 3}

            elif tool_name == "mcp_graph_rag_traversal":
                args = {"clinical_query": raw_query}

            # Call MCP Server tool
            res = mcp_server.call_tool(tool_name, args)
            raw_content = res.get("content", [{}])[0].get("text", "{}")
            
            try:
                parsed_content = json.loads(raw_content)
            except Exception:
                parsed_content = raw_content

            tool_outputs[tool_name] = parsed_content
            mcp_log.append({
                "tool": tool_name,
                "status": "SUCCESS",
                "arguments": args,
                "result_preview": str(parsed_content)[:120] + "..." if len(str(parsed_content)) > 120 else str(parsed_content)
            })

        except Exception as e:
            logger.error(f"Error executing MCP tool {tool_name}: {e}")
            mcp_log.append({
                "tool": tool_name,
                "status": "ERROR",
                "arguments": args,
                "error": str(e)
            })

    # ── 3. KB Miss / Low-Confidence External Search Fallback ─────────────
    if intent == "CLINICAL_QA":
        chunks = tool_outputs.get("mcp_guideline_retriever") or []
        has_adequate_kb = False
        if isinstance(chunks, list) and len(chunks) > 0:
            top_score = chunks[0].get("score", 0.0)
            if top_score >= 0.45:
                has_adequate_kb = True

        if not has_adequate_kb or any(w in raw_query.lower() for w in ["search online", "external", "pubmed", "latest study", "research"]):
            try:
                ext_res = mcp_server.call_tool("mcp_external_clinical_search", {"query": raw_query, "top_k": 3})
                ext_content = json.loads(ext_res.get("content", [{}])[0].get("text", "{}"))
                tool_outputs["mcp_external_clinical_search"] = ext_content
                mcp_log.append({
                    "tool": "mcp_external_clinical_search",
                    "status": "SUCCESS",
                    "trigger": "KB_MISS_FALLBACK",
                    "result_preview": str(ext_content.get("synthesized_guidance", ""))[:120] + "..."
                })
            except Exception as ext_err:
                logger.error(f"External search fallback error: {ext_err}")

    if gw_span:
        from ...telemetry.tracer import tracer
        tracer.end_span(gw_span, status="OK")

    return {
        "selected_tools": selected_tools,
        "tool_outputs": tool_outputs,
        "mcp_execution_log": mcp_log
    }
