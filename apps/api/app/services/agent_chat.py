import asyncio
import json
import threading
from collections.abc import AsyncIterator, Callable, Iterator
from uuid import UUID

from fastapi import HTTPException, status
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy.orm import Session

from app.agent.citations import catalog_from_steps
from app.agent.loop import AgentRunResult, iterate_agent, run_agent
from app.core.config import settings
from app.core.db import SessionLocal
from app.core.errors import api_error
from app.models.agent_run import AgentRun
from app.models.user import User
from app.providers.llm import LlmError
from app.providers.prompts import AGENT_CHAT_SYSTEM_PROMPT
from app.schemas.agent import AgentChatRequest, AgentChatResponse
from app.schemas.assistant import AssistantCitation
from app.services.pending import pending_from_steps

_REFUSAL = "模型没有给出可核对的来源，已拒绝回答。请换个问法，或确认相关复盘已完成分析索引。"


class _FinalAnswer(BaseModel):
    status: str
    answer: str
    citation_ids: list[str] = Field(default_factory=list)


def chat(db: Session, user: User, payload: AgentChatRequest) -> AgentChatResponse:
    question = payload.question.strip()
    if len(question) < 2:
        raise api_error(status.HTTP_400_BAD_REQUEST, "question_too_short")
    messages: list[dict[str, object]] = [
        {"role": "system", "content": AGENT_CHAT_SYSTEM_PROMPT},
        {"role": "user", "content": question},
    ]
    try:
        result = run_agent(db, user_id=user.id, messages=messages)
    except LlmError as exc:
        db.commit()
        raise api_error(status.HTTP_502_BAD_GATEWAY, exc.message) from exc
    try:
        response = _public_response(result)
    except HTTPException:
        _mark_run(db, result.run_id, "invalid_answer", result.answer)
        db.commit()
        raise
    response.pending_operations = pending_from_steps(result.steps)
    _align_trace(db, response)
    db.commit()
    return response


def format_sse(event: str, data: dict[str, object]) -> str:
    payload = json.dumps(data, ensure_ascii=False, default=str)
    return f"event: {event}\ndata: {payload}\n\n"


def iter_sse(db: Session, user_id: UUID, payload: AgentChatRequest) -> Iterator[str]:
    """Yield SSE frames as the loop runs. The caller commits only through this function."""
    question = payload.question.strip()
    if len(question) < 2:
        raise api_error(status.HTTP_400_BAD_REQUEST, "question_too_short")
    messages: list[dict[str, object]] = [
        {"role": "system", "content": AGENT_CHAT_SYSTEM_PROMPT},
        {"role": "user", "content": question},
    ]
    result: AgentRunResult | None = None
    try:
        for item in iterate_agent(db, user_id=user_id, messages=messages):
            if isinstance(item, AgentRunResult):
                result = item
                continue
            yield format_sse(item.name, item.data)
    except LlmError as exc:
        db.commit()
        yield format_sse("error", {"code": exc.message})
        yield format_sse("done", {"ok": False})
        return
    if result is None:
        yield format_sse("error", {"code": "agent_chat_failed"})
        yield format_sse("done", {"ok": False})
        return
    try:
        response = _public_response(result)
    except HTTPException as exc:
        _mark_run(db, result.run_id, "invalid_answer", result.answer)
        db.commit()
        yield format_sse("error", {"code": _error_code(exc)})
        yield format_sse("done", {"ok": False})
        return
    response.pending_operations = pending_from_steps(result.steps)
    _align_trace(db, response)
    db.commit()
    yield format_sse("answer", _answer_payload(response))
    yield format_sse("done", {"ok": True})


