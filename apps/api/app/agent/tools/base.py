from collections.abc import Callable
from dataclasses import dataclass
from typing import Generic, TypeVar
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy.orm import Session

ArgsT = TypeVar("ArgsT", bound=BaseModel)
ToolHandler = Callable[[Session, UUID, ArgsT], dict[str, object]]


@dataclass(frozen=True)
class ToolSpec(Generic[ArgsT]):
    """One tool: name, description, argument model, and the function that runs it."""

    name: str
    description: str
    args_model: type[ArgsT]
    handler: ToolHandler[ArgsT]

    def openai_schema(self) -> dict[str, object]:
        parameters = self.args_model.model_json_schema()
        parameters.pop("title", None)
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": parameters,
            },
        }
