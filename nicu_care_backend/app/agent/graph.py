"""
LangGraph Multi-Agent State Machine for NICU Post-Discharge Care.
Assembles specialized worker agents, MCP Gateway, deterministic guardrails, and verification loops.
"""

from typing import Dict, Any, Literal
from langgraph.graph import StateGraph, END

from .state import NICUAgentState
from .nodes.triage_supervisor import triage_supervisor_node
from .nodes.care_tracker import care_tracker_node
from .nodes.mcp_gateway import mcp_gateway_node
from .nodes.clinical_guide import clinical_guide_node
from .nodes.pediatric_math import pediatric_math_node
from .nodes.safety_critic import safety_critic_node
from .nodes.wiki_curator import wiki_curator_node


# ── Conditional Routing Functions ─────────────────────────────────────

def route_after_triage(state: NICUAgentState) -> Literal["safety_critic", "care_tracker", "mcp_gateway"]:
    """Routes based on Jev and Layer 1 intent classification."""
    intent = state.get("intent", "CLINICAL_QA")

    if intent in ["EMERGENCY", "OUT_OF_DOMAIN"]:
        # Immediate fast-path directly to safety critic
        return "safety_critic"
    elif intent.startswith("LOG_"):
        # Structured care logging path
        return "care_tracker"
    else:
        # All clinical, growth, timeline, hospital, or educational queries go through MCP Gateway
        return "mcp_gateway"


def route_after_critic(state: NICUAgentState) -> Literal["wiki_curator", "clinical_guide", END]:
    """Safety Critic verification and loop engineering."""
    safety_approved = state.get("safety_approved", False)
    retry_count = state.get("retry_count", 0)

    if safety_approved:
        return "wiki_curator"
    elif retry_count < 2:
        # Loop back to clinical_guide for safe self-correction rewrite
        return "clinical_guide"
    else:
        # Finalize sanitized fallback once retry threshold reached
        return END


# ── Build Graph ───────────────────────────────────────────────────────

def build_nicu_agent_graph():
    builder = StateGraph(NICUAgentState)

    # 1. Add all nodes
    builder.add_node("triage_supervisor", triage_supervisor_node)
    builder.add_node("care_tracker", care_tracker_node)
    builder.add_node("mcp_gateway", mcp_gateway_node)
    builder.add_node("pediatric_math", pediatric_math_node)
    builder.add_node("clinical_guide", clinical_guide_node)
    builder.add_node("safety_critic", safety_critic_node)
    builder.add_node("wiki_curator", wiki_curator_node)

    # 2. Set entry point
    builder.set_entry_point("triage_supervisor")

    # 3. Add conditional routing from Triage Supervisor
    builder.add_conditional_edges(
        "triage_supervisor",
        route_after_triage,
        {
            "safety_critic": "safety_critic",
            "care_tracker": "care_tracker",
            "mcp_gateway": "mcp_gateway",
        }
    )

    # 4. MCP Gateway dispatches into clinical guide
    builder.add_edge("mcp_gateway", "clinical_guide")

    # 5. Care tracker goes to safety critic
    builder.add_edge("care_tracker", "safety_critic")

    # 6. Clinical guide goes to safety critic for evaluation
    builder.add_edge("clinical_guide", "safety_critic")

    # 7. Critic verification & bounded loop control
    builder.add_conditional_edges(
        "safety_critic",
        route_after_critic,
        {
            "wiki_curator": "wiki_curator",
            "clinical_guide": "clinical_guide",
            END: END,
        }
    )

    # 8. Wiki curator completes execution
    builder.add_edge("wiki_curator", END)

    return builder.compile()


# Compiled singleton instance
nicu_agent = build_nicu_agent_graph()
app = nicu_agent
