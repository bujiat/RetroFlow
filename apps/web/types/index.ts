/** App Router 动态段 [locale] 注入给 layout / page 的 params */
export type LocaleParams = Promise<{ locale: string }>;

export type LocaleIdParams = Promise<{ locale: string; id: string }>;

export type RetroType = "sprint" | "incident" | "release";

export type RetroListItem = {
  id: string;
  type: RetroType;
  title: string;
  review_date: string;
  status: string;
  created_at: string;
};

export type AnalysisSummary = {
  keep: string[];
  decisions: { decision: string; reason: string }[];
  risks: { risk: string; suggestion: string }[];
};

export type ActionDraft = {
  id: string;
  title: string;
  description: string;
  suggested_success_criteria: string;
};

export type ProblemItem = {
  id: string;
  title: string;
  normalized_statement: string;
  category: string;
  severity: string;
  source_quote: string;
  disposition: string;
  match_status: string;
  cluster_id?: string | null;
  cluster_title?: string | null;
  suggested_actions: ActionDraft[];
};

export type RetroDetail = RetroListItem & {
  raw_content: string;
  index_status: string;
  analysis_error: string | null;
  analysis_summary: AnalysisSummary | null;
  updated_at: string;
  problems: ProblemItem[];
};

export type CreateRetroInput = {
  type: RetroType;
  title: string;
  review_date: string;
  raw_content: string;
};

export type ActionStatus =
  | "open"
  | "in_progress"
  | "evidence_submitted"
  | "verified"
  | "cancelled";

export type ActionItem = {
  id: string;
  retro_id: string;
  problem_occurrence_id: string;
  title: string;
  description: string;
  owner: string;
  due_date: string;
  success_criteria: string;
  status: ActionStatus | string;
  verified_at?: string | null;
  created_at: string;
};

export type MyWeek = {
  overdue: ActionItem[];
  due_this_week: ActionItem[];
  awaiting_verify: ActionItem[];
};

export type ActionEvent = {
  id: string;
  event_type: string;
  from_status: string | null;
  to_status: string | null;
  note: string | null;
  evidence_text: string | null;
  evidence_url: string | null;
  created_at: string;
};

export type OverdueActionBrief = {
  id: string;
  title: string;
  owner: string;
  due_date: string;
  status: string;
};

export type TrendsSummary = {
  overdue_actions: number;
  awaiting_work: number;
  awaiting_verify: number;
  verified_actions: number;
  cancelled_actions: number;
  verification_rate: number | null;
  kept_problems: number;
  published_retros: number;
  recurring_clusters: number;
  top_clusters: { id: string; title: string; occurrence_count: number }[];
  overdue_items: OverdueActionBrief[];
};

export type AssistantCitation = {
  id: string;
  source_type: "action" | "cluster" | "chunk" | "problem";
  title: string;
  excerpt: string;
  retro_id?: string | null;
  action_id?: string | null;
  href_hint?: string | null;
};

export type AssistantQueryResponse = {
  status: "answered" | "insufficient_evidence";
  answer: string;
  citations: AssistantCitation[];
};

export type WeeklyReviewCitation = {
  id: string;
  source_type: "action" | "event" | "retro" | "cluster";
  title: string;
  excerpt: string;
  retro_id?: string | null;
  action_id?: string | null;
  href_hint?: string | null;
};

export type WeeklyReview = {
  week_start: string;
  week_end: string;
  status: "ok" | "empty" | "insufficient_evidence";
  content_markdown: string;
  citations: WeeklyReviewCitation[];
  saved: boolean;
};
