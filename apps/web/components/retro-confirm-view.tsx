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

export function RetroConfirmView({ retroId }: RetroConfirmViewProps) {
  const t = useTranslations("retroConfirm");
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
      setError(t("publishNeedActions"));
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
        <Link href="/retros" className="text-sm text-zinc-600 hover:text-zinc-950">
          {t("back")}
        </Link>
        <p className="text-sm text-red-600">{error}</p>
      </div>
    );
  }

  if (!retro) {
    return <p className="text-sm text-zinc-500">{t("loading")}</p>;
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

  return (
    <div className="mx-auto max-w-3xl space-y-8">
      <div>
        <Link href="/retros" className="text-sm text-zinc-600 hover:text-zinc-950">
          {t("back")}
        </Link>
        <h1 className="mt-3 text-xl font-semibold tracking-tight text-zinc-950">
          {retro.title}
        </h1>
        <p className="mt-1 text-sm text-zinc-500">
          {retro.type} · {retro.review_date} · {retro.status}
        </p>
      </div>

      {error ? <p className="text-sm text-red-600">{error}</p> : null}

      {published ? (
        <div className="border-t border-zinc-200 pt-4">
          <Link
            href="/actions/board"
            className="text-sm font-medium text-zinc-950 underline-offset-4 hover:underline"
          >
            {t("goActions")}
          </Link>
        </div>
      ) : null}

      {failed ? (
        <div className="space-y-3 rounded-md border border-red-200 bg-red-50 p-4">
          <p className="text-sm text-red-700">
            {t("analyzeFailedHint")}
            {retro.analysis_error ? ` (${retro.analysis_error})` : ""}
          </p>
          <button
            type="button"
            disabled={analyzing}
            onClick={() => void onRetryAnalyze()}
            className="rounded-md bg-zinc-900 px-3 py-2 text-sm font-medium text-white hover:bg-zinc-800 disabled:opacity-60"
          >
            {analyzing ? t("analyzing") : t("retryAnalyze")}
          </button>
        </div>
      ) : null}

      {showRetryAnalyze && !failed ? (
        <div className="space-y-3 rounded-md border border-zinc-200 bg-zinc-50 p-4">
          <p className="text-sm text-zinc-600">
            {retro.status === "analyzing" ? t("analyzingStuckHint") : t("noAnalysisYet")}
          </p>
          <button
            type="button"
            disabled={analyzing}
            onClick={() => void onRetryAnalyze()}
            className="rounded-md bg-zinc-900 px-3 py-2 text-sm font-medium text-white hover:bg-zinc-800 disabled:opacity-60"
          >
            {analyzing ? t("analyzing") : t("retryAnalyze")}
          </button>
        </div>
      ) : null}

      {summary ? (
        <section className="space-y-4">
          <h2 className="text-sm font-medium text-zinc-900">{t("summaryHeading")}</h2>
          {summary.keep.length > 0 ? (
            <div>
              <h3 className="text-xs font-medium uppercase tracking-wide text-zinc-500">
                {t("keepHeading")}
              </h3>
              <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-zinc-800">
                {summary.keep.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </div>
          ) : null}
          {summary.decisions.length > 0 ? (
            <div>
              <h3 className="text-xs font-medium uppercase tracking-wide text-zinc-500">
                {t("decisionsHeading")}
              </h3>
              <ul className="mt-2 space-y-2 text-sm text-zinc-800">
                {summary.decisions.map((item) => (
                  <li key={`${item.decision}-${item.reason}`}>
                    <p className="font-medium">{item.decision}</p>
                    <p className="text-zinc-600">{item.reason}</p>
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
          {summary.risks.length > 0 ? (
            <div>
              <h3 className="text-xs font-medium uppercase tracking-wide text-zinc-500">
                {t("risksHeading")}
              </h3>
              <ul className="mt-2 space-y-2 text-sm text-zinc-800">
                {summary.risks.map((item) => (
                  <li key={`${item.risk}-${item.suggestion}`}>
                    <p className="font-medium">{item.risk}</p>
                    <p className="text-zinc-600">{item.suggestion}</p>
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
        </section>
      ) : null}

      {visibleProblems.length > 0 ? (
        <section className="space-y-4">
          <h2 className="text-sm font-medium text-zinc-900">{t("problemsHeading")}</h2>
          <ul className="space-y-6">
            {visibleProblems.map((problem, index) => {
              const visibleActions = problem.suggested_actions.filter(
                (a) => !discardedActions.has(a.id),
              );
              return (
                <li key={problem.id} className="space-y-3 border-t border-zinc-200 pt-4">
                  <div className="flex items-start justify-between gap-4">
                    <div>
                      <p className="font-medium text-zinc-950">
                        {index + 1}. {problem.title}
                      </p>
                      <p className="mt-1 text-sm text-zinc-500">
                        {problem.category} · {problem.severity}
                      </p>
                      <p className="mt-2 text-sm text-zinc-700">
                        {problem.normalized_statement}
                      </p>
                      <p className="mt-2 text-sm text-zinc-600">
                        <span className="font-medium text-zinc-800">{t("clusterLabel")}: </span>
                        {problem.cluster_title ?? t("clusterNone")}
                        {ready ? (
                          <>
                            {" · "}
                            <button
                              type="button"
                              disabled={clusterBusy}
                              onClick={() => void openClusterEditor(problem.id)}
                              className="text-zinc-900 underline-offset-2 hover:underline"
                            >
                              {t("clusterChange")}
                            </button>
                          </>
                        ) : null}
                      </p>
                      {editingClusterFor === problem.id ? (
                        <div className="mt-2 space-y-2 rounded-md border border-zinc-200 bg-zinc-50 p-3 text-sm">
                          <ul className="max-h-40 space-y-1 overflow-y-auto">
                            {clusterOptions.map((c) => (
                              <li key={c.id}>
                                <button
                                  type="button"
                                  disabled={clusterBusy}
                                  onClick={() => void applyClusterLink(problem.id, c.id)}
                                  className="w-full rounded px-2 py-1 text-left hover:bg-white disabled:opacity-60"
                                >
                                  {c.canonical_title}
                                  <span className="text-zinc-500">
                                    {" "}
                                    · {c.occurrence_count}
                                  </span>
                                </button>
                              </li>
                            ))}
                          </ul>
                          <div className="flex flex-wrap items-center gap-2">
                            <input
                              value={newClusterTitle}
                              onChange={(e) => setNewClusterTitle(e.target.value)}
                              placeholder={t("clusterNewPlaceholder")}
                              className="min-w-[12rem] flex-1 rounded-md border border-zinc-300 bg-white px-2 py-1.5 outline-none focus:border-zinc-900"
                            />
                            <button
                              type="button"
                              disabled={clusterBusy}
                              onClick={() => void applyNewCluster(problem.id)}
                              className="rounded-md bg-zinc-900 px-3 py-1.5 text-white hover:bg-zinc-800 disabled:opacity-60"
                            >
                              {t("clusterCreate")}
                            </button>
                            <button
                              type="button"
                              onClick={() => setEditingClusterFor(null)}
                              className="text-zinc-600 hover:text-zinc-950"
                            >
                              {t("clusterCancel")}
                            </button>
                          </div>
                        </div>
                      ) : null}
                      <blockquote className="mt-2 border-l-2 border-zinc-300 pl-3 text-sm text-zinc-600">
                        {problem.source_quote}
                      </blockquote>
                    </div>
                    {ready ? (
                      <button
                        type="button"
                        onClick={() =>
                          setDiscardedProblems((prev) => new Set(prev).add(problem.id))
                        }
                        className="shrink-0 text-sm text-zinc-500 hover:text-red-600"
                      >
                        {t("removeProblem")}
                      </button>
                    ) : null}
                  </div>

                  {visibleActions.length > 0 ? (
                    <div className="space-y-3">
                      <h3 className="text-xs font-medium uppercase tracking-wide text-zinc-500">
                        {t("actionsHeading")}
                      </h3>
                      <ul className="space-y-4">
                        {visibleActions.map((action) => {
                          const edit = actionEdits[action.id];
                          return (
                            <li
                              key={action.id}
                              className="space-y-3 rounded-md border border-zinc-200 bg-zinc-50 p-3 text-sm"
                            >
                              <div className="flex items-start justify-between gap-3">
                                <div>
                                  <p className="font-medium text-zinc-900">{action.title}</p>
                                  <p className="mt-1 text-zinc-700">{action.description}</p>
                                </div>
                                {ready ? (
                                  <button
                                    type="button"
                                    onClick={() =>
                                      setDiscardedActions((prev) =>
                                        new Set(prev).add(action.id),
                                      )
                                    }
                                    className="shrink-0 text-sm text-zinc-500 hover:text-red-600"
                                  >
                                    {t("removeAction")}
                                  </button>
                                ) : null}
                              </div>

                              {ready && edit ? (
                                <div className="grid gap-3 sm:grid-cols-3">
                                  <label className="block space-y-1">
                                    <span className="text-xs text-zinc-500">{t("owner")}</span>
                                    <input
                                      value={edit.owner}
                                      onChange={(e) =>
                                        updateAction(action.id, { owner: e.target.value })
                                      }
                                      className="w-full rounded-md border border-zinc-300 bg-white px-2 py-1.5 text-sm outline-none focus:border-zinc-900"
                                      placeholder={t("ownerPlaceholder")}
                                    />
                                  </label>
                                  <label className="block space-y-1">
                                    <span className="text-xs text-zinc-500">{t("dueDate")}</span>
                                    <input
                                      type="date"
                                      value={edit.due_date}
                                      onChange={(e) =>
                                        updateAction(action.id, { due_date: e.target.value })
                                      }
                                      className="w-full rounded-md border border-zinc-300 bg-white px-2 py-1.5 text-sm outline-none focus:border-zinc-900"
                                    />
                                  </label>
                                  <label className="block space-y-1 sm:col-span-3">
                                    <span className="text-xs text-zinc-500">
                                      {t("successCriteria")}
                                    </span>
                                    <input
                                      value={edit.success_criteria}
                                      onChange={(e) =>
                                        updateAction(action.id, {
                                          success_criteria: e.target.value,
                                        })
                                      }
                                      className="w-full rounded-md border border-zinc-300 bg-white px-2 py-1.5 text-sm outline-none focus:border-zinc-900"
                                    />
                                  </label>
                                </div>
                              ) : (
                                <p className="text-zinc-600">
                                  <span className="font-medium">{t("successCriteria")}: </span>
                                  {action.suggested_success_criteria}
                                </p>
                              )}
                            </li>
                          );
                        })}
                      </ul>
                    </div>
                  ) : null}
                </li>
              );
            })}
          </ul>
        </section>
      ) : null}

      {ready ? (
        <div className="flex flex-wrap items-center gap-3 border-t border-zinc-200 pt-6">
          <button
            type="button"
            disabled={publishing || analyzing}
            onClick={() => void onPublish()}
            className="rounded-md bg-zinc-900 px-4 py-2.5 text-sm font-medium text-white hover:bg-zinc-800 disabled:opacity-60"
          >
            {publishing ? t("publishing") : t("publish")}
          </button>
          <button
            type="button"
            disabled={publishing || analyzing}
            onClick={() => void onRetryAnalyze()}
            className="rounded-md border border-zinc-300 bg-white px-4 py-2.5 text-sm font-medium text-zinc-800 hover:bg-zinc-50 disabled:opacity-60"
          >
            {analyzing ? t("analyzing") : t("retryAnalyze")}
          </button>
          <Link href="/retros" className="text-sm text-zinc-600 hover:text-zinc-950">
            {t("saveForLater")}
          </Link>
        </div>
      ) : null}
    </div>
  );
}
