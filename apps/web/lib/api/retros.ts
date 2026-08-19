import { apiRequest } from "@/lib/api/client";
import type { CreateRetroInput, RetroDetail, RetroListItem } from "@/types";

export type { CreateRetroInput, RetroDetail, RetroListItem, RetroType } from "@/types";

export function listRetros(): Promise<RetroListItem[]> {
  return apiRequest<RetroListItem[]>("/retros", {
    method: "GET",
    fallbackError: "list_retros_failed",
  });
}

export function getRetro(id: string): Promise<RetroDetail> {
  return apiRequest<RetroDetail>(`/retros/${id}`, {
    method: "GET",
    fallbackError: "get_retro_failed",
  });
}

export function createRetro(input: CreateRetroInput): Promise<RetroListItem> {
  return apiRequest<RetroListItem>("/retros", {
    method: "POST",
    body: input,
    fallbackError: "create_retro_failed",
  });
}

export function analyzeRetro(id: string): Promise<RetroDetail> {
  return apiRequest<RetroDetail>(`/retros/${id}/analyze`, {
    method: "POST",
    fallbackError: "analyze_retro_failed",
  });
}

export type PublishActionInput = {
  action_draft_id: string;
  owner: string;
  due_date: string;
  success_criteria: string;
};

export type PublishRetroInput = {
  discarded_problem_ids: string[];
  discarded_action_draft_ids: string[];
  actions: PublishActionInput[];
};

export function publishRetro(id: string, input: PublishRetroInput): Promise<RetroDetail> {
  return apiRequest<RetroDetail>(`/retros/${id}/publish`, {
    method: "POST",
    body: input,
    fallbackError: "publish_retro_failed",
  });
}

