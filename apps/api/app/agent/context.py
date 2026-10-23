from contextlib import contextmanager
from contextvars import ContextVar
from uuid import UUID

_run_id: ContextVar[UUID | None] = ContextVar("agent_run_id", default=None)


def current_run_id() -> UUID | None:
    return _run_id.get()


@contextmanager
def bind_run(run_id: UUID | None):
    if run_id is None:
        yield
        return
    token = _run_id.set(run_id)
    try:
        yield
    finally:
        _run_id.reset(token)
