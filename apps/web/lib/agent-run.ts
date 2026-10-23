import type { AgentStreamEvent } from "@/lib/api/agent";
import type { AgentAnswer } from "@/types";

export type ToolStep = {
  key: string;
  name: string;
  arguments: Record<string, unknown>;
  ok: boolean | null;
  summary: string | null;
};

export type PendingCard = {
  id: string;
  toolName: string;
  summary: string;
  expiresAt: string;
  resolution: "open" | "approved" | "rejected";
  actionTitle: string | null;
  notice: string | null;
  locked: boolean;
};

export type WorkbenchState = {
  runId: string | null;
  steps: ToolStep[];
  pendings: PendingCard[];
  answer: AgentAnswer | null;
  errorCode: string | null;
};

export function emptyWorkbench(): WorkbenchState {
  return {
    runId: null,
    steps: [],
    pendings: [],
    answer: null,
    errorCode: null,
  };
}

export function applyAgentEvent(state: WorkbenchState, event: AgentStreamEvent): WorkbenchState {
  if (event.event === "run_started") {
    return { ...emptyWorkbench(), runId: event.data.run_id };
  }
  if (event.event === "tool_call") {
    const step: ToolStep = {
      key: `${state.steps.length}-${event.data.name}`,
      name: event.data.name,
      arguments: event.data.arguments,
      ok: null,
      summary: null,
    };
    return { ...state, steps: [...state.steps, step] };
  }
  if (event.event === "tool_result") {
    const index = state.steps.findIndex(
      (step) => step.name === event.data.name && step.ok === null,
    );
    if (index < 0) return state;
    const steps = state.steps.slice();
    const current = steps[index];
    if (!current) return state;
    steps[index] = { ...current, ok: event.data.ok, summary: event.data.summary };
    return { ...state, steps };
  }
  if (event.event === "pending_operation") {
    if (state.pendings.some((item) => item.id === event.data.id)) return state;
    const card: PendingCard = {
      id: event.data.id,
      toolName: event.data.tool_name,
      summary: event.data.summary,
      expiresAt: event.data.expires_at,
      resolution: "open",
      actionTitle: null,
      notice: null,
      locked: false,
    };
    return { ...state, pendings: [...state.pendings, card] };
  }
  if (event.event === "answer") {
    return {
      ...state,
      runId: event.data.run_id ?? state.runId,
      answer: {
        status: event.data.status,
        answer: event.data.answer,
        citations: event.data.citations,
        runId: event.data.run_id,
      },
    };
  }
  if (event.event === "error") {
    return { ...state, errorCode: event.data.code };
  }
  return state;
}
