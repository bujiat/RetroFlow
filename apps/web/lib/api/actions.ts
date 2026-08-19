import { apiRequest } from "@/lib/api/client";
import type { ActionEvent, ActionItem, MyWeek } from "@/types";

export type { ActionEvent, ActionItem, ActionStatus, MyWeek } from "@/types";

export function listActions(): Promise<ActionItem[]> {
  return apiRequest<ActionItem[]>("/actions", {
    method: "GET",
    fallbackError: "list_actions_failed",
  });
}

export function getMyWeek(): Promise<MyWeek> {
  return apiRequest<MyWeek>("/actions/my-week", {
    method: "GET",
    fallbackError: "my_week_failed",
  });
}

export function listActionEvents(id: string): Promise<ActionEvent[]> {
  return apiRequest<ActionEvent[]>(`/actions/${id}/events`, {
    method: "GET",
    fallbackError: "list_action_events_failed",
  });
}

export function patchActionStatus(
  id: string,
  status: "open" | "in_progress" | "cancelled",
): Promise<ActionItem> {
  return apiRequest<ActionItem>(`/actions/${id}`, {
    method: "PATCH",
    body: { status },
    fallbackError: "patch_action_failed",
  });
}

export function submitEvidence(
  id: string,
  input: {
    completion_note: string;
    evidence_text?: string | null;
    evidence_url?: string | null;
  },
): Promise<ActionItem> {
  return apiRequest<ActionItem>(`/actions/${id}/evidence`, {
    method: "POST",
    body: input,
    fallbackError: "submit_evidence_failed",
  });
}

export function verifyAction(id: string): Promise<ActionItem> {
  return apiRequest<ActionItem>(`/actions/${id}/verify`, {
    method: "POST",
    fallbackError: "verify_action_failed",
  });
}

export function rejectAction(id: string, reject_reason: string): Promise<ActionItem> {
  return apiRequest<ActionItem>(`/actions/${id}/reject`, {
    method: "POST",
    body: { reject_reason },
    fallbackError: "reject_action_failed",
  });
}
