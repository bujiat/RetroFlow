import { apiRequest, openApiStream } from "@/lib/api/client";
import type {
  ActionItem,
  AgentAnswerStatus,
  AgentRunDetail,
  AgentRunList,
  AssistantCitation,
  PendingOperation,
} from "@/types";

export type AgentStreamEvent =
  | { event: "run_started"; data: { run_id: string } }
  | { event: "tool_call"; data: { name: string; arguments: Record<string, unknown> } }
  | { event: "tool_result"; data: { name: string; ok: boolean; summary: string } }
  | { event: "pending_operation"; data: PendingOperation }
  | {
      event: "answer";
      data: {
        status: AgentAnswerStatus;
        answer: string;
        citations: AssistantCitation[];
        run_id: string | null;
      };
    }
  | { event: "error"; data: { code: string } }
  | { event: "done"; data: { ok: boolean } };

export type ConfirmOperationResult = {
  operation: PendingOperation;
  action: ActionItem;
};

const ANSWER_STATUSES: readonly AgentAnswerStatus[] = [
  "answered",
  "insufficient_evidence",
  "max_steps",
  "tool_failures",
];

export async function streamAgentChat(
  question: string,
  onEvent: (event: AgentStreamEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  const response = await openApiStream(
    "/agent/chat",
    { question },
    "agent_chat_failed",
    signal,
  );
  const reader = response.body?.getReader();
  if (!reader) return;
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    buffer = buffer.replace(/\r\n/g, "\n");
    const frames = buffer.split("\n\n");
    buffer = frames.pop() ?? "";
    for (const frame of frames) {
      const event = parseSseFrame(frame);
      if (event) onEvent(event);
    }
  }
  const tail = parseSseFrame(buffer);
  if (tail) onEvent(tail);
}

export function confirmOperation(id: string): Promise<ConfirmOperationResult> {
  return apiRequest<ConfirmOperationResult>(`/agent/operations/${id}/confirm`, {
    method: "POST",
    fallbackError: "confirm_operation_failed",
  });
}

export function listAgentRuns(): Promise<AgentRunList> {
  return apiRequest<AgentRunList>("/agent/runs", {
    method: "GET",
    fallbackError: "list_agent_runs_failed",
  });
}

export function getAgentRun(id: string): Promise<AgentRunDetail> {
  return apiRequest<AgentRunDetail>(`/agent/runs/${id}`, {
    method: "GET",
    fallbackError: "get_agent_run_failed",
  });
}

export function rejectOperation(id: string): Promise<PendingOperation> {
  return apiRequest<PendingOperation>(`/agent/operations/${id}/reject`, {
    method: "POST",
    fallbackError: "reject_operation_failed",
  });
}

export function parseSseFrame(raw: string): AgentStreamEvent | null {
  let eventName = "message";
  const dataLines: string[] = [];
  for (const line of raw.split("\n")) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith(":")) continue;
    if (trimmed.startsWith("event:")) {
      eventName = trimmed.slice("event:".length).trim();
    } else if (trimmed.startsWith("data:")) {
      dataLines.push(trimmed.slice("data:".length).trim());
    }
  }
  if (dataLines.length === 0) return null;
  let parsed: unknown;
  try {
    parsed = JSON.parse(dataLines.join("\n"));
  } catch {
    return null;
  }
  return eventFrom(eventName, parsed);
}

function eventFrom(eventName: string, parsed: unknown): AgentStreamEvent | null {
  if (!isRecord(parsed)) return null;
  if (eventName === "run_started" && typeof parsed.run_id === "string") {
    return { event: "run_started", data: { run_id: parsed.run_id } };
  }
  if (eventName === "tool_call" && typeof parsed.name === "string") {
    return {
      event: "tool_call",
      data: {
        name: parsed.name,
        arguments: isRecord(parsed.arguments) ? parsed.arguments : {},
      },
    };
  }
  if (eventName === "tool_result" && typeof parsed.name === "string") {
    return {
      event: "tool_result",
      data: {
        name: parsed.name,
        ok: parsed.ok === true,
        summary: typeof parsed.summary === "string" ? parsed.summary : "",
      },
    };
  }
  if (
    eventName === "pending_operation" &&
    typeof parsed.id === "string" &&
    typeof parsed.tool_name === "string" &&
    typeof parsed.summary === "string" &&
    typeof parsed.expires_at === "string"
  ) {
    return {
      event: "pending_operation",
      data: {
        id: parsed.id,
        tool_name: parsed.tool_name,
        summary: parsed.summary,
        expires_at: parsed.expires_at,
      },
    };
  }
  if (eventName === "answer" && isAnswerStatus(parsed.status) && typeof parsed.answer === "string") {
    return {
      event: "answer",
      data: {
        status: parsed.status,
        answer: parsed.answer,
        citations: readCitations(parsed.citations),
        run_id: typeof parsed.run_id === "string" ? parsed.run_id : null,
      },
    };
  }
  if (eventName === "error" && typeof parsed.code === "string") {
    return { event: "error", data: { code: parsed.code } };
  }
  if (eventName === "done") {
    return { event: "done", data: { ok: parsed.ok === true } };
  }
  return null;
}

function readCitations(value: unknown): AssistantCitation[] {
  if (!Array.isArray(value)) return [];
  return value.flatMap((item) => {
    const citation = readCitation(item);
    return citation ? [citation] : [];
  });
}

function readCitation(value: unknown): AssistantCitation | null {
  if (!isRecord(value)) return null;
  const source = value.source_type;
  if (
    source !== "action" &&
    source !== "cluster" &&
    source !== "chunk" &&
    source !== "problem" &&
    source !== "pull_request"
  ) {
    return null;
  }
  if (
    typeof value.id !== "string" ||
    typeof value.title !== "string" ||
    typeof value.excerpt !== "string"
  ) {
    return null;
  }
  return {
    id: value.id,
    source_type: source,
    title: value.title,
    excerpt: value.excerpt,
    retro_id: typeof value.retro_id === "string" ? value.retro_id : null,
    action_id: typeof value.action_id === "string" ? value.action_id : null,
    href_hint: typeof value.href_hint === "string" ? value.href_hint : null,
  };
}

function isAnswerStatus(value: unknown): value is AgentAnswerStatus {
  return typeof value === "string" && ANSWER_STATUSES.includes(value as AgentAnswerStatus);
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
