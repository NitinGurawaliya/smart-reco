from __future__ import annotations

from typing import Literal

from langgraph.graph import END, StateGraph
from sqlalchemy.orm import Session

from app.agent.nodes import AgentState, make_nodes
from app.config import settings


def _route_after_grade(state: AgentState) -> Literal["generate_recommendation", "refine"]:
    if state.get("grade_pass"):
        return "generate_recommendation"
    if int(state.get("retry_count") or 0) >= settings.AGENT_MAX_RETRIES:
        return "generate_recommendation"
    return "refine"


def build_agent_graph(db: Session):
    nodes = make_nodes(db)
    graph = StateGraph(AgentState)

    graph.add_node("summarize_activity", nodes["summarize_activity"])
    graph.add_node("retrieve", nodes["retrieve"])
    graph.add_node("grade_retrieval", nodes["grade_retrieval"])
    graph.add_node("refine", nodes["refine"])
    graph.add_node("generate_recommendation", nodes["generate_recommendation"])
    graph.add_node("store", nodes["store"])

    graph.set_entry_point("summarize_activity")
    graph.add_edge("summarize_activity", "retrieve")
    graph.add_edge("retrieve", "grade_retrieval")
    graph.add_conditional_edges(
        "grade_retrieval",
        _route_after_grade,
        {
            "refine": "refine",
            "generate_recommendation": "generate_recommendation",
        },
    )
    graph.add_edge("refine", "retrieve")
    graph.add_edge("generate_recommendation", "store")
    graph.add_edge("store", END)

    return graph.compile()
