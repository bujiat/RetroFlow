"use client";

import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";

import { Link, useRouter } from "@/i18n/navigation";
import { ApiError, failedRequestMessage, redirectToLoginIfUnauthorized } from "@/lib/api/client";
import {
  listProblemClusters,
  relinkOccurrenceCluster,
  type ProblemCluster,
} from "@/lib/api/problems";
import {
  analyzeRetro,
  getRetro,
  publishRetro,
  type RetroDetail,
} from "@/lib/api/retros";
import type { AnalysisSummary } from "@/types";

function summaryHasItems(summary: AnalysisSummary | null): boolean {
  if (!summary) return false;
  return (
    summary.keep.length > 0 ||
    summary.decisions.length > 0 ||
    summary.risks.length > 0
  );
}

type RetroConfirmViewProps = {
  retroId: string;
};

type ActionEdit = {
  owner: string;
  due_date: string;
  success_criteria: string;
};

function defaultDueDate(): string {
  const d = new Date();
  d.setDate(d.getDate() + 7);
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

const TYPE_META: Record<string, { emoji: string; labelKey: "typeSprint" | "typeIncident" | "typeRelease" }> = {
  sprint: { emoji: "🚀", labelKey: "typeSprint" },
  incident: { emoji: "⚙️", labelKey: "typeIncident" },
  release: { emoji: "🎨", labelKey: "typeRelease" },
};

const STATUS_KEYS = ["draft", "analyzing", "analysis_failed", "ready_for_review", "published"] as const;

export function RetroConfirmView({ retroId }: RetroConfirmViewProps) {
  const t = useTranslations("retroConfirm");
  const tStatus = useTranslations("retros");
  const tType = useTranslations("retroNew");
  const tCommon = useTranslations("common");
  const router = useRouter();
  const [retro, setRetro] = useState<RetroDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [publishing, setPublishing] = useState(false);
  const [discardedProblems, setDiscardedProblems] = useState<Set<string>>(new Set());
  const [discardedActions, setDiscardedActions] = useState<Set<string>>(new Set());
  const [actionEdits, setActionEdits] = useState<Record<string, ActionEdit>>({});
  const [editingClusterFor, setEditingClusterFor] = useState<string | null>(null);
  const [clusterOptions, setClusterOptions] = useState<ProblemCluster[]>([]);
  const [newClusterTitle, setNewClusterTitle] = useState("");
  const [clusterBusy, setClusterBusy] = useState(false);

  function syncEditsFromRetro(data: RetroDetail) {
    const next: Record<string, ActionEdit> = {};
    for (const problem of data.problems) {
      for (const action of problem.suggested_actions) {
        next[action.id] = {
          owner: "",
          due_date: defaultDueDate(),
          success_criteria: action.suggested_success_criteria,
        };
      }
    }
    setActionEdits(next);
    setDiscardedProblems(new Set());
    setDiscardedActions(new Set());
  }

  async function load() {
    try {
      const data = await getRetro(retroId);
      setRetro(data);
      setError(null);
      if (data.status === "ready_for_review") {
        syncEditsFromRetro(data);
      }
    } catch (err) {
      if (redirectToLoginIfUnauthorized(err, router.replace)) return;
      if (err instanceof ApiError && (err.code === "retro_not_found" || err.status === 404)) {
        setError(t("notFound"));
        return;
      }
      setError(
        failedRequestMessage(err, {
          network: tCommon("networkError"),
          fallback: t("loadFailed"),
        }),
      );
    }
  }

  useEffect(() => {
    let cancelled = false;

    async function run() {
      try {
        const data = await getRetro(retroId);
        if (cancelled) return;
        setRetro(data);
        setError(null);
        if (data.status === "ready_for_review") {
          syncEditsFromRetro(data);
        }
      } catch (err) {
        if (cancelled) return;
        if (redirectToLoginIfUnauthorized(err, router.replace)) return;
        if (err instanceof ApiError && (err.code === "retro_not_found" || err.status === 404)) {
          setError(t("notFound"));
          return;
        }
        setError(
          failedRequestMessage(err, {
            network: tCommon("networkError"),
            fallback: t("loadFailed"),
          }),
        );
      }
    }

    void run();
    return () => {
      cancelled = true;
    };
  }, [retroId, router, t, tCommon]);

  async function onRetryAnalyze() {
    setAnalyzing(true);
    setError(null);
    try {
      const data = await analyzeRetro(retroId);
      setRetro(data);
      syncEditsFromRetro(data);
    } catch (err) {
      if (redirectToLoginIfUnauthorized(err, router.replace)) return;
      setError(
        err instanceof ApiError && err.code === "llm_not_configured"
          ? t("llmNotConfigured")
          : t("analyzeFailed"),
      );
      await load();
    } finally {
      setAnalyzing(false);
    }
  }

  function updateAction(id: string, patch: Partial<ActionEdit>) {
    setActionEdits((prev) => ({
      ...prev,
      [id]: { ...prev[id], ...patch },
    }));
  }

  async function openClusterEditor(problemId: string) {
    setEditingClusterFor(problemId);
    setNewClusterTitle("");
    setClusterBusy(true);
    try {
      setClusterOptions(await listProblemClusters());
    } catch (err) {
      if (redirectToLoginIfUnauthorized(err, router.replace)) return;
      setError(t("clusterLoadFailed"));
    } finally {
      setClusterBusy(false);
    }
  }

  async function applyClusterLink(problemId: string, clusterId: string) {
    setClusterBusy(true);
    setError(null);
    try {
      const cluster = await relinkOccurrenceCluster(problemId, { cluster_id: clusterId });
      setRetro((prev) => {
        if (!prev) return prev;
        return {
          ...prev,
          problems: prev.problems.map((p) =>
            p.id === problemId
              ? {
                  ...p,
                  cluster_id: cluster.id,
                  cluster_title: cluster.canonical_title,
                  match_status: "manual",
                }
              : p,
          ),
        };
      });
      setEditingClusterFor(null);
    } catch (err) {
      if (redirectToLoginIfUnauthorized(err, router.replace)) return;
      setError(t("clusterUpdateFailed"));
    } finally {
      setClusterBusy(false);
    }
  }

  async function applyNewCluster(problemId: string) {
    const title = newClusterTitle.trim();
    if (!title) {
      setError(t("clusterTitleRequired"));
      return;
    }
    setClusterBusy(true);
    setError(null);
    try {
      const cluster = await relinkOccurrenceCluster(problemId, {
        new_cluster_title: title,
      });
      setRetro((prev) => {
        if (!prev) return prev;
        return {
          ...prev,
          problems: prev.problems.map((p) =>
            p.id === problemId
              ? {
                  ...p,
                  cluster_id: cluster.id,
                  cluster_title: cluster.canonical_title,
                  match_status: "manual",
                }
              : p,
          ),
        };
      });
      setEditingClusterFor(null);
      setNewClusterTitle("");
    } catch (err) {
      if (redirectToLoginIfUnauthorized(err, router.replace)) return;
      setError(t("clusterUpdateFailed"));
    } finally {
      setClusterBusy(false);
    }
  }

  async function onPublish() {
    if (!retro) return;
    setError(null);

    const actions = [];
    for (const problem of retro.problems) {
      if (discardedProblems.has(problem.id) || problem.disposition === "discarded") {
        continue;
      }
      for (const action of problem.suggested_actions) {
        if (discardedActions.has(action.id)) continue;
        const edit = actionEdits[action.id];
        if (!edit) continue;
        if (!edit.owner.trim() || !edit.due_date || !edit.success_criteria.trim()) {
          setError(t("publishFieldsRequired"));
          return;
        }
        actions.push({
          action_draft_id: action.id,
          owner: edit.owner.trim(),
          due_date: edit.due_date,
          success_criteria: edit.success_criteria.trim(),
        });
      }
    }

    if (actions.length === 0) {
      const extractedEmpty =
        retro.problems.length === 0 && !summaryHasItems(retro.analysis_summary);
      setError(extractedEmpty ? t("extractEmptyHint") : t("publishNeedActions"));
      return;
    }
    if (actions.length > 3) {
      setError(t("publishTooManyActions"));
      return;
    }

    const keptProblemCount = retro.problems.filter(
      (p) => !discardedProblems.has(p.id) && p.disposition !== "discarded",
    ).length;
    if (keptProblemCount > 5) {
      setError(t("publishTooManyProblems"));
      return;
    }

    setPublishing(true);
    try {
      const data = await publishRetro(retroId, {
        discarded_problem_ids: [...discardedProblems],
        discarded_action_draft_ids: [...discardedActions],
        actions,
      });
      setRetro(data);
      router.push("/actions/board");
    } catch (err) {
      if (redirectToLoginIfUnauthorized(err, router.replace)) return;
      setError(t("publishFailed"));
    } finally {
      setPublishing(false);
    }
  }

  if (error && !retro) {
    return (
      <div className="space-y-4">
        <Link href="/retros" className="text-sm font-semibold text-ink/50 hover:text-ink">
          {t("back")}
        </Link>
        <p className="text-sm font-semibold text-coral">{error}</p>
      </div>
    );
  }

  if (!retro) {
    return <p className="rf-lede">{t("loading")}</p>;
  }

  const summary = retro.analysis_summary;
  const failed = retro.status === "analysis_failed";
  const ready = retro.status === "ready_for_review";
  const published = retro.status === "published";
  const showRetryAnalyze =
    !published &&
    (failed ||
      retro.status === "analyzing" ||
      retro.status === "draft" ||
      (!ready && retro.problems.length === 0));

  const visibleProblems = retro.problems.filter(
    (p) => p.disposition !== "discarded" && !discardedProblems.has(p.id),
  );
  const extractionEmpty =
    ready && retro.problems.length === 0 && !summaryHasItems(summary);

  const typeMeta = TYPE_META[retro.type] ?? TYPE_META.sprint;
  const statusLabel = STATUS_KEYS.includes(retro.status as (typeof STATUS_KEYS)[number])
    ? tStatus(`status.${retro.status as (typeof STATUS_KEYS)[number]}`)
    : retro.status;

  return (
    <div className="space-y-5 pb-24">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <Link href="/retros" className="text-sm font-semibold text-ink/50 hover:text-ink">
            {t("back")}
          </Link>
          <h1 className="rf-h1 mt-2">{retro.title}</h1>
          <p className="mt-2 flex flex-wrap items-center gap-2 text-sm font-medium text-ink/45">
            <span className="rf-chip bg-sand text-ink">
              {typeMeta.emoji} {tType(typeMeta.labelKey)}
            </span>
            <span>{retro.review_date}</span>
            <span className="rf-chip bg-sand">{statusLabel}</span>
          </p>
        </div>
        {published ? (
          <Link href="/actions/board" className="rf-btn-primary px-4 py-2">
            {t("goActions")}
          </Link>
        ) : null}
      </div>

      {error ? <p className="text-sm font-semibold text-coral">{error}</p> : null}

      {failed ? (
        <div className="rf-card flex flex-wrap items-center justify-between gap-3 bg-[#fff1ed] p-4">
          <p className="text-sm font-medium text-coral">{t("analyzeFailedHint")}</p>
          <button
            type="button"
            disabled={analyzing}
            onClick={() => void onRetryAnalyze()}
            className="rf-btn-primary px-4 py-2"
          >
            {analyzing ? t("analyzing") : t("retryAnalyze")}
          </button>
        </div>
      ) : null}

      {showRetryAnalyze && !failed ? (
        <div className="rf-card flex flex-wrap items-center justify-between gap-3 bg-sand/50 p-4">
          <p className="text-sm text-ink/70">
            {retro.status === "analyzing" ? t("analyzingStuckHint") : t("noAnalysisYet")}
          </p>
          <button
            type="button"
            disabled={analyzing}
            onClick={() => void onRetryAnalyze()}
            className="rf-btn-primary px-4 py-2"
          >
            {analyzing ? t("analyzing") : t("retryAnalyze")}
          </button>
        </div>
      ) : null}

      {extractionEmpty ? (
        <div className="rf-card space-y-3 border-sun/40 bg-[#fff8ea] p-4">
          <p className="text-sm font-bold text-ink">{t("extractEmptyTitle")}</p>
          <p className="text-sm text-ink/70">{t("extractEmptyHint")}</p>
          <button
            type="button"
            disabled={analyzing || publishing}
            onClick={() => void onRetryAnalyze()}
            className="rf-btn-primary px-4 py-2"
          >
            {analyzing ? t("analyzing") : t("retryAnalyze")}
          </button>
        </div>
      ) : null}

      {summary && summaryHasItems(summary) ? (
        <section className="grid gap-3 sm:grid-cols-3">
          {summary.keep.length > 0 ? (
            <div className="rounded-3xl p-4" style={{ background: "#EDFAF5", border: "2px solid #3ECFA022" }}>
              <p className="text-xs font-extrabold text-[#2a9a74]">{t("keepHeading")}</p>
              <ul className="mt-2 space-y-1.5 text-sm font-medium text-ink">
                {summary.keep.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </div>
          ) : null}
          {summary.decisions.length > 0 ? (
            <div className="rounded-3xl p-4" style={{ background: "#EEF7FF", border: "2px solid #4AAFFF22" }}>
              <p className="text-xs font-extrabold text-[#2b7ec4]">{t("decisionsHeading")}</p>
              <ul className="mt-2 space-y-1.5 text-sm font-medium text-ink">
                {summary.decisions.map((item) => (
                  <li key={`${item.decision}-${item.reason}`}>{item.decision}</li>
                ))}
              </ul>
            </div>
          ) : null}
          {summary.risks.length > 0 ? (
            <div className="rounded-3xl p-4" style={{ background: "#FFF0EC", border: "2px solid #FF6B4A22" }}>
              <p className="text-xs font-extrabold text-coral">{t("risksHeading")}</p>
              <ul className="mt-2 space-y-1.5 text-sm font-medium text-ink">
                {summary.risks.map((item) => (
                  <li key={`${item.risk}-${item.suggestion}`}>{item.risk}</li>
                ))}
              </ul>
            </div>
          ) : null}
        </section>
      ) : null}

      {visibleProblems.length > 0 ? (
        <section className="space-y-3">
          <h2 className="text-sm font-extrabold text-ink">
            {t("problemsHeading")}
            <span className="ml-2 font-medium text-ink/35">{visibleProblems.length}</span>
          </h2>
          <ul className="space-y-3">
            {visibleProblems.map((problem, index) => {
              const visibleActions = problem.suggested_actions.filter(
                (a) => !discardedActions.has(a.id),
              );
              return (
                <li key={problem.id} className="rf-card space-y-3 p-4">
                  <div className="flex items-start gap-3">
                    <span className="flex size-7 shrink-0 items-center justify-center rounded-full bg-coral text-xs font-bold text-white">
                      {index + 1}
                    </span>
                    <div className="min-w-0 flex-1">
                      <p className="font-extrabold text-ink">{problem.title}</p>
                      <div className="mt-1.5 flex flex-wrap items-center gap-2 text-xs font-semibold">
                        {problem.cluster_title ? (
                          <span className="rf-chip bg-plum/15 text-plum">{problem.cluster_title}</span>
                        ) : (
                          <span className="rf-chip bg-sand text-ink/40">{t("clusterNone")}</span>
                        )}
                        {ready ? (
                          <button
                            type="button"
                            disabled={clusterBusy}
                            onClick={() => void openClusterEditor(problem.id)}
                            className="font-semibold text-coral hover:underline"
                          >
                            {t("clusterChange")}
                          </button>
                        ) : null}
                      </div>
                      {editingClusterFor === problem.id ? (
                        <div className="mt-2 space-y-2 rounded-2xl bg-sand/60 p-3 text-sm">
                          <ul className="max-h-40 space-y-1 overflow-y-auto">
                            {clusterOptions.map((c) => (
                              <li key={c.id}>
                                <button
                                  type="button"
                                  disabled={clusterBusy}
                                  onClick={() => void applyClusterLink(problem.id, c.id)}
                                  className="w-full rounded-xl px-2 py-1 text-left hover:bg-white disabled:opacity-60"
                                >
                                  {c.canonical_title}
                                  <span className="text-ink/40"> · {c.occurrence_count}</span>
                                </button>
                              </li>
                            ))}
                          </ul>
                          <div className="flex flex-wrap items-center gap-2">
                            <input
                              value={newClusterTitle}
                              onChange={(e) => setNewClusterTitle(e.target.value)}
                              placeholder={t("clusterNewPlaceholder")}
                              className="rf-input min-w-[12rem] flex-1"
                            />
                            <button
                              type="button"
                              disabled={clusterBusy}
                              onClick={() => void applyNewCluster(problem.id)}
                              className="rf-btn-primary px-3 py-1.5"
                            >
                              {t("clusterCreate")}
                            </button>
                            <button
                              type="button"
                              onClick={() => setEditingClusterFor(null)}
                              className="font-semibold text-ink/50 hover:text-ink"
                            >
                              {t("clusterCancel")}
                            </button>
                          </div>
                        </div>
                      ) : null}
                    </div>
                    {ready ? (
                      <button
                        type="button"
                        onClick={() =>
                          setDiscardedProblems((prev) => new Set(prev).add(problem.id))
                        }
                        className="shrink-0 text-sm font-semibold text-ink/30 hover:text-coral"
                        aria-label={t("removeProblem")}
                      >
                        ×
                      </button>
                    ) : null}
                  </div>

                  {visibleActions.length > 0 ? (
                    <ul className="space-y-2 pl-10">
                      {visibleActions.map((action) => {
                        const edit = actionEdits[action.id];
                        return (
                          <li key={action.id} className="rounded-2xl bg-sand/50 p-3">
                            <div className="flex items-start justify-between gap-3">
                              <p className="text-sm font-bold text-ink">{action.title}</p>
                              {ready ? (
                                <button
                                  type="button"
                                  onClick={() =>
                                    setDiscardedActions((prev) => new Set(prev).add(action.id))
                                  }
                                  className="shrink-0 text-sm font-semibold text-ink/30 hover:text-coral"
                                  aria-label={t("removeAction")}
                                >
                                  ×
                                </button>
                              ) : null}
                            </div>

                            {ready && edit ? (
                              <div className="mt-3 grid gap-2 sm:grid-cols-3">
                                <input
                                  value={edit.owner}
                                  onChange={(e) =>
                                    updateAction(action.id, { owner: e.target.value })
                                  }
                                  className="rf-input py-2"
                                  placeholder={t("owner")}
                                  aria-label={t("owner")}
                                />
                                <input
                                  type="date"
                                  value={edit.due_date}
                                  onChange={(e) =>
                                    updateAction(action.id, { due_date: e.target.value })
                                  }
                                  className="rf-input py-2"
                                  aria-label={t("dueDate")}
                                />
                                <input
                                  value={edit.success_criteria}
                                  onChange={(e) =>
                                    updateAction(action.id, {
                                      success_criteria: e.target.value,
                                    })
                                  }
                                  className="rf-input py-2 sm:col-span-1"
                                  placeholder={t("successCriteria")}
                                  aria-label={t("successCriteria")}
                                />
                              </div>
                            ) : action.suggested_success_criteria ? (
                              <p className="mt-1 text-xs font-medium text-ink/45">
                                {action.suggested_success_criteria}
                              </p>
                            ) : null}
                          </li>
                        );
                      })}
                    </ul>
                  ) : null}
                </li>
              );
            })}
          </ul>
        </section>
      ) : null}

      {ready ? (
        <div className="sticky bottom-0 z-10 -mx-6 border-t border-ink/8 bg-cream/95 px-6 py-4 backdrop-blur-sm lg:-mx-10 lg:px-10">
          <div className="mx-auto flex max-w-[960px] flex-wrap items-center gap-3">
            <button
              type="button"
              disabled={publishing || analyzing}
              onClick={() => void onPublish()}
              className="rf-btn-primary px-5 py-2.5"
            >
              {publishing ? t("publishing") : t("publish")}
            </button>
            <button
              type="button"
              disabled={publishing || analyzing}
              onClick={() => void onRetryAnalyze()}
              className="rf-btn-secondary px-5 py-2.5"
            >
              {analyzing ? t("analyzing") : t("retryAnalyze")}
            </button>
            <Link href="/retros" className="text-sm font-semibold text-ink/50 hover:text-ink">
              {t("saveForLater")}
            </Link>
            <p className="w-full text-xs font-medium text-ink/40">{t("publishHint")}</p>
          </div>
        </div>
      ) : null}
    </div>
  );
}
