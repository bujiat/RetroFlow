from typing import TypedDict

from langgraph.graph import END, START, StateGraph

HISTORY_NOTE = "这是复发问题，需要查看上次行动。"


class ToyState(TypedDict):
    """Data that moves from one node to the next. A node returns only the fields it changes."""

    text: str
    recurring: bool
    note: str


def read_text(state: ToyState) -> dict[str, bool]:
    text = state["text"]
    return {"recurring": "再次" in text or "复发" in text}


def route_after_read(state: ToyState) -> str:
    if state["recurring"]:
        return "history"
    return END


def add_history_note(state: ToyState) -> dict[str, str]:
    return {"note": HISTORY_NOTE}


def compile_toy_graph():
    """Two nodes and one conditional edge. No checkpointer and no model call."""
    graph = StateGraph(ToyState)
    graph.add_node("read", read_text)
    graph.add_node("history", add_history_note)
    graph.add_edge(START, "read")
    graph.add_conditional_edges("read", route_after_read)
    graph.add_edge("history", END)
    return graph.compile()


toy_graph = compile_toy_graph()


def run_toy(text: str) -> ToyState:
    result = toy_graph.invoke({"text": text, "recurring": False, "note": ""})
    return {
        "text": result["text"],
        "recurring": bool(result["recurring"]),
        "note": str(result["note"]),
    }
