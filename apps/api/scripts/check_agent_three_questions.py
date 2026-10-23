"""Live check: three questions should call different tools and return citations.

Run from apps/api while the API is listening on 127.0.0.1:8000:

    .\\.venv\\Scripts\\python.exe scripts/check_agent_three_questions.py
"""

import json
import sys

import httpx

_BASE = "http://127.0.0.1:8000/api/v1"
_QUESTIONS = (
    "发布当天数据库迁移没有跑，复盘原文里是怎么说的？",
    "现在还有哪些未完成的行动项？",
    "逾期有几条，验收率是多少？",
)


def main() -> int:
    failed = False
    seen: set[str] = set()
    with httpx.Client(timeout=180.0) as client:
        login = client.post(
            f"{_BASE}/auth/login",
            json={"email": "demo@example.com", "password": "demo1234"},
        )
        login.raise_for_status()
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
        for question in _QUESTIONS:
            print("=" * 20)
            print(f"question: {question}")
            names = _ask(client, headers, question)
            seen.update(names)
            if not names:
                failed = True
    print("=" * 20)
    print("tools_seen:", ", ".join(sorted(seen)) if seen else "(none)")
    if failed or len(seen) < 2:
        return 1
    return 0


def _ask(client: httpx.Client, headers: dict[str, str], question: str) -> list[str]:
    names: list[str] = []
    with client.stream(
        "POST",
        f"{_BASE}/agent/chat",
        headers=headers,
        json={"question": question},
    ) as response:
        print(f"http: {response.status_code}")
        response.raise_for_status()
        event: str | None = None
        data_lines: list[str] = []
        for line in response.iter_lines():
            if line != "":
                if line.startswith("event:"):
                    event = line.split(":", 1)[1].strip()
                elif line.startswith("data:"):
                    data_lines.append(line.split(":", 1)[1].strip())
                continue
            if event and data_lines:
                payload = json.loads("\n".join(data_lines))
                names.extend(_print_event(event, payload))
            event = None
            data_lines = []
    print("tools:", ", ".join(names) if names else "(none)")
    return names


def _print_event(event: str, payload: dict[str, object]) -> list[str]:
    if event == "tool_call":
        print(f"tool_call: {payload.get('name')} {json.dumps(payload.get('arguments'), ensure_ascii=False)}")
        name = payload.get("name")
        return [name] if isinstance(name, str) else []
    if event == "tool_result":
        print(f"tool_result: {payload.get('name')} ok={payload.get('ok')}")
    elif event == "answer":
        citations = payload.get("citations")
        ids = [item.get("id") for item in citations] if isinstance(citations, list) else []
        print(f"status: {payload.get('status')}")
        print("citations:", ", ".join(str(item) for item in ids) if ids else "(none)")
        print(f"answer: {payload.get('answer')}")
    elif event in {"error", "done"}:
        print(f"{event}: {json.dumps(payload, ensure_ascii=False)}")
    return []


if __name__ == "__main__":
    sys.exit(main())
