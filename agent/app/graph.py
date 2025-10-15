from __future__ import annotations

from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from .tools import acme_whoami


class GState(TypedDict, total=False):
    task: str
    profile: dict
    access_token: str


async def node_whoami(state: GState) -> dict:
    """Execute whoami tool with the access token from state."""
    access_token = state.get("access_token", "")
    profile = await acme_whoami(access_token)
    return {"profile": profile}


def build_graph():
    """Build the LangGraph agent graph."""
    g = StateGraph(GState)
    g.add_node("whoami", node_whoami)
    g.add_edge(START, "whoami")
    g.add_edge("whoami", END)
    return g.compile()
