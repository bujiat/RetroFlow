import re
from uuid import UUID

from app.agent.loop import AgentStep
from app.schemas.assistant import AssistantCitation


def catalog_from_steps(steps: list[AgentStep]) -> dict[str, AssistantCitation]:
    """Citations the model is allowed to use: ids that appeared in this run's tool results."""
    catalog: dict[str, AssistantCitation] = {}
    for step in steps:
        data = _data(step.result)
        if data is None:
            continue
        if step.name == "search_retro_content":
            for hit in _dicts(data.get("hits")):
                _add(catalog, _chunk_citation(hit))
        elif step.name == "find_similar_problems":
            match = data.get("match")
            if isinstance(match, dict):
                _add(catalog, _cluster_citation(match))
        elif step.name == "list_actions":
            for item in _dicts(data.get("items")):
                _add(catalog, _action_citation(item))
        elif step.name == "get_action_history":
            _add(catalog, _history_citation(data))
        elif step.name == "get_trends":
            for cluster in _dicts(data.get("top_clusters")):
                _add(catalog, _cluster_citation(cluster))
            for item in _dicts(data.get("overdue_items")):
                _add(catalog, _action_citation(item))
        elif step.name == "read_github_pr":
            _add(catalog, _pull_request_citation(data))
    return catalog


def _data(result: dict[str, object]) -> dict[str, object] | None:
    if result.get("ok") is not True:
        return None
    data = result.get("data")
    if isinstance(data, dict):
        return data
    return None


def _dicts(value: object) -> list[dict[str, object]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _add(catalog: dict[str, AssistantCitation], citation: AssistantCitation | None) -> None:
    if citation is None:
        return
    current = catalog.get(citation.id)
    if current is None or (current.title == "行动项" and citation.title != "行动项"):
        catalog[citation.id] = citation


def _chunk_citation(hit: dict[str, object]) -> AssistantCitation | None:
    cid = _prefixed(hit.get("id"), "chunk")
    retro_id = _uuid(hit.get("retro_id"))
    if cid is None:
        return None
    excerpt = _text(hit.get("excerpt"))[:280]
    return AssistantCitation(
        id=cid,
        source_type="chunk",
        title=excerpt[:40] or "复盘原文",
        excerpt=excerpt,
        retro_id=retro_id,
        href_hint=f"/retro/{retro_id}/confirm" if retro_id else None,
    )


def _action_citation(item: dict[str, object]) -> AssistantCitation | None:
    cid = _prefixed(item.get("id"), "action")
    action_id = _uuid(cid.removeprefix("action:")) if cid else None
    if cid is None or action_id is None:
        return None
    title = _text(item.get("title")) or "行动项"
    status = _text(item.get("status"))
    due = _text(item.get("due_date"))
    owner = _text(item.get("owner"))
    excerpt = " · ".join(part for part in (status, due, owner) if part)
    return AssistantCitation(
        id=cid,
        source_type="action",
        title=title,
        excerpt=excerpt or title,
        action_id=action_id,
        href_hint="/actions/board",
    )


def _cluster_citation(item: dict[str, object]) -> AssistantCitation | None:
    cid = _prefixed(item.get("id"), "cluster")
    if cid is None:
        return None
    title = _text(item.get("title")) or "重复问题"
    return AssistantCitation(
        id=cid,
        source_type="cluster",
        title=title,
        excerpt=title,
        href_hint="/trends",
    )


def _pull_request_citation(data: dict[str, object]) -> AssistantCitation | None:
    match = re.fullmatch(r"pr:([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)/([1-9][0-9]{0,9})", _text(data.get("id")))
    if match is None:
        return None
    owner, repo, number = match.groups()
    title = _text(data.get("title"))[:120] or f"{owner}/{repo}#{number}"
    excerpt = _text(data.get("body"))[:280] or title
    return AssistantCitation(
        id=match.group(0),
        source_type="pull_request",
        title=title,
        excerpt=excerpt,
        href_hint=f"https://github.com/{owner}/{repo}/pull/{number}",
    )


def _history_citation(data: dict[str, object]) -> AssistantCitation | None:
    if data.get("found") is not True:
        return None
    cid = _prefixed(data.get("action_id"), "action")
    action_id = _uuid(cid.removeprefix("action:")) if cid else None
    if cid is None or action_id is None:
        return None
    return AssistantCitation(
        id=cid,
        source_type="action",
        title="行动项",
        excerpt="状态记录",
        action_id=action_id,
        href_hint="/actions/board",
    )


def _prefixed(value: object, prefix: str) -> str | None:
    if not isinstance(value, str) or not value.startswith(f"{prefix}:"):
        return None
    if _uuid(value.removeprefix(f"{prefix}:")) is None:
        return None
    return value


def _uuid(value: object) -> UUID | None:
    if not isinstance(value, str):
        return None
    try:
        return UUID(value)
    except ValueError:
        return None


def _text(value: object) -> str:
    if value is None:
        return ""
    return str(value)
