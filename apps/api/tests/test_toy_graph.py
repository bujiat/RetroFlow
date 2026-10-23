from app.workflows.toy_graph import HISTORY_NOTE, run_toy, toy_graph


def test_a_new_problem_stops_after_the_first_node() -> None:
    result = run_toy("部署失败")
    assert result["recurring"] is False
    assert result["note"] == ""
    assert result["text"] == "部署失败"


def test_a_recurring_problem_reaches_the_history_node() -> None:
    again = run_toy("这个问题再次出现")
    repeat = run_toy("复发的发布问题")
    assert again["recurring"] is True
    assert again["note"] == HISTORY_NOTE
    assert repeat["recurring"] is True
    assert repeat["note"] == HISTORY_NOTE


def test_the_graph_has_two_nodes_and_no_checkpointer() -> None:
    names = set(toy_graph.get_graph().nodes)
    assert "read" in names
    assert "history" in names
    assert toy_graph.checkpointer is None
