from app.agent.tools.actions import get_action_history_tool, list_actions_tool
from app.agent.tools.base import ToolSpec
from app.agent.tools.github import read_github_pr_tool
from app.agent.tools.problems import find_similar_problems_tool
from app.agent.tools.proposals import propose_action_tool, propose_status_change_tool
from app.agent.tools.search import search_retro_content_tool
from app.agent.tools.trends import get_trends_tool


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, ToolSpec] = {}

    def register(self, tool: ToolSpec) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> ToolSpec | None:
        return self._tools.get(name)

    def openai_tools(self) -> list[dict[str, object]]:
        return [tool.openai_schema() for tool in self._tools.values()]


def build_default_registry() -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(search_retro_content_tool)
    registry.register(find_similar_problems_tool)
    registry.register(list_actions_tool)
    registry.register(get_action_history_tool)
    registry.register(get_trends_tool)
    registry.register(read_github_pr_tool)
    registry.register(propose_action_tool)
    registry.register(propose_status_change_tool)
    return registry


default_registry = build_default_registry()
