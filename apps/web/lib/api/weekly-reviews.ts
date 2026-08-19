import { apiRequest } from "@/lib/api/client";
import type { WeeklyReview } from "@/types";

export type { WeeklyReview } from "@/types";

export function getCurrentWeeklyReview(): Promise<WeeklyReview> {
  return apiRequest<WeeklyReview>("/weekly-reviews/current", {
    method: "GET",
    fallbackError: "get_weekly_review_failed",
  });
}

export function generateWeeklyReview(weekStart?: string): Promise<WeeklyReview> {
  return apiRequest<WeeklyReview>("/weekly-reviews/generate", {
    method: "POST",
    body: weekStart ? { week_start: weekStart } : {},
    fallbackError: "generate_weekly_review_failed",
  });
}

export function saveWeeklyReview(
  weekStart: string,
  input: {
    content_markdown: string;
    citation_ids: string[];
  },
): Promise<WeeklyReview> {
  return apiRequest<WeeklyReview>(`/weekly-reviews/${weekStart}`, {
    method: "PUT",
    body: input,
    fallbackError: "save_weekly_review_failed",
  });
}
