import { apiRequest } from "@/lib/api/client";
import type { AssistantQueryResponse } from "@/types";

export type { AssistantQueryResponse } from "@/types";

export function queryAssistant(question: string): Promise<AssistantQueryResponse> {
  return apiRequest<AssistantQueryResponse>("/assistant/query", {
    method: "POST",
    body: { question },
    fallbackError: "assistant_query_failed",
  });
}
