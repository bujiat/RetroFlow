import { apiRequest } from "@/lib/api/client";
import type { TrendsSummary } from "@/types";

export type { TrendsSummary } from "@/types";

export function getTrendsSummary(): Promise<TrendsSummary> {
  return apiRequest<TrendsSummary>("/trends/summary", {
    method: "GET",
    fallbackError: "trends_summary_failed",
  });
}
