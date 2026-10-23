"""Live check: DeepSeek returns an OpenAI-style tool call, then a final answer.

Run from apps/api:

    .\\.venv\\Scripts\\python.exe scripts/check_deepseek_tools.py

The API key stays in the environment. This script never prints it.
"""

import json
import sys

from app.providers.llm import LlmError, chat_with_tools

_TOOL = {
    "type": "function",
    "function": {
        "name": "lookup_demo_fact",
        "description": "返回一条固定的演示事实。topic 只能是 checklist。",
        "parameters": {
            "type": "object",
            "properties": {"topic": {"type": "string", "enum": ["checklist"]}},
            "required": ["topic"],
            "additionalProperties": False,
        },
    },
}


def main() -> int:
    messages: list[dict[str, object]] = [
        {
            "role": "system",
            "content": "你只能根据工具结果回答。需要事实时必须调用 lookup_demo_fact。",
        },
        {
            "role": "user",
            "content": "发布清单遗漏出现了几次？请调用 lookup_demo_fact，topic 填 checklist。",
        },
    ]
    try:
        first = chat_with_tools(messages, [_TOOL])
    except LlmError as exc:
        print(f"model_error: {exc.message}")
        return 1
    if not first.tool_calls:
        print("no_tool_call")
        print(f"content: {first.content}")
        return 1

    for call in first.tool_calls:
        print(f"tool_call: {call.name} {json.dumps(call.arguments, ensure_ascii=False)}")
    messages.append(
        {
            "role": "assistant",
            "content": first.content,
            "tool_calls": [
                {
                    "id": item.id,
                    "type": "function",
                    "function": {
                        "name": item.name,
                        "arguments": json.dumps(item.arguments, ensure_ascii=False),
                    },
                }
                for item in first.tool_calls
            ],
        }
    )
    for call in first.tool_calls:
        fact = "发布清单遗漏出现了三次。" if call.arguments.get("topic") == "checklist" else "未知主题。"
        messages.append(
            {
                "role": "tool",
                "tool_call_id": call.id,
                "content": json.dumps({"fact": fact}, ensure_ascii=False),
            }
        )
    try:
        second = chat_with_tools(messages, [_TOOL])
    except LlmError as exc:
        print(f"model_error: {exc.message}")
        return 1
    if second.tool_calls and not second.content:
        print("second_turn_still_called_a_tool")
        print(f"tool_call: {second.tool_calls[0].name}")
        return 1
    print(f"final_answer: {second.content}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