async def stream_chat(
    user_id: UUID,
    payload: AgentChatRequest,
    *,
    open_session: Callable[[], Session] | None = None,
) -> AsyncIterator[str]:
    """Run iter_sse on one thread so each frame can leave before the next model call."""
    loop = asyncio.get_running_loop()
    frames: asyncio.Queue[str | None] = asyncio.Queue()
    opener = open_session or SessionLocal

    def emit(frame: str | None) -> None:
        try:
            loop.call_soon_threadsafe(frames.put_nowait, frame)
        except RuntimeError:
            return

    def worker() -> None:
        try:
            db = opener()
            try:
                for frame in iter_sse(db, user_id, payload):
                    emit(frame)
            finally:
                db.close()
        except Exception:
            # A failure here is already off the request thread. The client only
            # learns about it if this frame still goes out.
            emit(format_sse("error", {"code": "agent_chat_failed"}))
            emit(format_sse("done", {"ok": False}))
        finally:
            emit(None)

    threading.Thread(target=worker, daemon=True).start()
    while True:
        frame = await frames.get()
        if frame is None:
            break
        yield frame


def _answer_payload(response: AgentChatResponse) -> dict[str, object]:
    return {
        "status": response.status,
        "answer": response.answer,
        "citations": [item.model_dump(mode="json") for item in response.citations],
        "run_id": str(response.run_id) if response.run_id else None,
    }


def _error_code(exc: HTTPException) -> str:
    detail = exc.detail
    if isinstance(detail, dict):
        code = detail.get("code")
        if isinstance(code, str):
            return code
    return "agent_chat_failed"


def _public_response(result: AgentRunResult) -> AgentChatResponse:
    if result.status in {"max_steps", "tool_failures"}:
        return AgentChatResponse(
            status=result.status,
            answer=result.answer or "",
            citations=[],
            run_id=result.run_id,
        )
    try:
        parsed = _parse_final_answer(result.answer)
    except (ValidationError, json.JSONDecodeError, ValueError) as exc:
        raise api_error(status.HTTP_502_BAD_GATEWAY, "assistant_schema_invalid") from exc
    citations = _valid_citations(parsed.citation_ids, catalog_from_steps(result.steps))
    status_value = parsed.status
    if status_value not in {"answered", "insufficient_evidence"}:
        status_value = "insufficient_evidence"
    if status_value == "answered" and not citations:
        return AgentChatResponse(
            status="insufficient_evidence",
            answer=_REFUSAL,
            citations=[],
            run_id=result.run_id,
        )
    return AgentChatResponse(
        status=status_value,
        answer=parsed.answer.strip() or "（空回答）",
        citations=citations,
        run_id=result.run_id,
    )


def _valid_citations(
    citation_ids: list[str],
    catalog: dict[str, AssistantCitation],
) -> list[AssistantCitation]:
    valid: list[AssistantCitation] = []
    seen: set[str] = set()
    for cid in citation_ids:
        if cid in catalog and cid not in seen:
            valid.append(catalog[cid])
            seen.add(cid)
        if len(valid) >= settings.rag_max_citations:
            break
    return valid


def _parse_final_answer(raw: str | None) -> _FinalAnswer:
    if not raw or not raw.strip():
        raise ValueError("empty answer")
    text = raw.strip()
    if text.startswith("```"):
        text = text.removeprefix("```json").removeprefix("```").strip()
        if text.endswith("```"):
            text = text[: -len("```")].strip()
    try:
        return _FinalAnswer.model_validate_json(text)
    except (ValidationError, json.JSONDecodeError):
        start = text.find("{")
        end = text.rfind("}")
        if start < 0 or end <= start:
            raise
        return _FinalAnswer.model_validate_json(text[start : end + 1])


def _align_trace(db: Session, response: AgentChatResponse) -> None:
    _mark_run(db, response.run_id, response.status, response.answer)


def _mark_run(db: Session, run_id: UUID | None, status_value: str, output: str | None) -> None:
    if run_id is None:
        return
    run = db.get(AgentRun, run_id)
    if run is None:
        return
    run.status = status_value
    if output is not None:
        run.output = output
