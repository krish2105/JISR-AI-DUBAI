"""
graph.py — Wire the agents into a LangGraph state machine.

    START -> ingest -> guard -> supervisor --(normal)--> quote -> duty -> docs -> trust -> outreach -> governance -> END
                                         \\--(bank-change attack)---------------------------------------> governance

Why this file exists:
    The order of agents and the branching rule live in one readable place. Phase 9 replaces
    the fixed chain with a supervisor that plans dynamically and re-plans on tool failures.
"""

from functools import lru_cache

from langgraph.graph import END, START, StateGraph

from app.agents import nodes
from app.agents.state import RunState


def route_after_supervisor(state: RunState) -> str:
    """Follow the supervisor's plan: go to its first step (governance for attacks)."""
    return state.plan[0] if state.plan else "governance"


def route_after_quote(state: RunState) -> str:
    """Explainable re-plan after pricing (see nodes.route_after_pricing)."""
    return nodes.route_after_pricing(state.quote or {})[0]


@lru_cache
def build_graph():
    """Build and compile the Phase 1 graph once (compiled graphs are reusable)."""
    graph = StateGraph(RunState)
    for name in ("ingest", "guard", "supervisor", "quote", "duty", "docs", "trust", "outreach", "governance"):
        graph.add_node(name, getattr(nodes, name))

    graph.add_edge(START, "ingest")
    graph.add_edge("ingest", "guard")
    graph.add_edge("guard", "supervisor")
    graph.add_conditional_edges("supervisor", route_after_supervisor, ["quote", "governance"])
    graph.add_conditional_edges("quote", route_after_quote, ["duty", "docs", "trust"])
    graph.add_edge("duty", "docs")
    graph.add_edge("docs", "trust")
    graph.add_edge("trust", "outreach")
    graph.add_edge("outreach", "governance")
    graph.add_edge("governance", END)
    return graph.compile()
