"""
LangGraph State Schema for the NICU Care Agent Team.
Includes typed containers for MCP Gateway tools, Model Routing, and Loop Engineering.
"""

from typing import TypedDict, Optional, List, Dict, Any


class NICUAgentState(TypedDict):
    # ── User Input & Context ──────────────────────────────────────────
    baby_id: str
    raw_query: str
    detected_language: str
    baby_wiki_context: str
    trace_id: Optional[str]
    parent_span_id: Optional[str]

    # ── Input Guardrails & Security ───────────────────────────────────
    input_guardrail_passed: bool
    input_guardrail_notes: Optional[str]

    # ── Jev & Model Routing & Intent Classification ───────────────────
    intent: str                          # "EMERGENCY", "GROWTH_ANALYSIS", "TIMELINE_INSPECT", "LOG_FEED", "LOG_DIAPER", "HOSPITAL_LOOKUP", "CLINICAL_QA"
    urgency: str                         # "EMERGENCY", "ROUTINE", "INFORMATIONAL"
    emergency_probability: float
    is_emergency: bool
    selected_model: Optional[str]
    requested_model: Optional[str]

    # ── MCP Gateway & Tool Execution Results ──────────────────────────
    selected_tools: List[str]
    tool_outputs: Dict[str, Any]
    mcp_execution_log: List[Dict[str, Any]]
    retrieved_chunks: List[Dict[str, Any]]
    math_results: Optional[Dict[str, Any]]
    hospital_contact: Optional[Dict[str, Any]]
    logged_entry_summary: Optional[str]

    # ── Candidate Draft & Validation Loop ─────────────────────────────
    draft_response: str
    voice_summary: str
    safety_approved: bool
    safety_violations: List[str]
    critique_notes: Optional[str]
    retry_count: int
    loop_iteration: int

    # ── Output Guardrails & Final Delivery ────────────────────────────
    output_guardrail_passed: bool
    final_text_card: str
    final_voice_summary: str
    wiki_updated: bool
    next_reminder_minutes: Optional[int]
