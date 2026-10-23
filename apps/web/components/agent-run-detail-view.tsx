"use client";

import { useLocale, useTranslations } from "next-intl";
import { useEffect, useState } from "react";

import { Link, useRouter } from "@/i18n/navigation";
import { getAgentRun } from "@/lib/api/agent";
import { ApiError, failedRequestMessage, redirectToLoginIfUnauthorized } from "@/lib/api/client";
import type { AgentRunDetail, AgentStepRecord } from "@/types";

export function AgentRunDetailView({ runId }: { runId: string }) {
  const t = useTranslations("agentRuns");
  const tCommon = useTranslations("common");
  const locale = useLocale();
  const router = useRouter();
  const [run, setRun] = useState<AgentRunDetail | null>(null);
  const [missing, setMissing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [openSteps, setOpenSteps] = useState<Record<number, boolean>>({});

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const data = await getAgentRun(runId);
        if (cancelled) return;
        setRun(data);
        setMissing(false);
        setError(null);
      } catch (err) {
        if (cancelled) return;
        if (redirectToLoginIfUnauthorized(err, router.replace)) return;
        if (err instanceof ApiError && err.code === "run_not_found") {
          setMissing(true);
          setRun(null);
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
    void load();
    return () => {
      cancelled = true;
    };
  }, [runId, router, t, tCommon]);

  return (
    <div className="mx-auto flex w-full max-w-3xl flex-col gap-6">
      <div>
        <Link
          href="/assistant/runs"
          className="text-xs font-bold text-plum underline-offset-2 hover:underline"
        >
          {t("backList")}
        </Link>
        <h1 className="rf-h1 mt-2 text-[1.75rem]">{t("title")}</h1>
      </div>

      {error ? (
        <p role="alert" className="text-sm font-semibold text-coral">
          {error}
        </p>
      ) : null}
      {missing ? <p className="rf-lede">{t("notFound")}</p> : null}
      {run === null && !error && !missing ? <p className="rf-lede">{t("loading")}</p> : null}

      {run ? (
        <>
          <section className="rf-card space-y-3 p-5">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <span className={statusClass(run.status)}>{statusText(run.status, t)}</span>
              <time className="text-xs font-medium text-ink/40" dateTime={run.created_at}>
                {formatWhen(run.created_at, locale)}
              </time>
            </div>
            <div>
              <h2 className="text-xs font-bold tracking-wide text-ink/40 uppercase">{t("question")}</h2>
              <p className="mt-1 text-sm leading-relaxed text-ink">{run.question || "—"}</p>
            </div>
            <p className="text-xs font-medium text-ink/50">
              {formatDuration(run.duration_ms, t)}
              {" · "}
              {t("promptTokens")} {run.prompt_tokens}
              {" · "}
              {t("completionTokens")} {run.completion_tokens}
            </p>
            {run.output ? (
              <div className="border-t border-ink/8 pt-3">
                <h2 className="text-xs font-bold tracking-wide text-ink/40 uppercase">{t("output")}</h2>
                <p className="mt-1 text-sm leading-relaxed whitespace-pre-wrap text-ink">{run.output}</p>
              </div>
            ) : null}
          </section>

          <section className="space-y-2" aria-label={t("steps")}>
            <h2 className="text-xs font-bold tracking-wide text-ink/40 uppercase">{t("steps")}</h2>
            {run.steps.length === 0 ? <p className="rf-lede">{t("noSteps")}</p> : null}
            <ol className="space-y-2">
              {run.steps.map((step) => (
                <li key={step.step_index}>
                  <StepCard
                    step={step}
                    open={openSteps[step.step_index] === true}
                    onToggle={() =>
                      setOpenSteps((current) => ({
                        ...current,
                        [step.step_index]: !current[step.step_index],
                      }))
                    }
                    title={stepTitle(step, t)}
                    duration={formatDuration(step.duration_ms, t)}
                    promptLabel={t("promptTokens")}
                    completionLabel={t("completionTokens")}
                    argumentsLabel={t("arguments")}
                    summaryLabel={t("summary")}
                    errorLabel={t("stepError")}
                    expandLabel={t("expand")}
                    collapseLabel={t("collapse")}
                  />
                </li>
              ))}
            </ol>
          </section>
        </>
      ) : null}
    </div>
  );
}

function StepCard({
  step,
  open,
  onToggle,
  title,
  duration,
  promptLabel,
  completionLabel,
  argumentsLabel,
  summaryLabel,
  errorLabel,
  expandLabel,
  collapseLabel,
}: {
  step: AgentStepRecord;
  open: boolean;
  onToggle: () => void;
  title: string;
  duration: string;
  promptLabel: string;
  completionLabel: string;
  argumentsLabel: string;
  summaryLabel: string;
  errorLabel: string;
  expandLabel: string;
  collapseLabel: string;
}) {
  const hasBody = step.arguments !== null || Boolean(step.result_summary);
  return (
    <div className="rf-card">
      <button
        type="button"
        aria-expanded={open}
        onClick={onToggle}
        className="flex w-full items-start justify-between gap-3 px-4 py-3 text-left"
      >
        <span className="min-w-0">
          <span className="block text-sm font-bold text-ink">
            {step.step_index}. {title}
          </span>
          <span className="mt-1 block text-xs font-medium text-ink/50">
            {duration}
            {" · "}
            {promptLabel} {step.prompt_tokens}
            {" · "}
            {completionLabel} {step.completion_tokens}
          </span>
        </span>
        {hasBody ? (
          <span className="shrink-0 text-xs font-bold text-plum">{open ? collapseLabel : expandLabel}</span>
        ) : null}
      </button>
      {step.error ? (
        <p className="px-4 pb-3 text-sm font-semibold text-coral">
          <span className="block text-xs tracking-wide uppercase">{errorLabel}</span>
          {step.error}
        </p>
      ) : null}
      {open && hasBody ? (
        <div className="space-y-2 border-t border-ink/8 px-4 py-3">
          {step.arguments ? (
            <div>
              <p className="text-xs font-bold text-ink/40">{argumentsLabel}</p>
              <pre className="mt-1 overflow-x-auto text-xs leading-relaxed whitespace-pre-wrap text-ink/70">
                {JSON.stringify(step.arguments, null, 2)}
              </pre>
            </div>
          ) : null}
          {step.result_summary ? (
            <div>
              <p className="text-xs font-bold text-ink/40">{summaryLabel}</p>
              <p className="mt-1 text-xs leading-relaxed whitespace-pre-wrap text-ink/70">
                {step.result_summary}
              </p>
            </div>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

function stepTitle(step: AgentStepRecord, t: (key: string) => string): string {
  if (step.step_type === "tool") {
    return step.tool_name ? `${t("stepTool")} · ${step.tool_name}` : t("stepTool");
  }
  return t("stepLlm");
}

function statusText(status: string, t: (key: string) => string): string {
  if (status === "running") return t("statusRunning");
  if (status === "answered") return t("statusAnswered");
  if (status === "insufficient_evidence") return t("statusInsufficient");
  if (status === "max_steps") return t("statusMaxSteps");
  if (status === "tool_failures") return t("statusToolFailures");
  if (status === "error") return t("statusError");
  if (status === "invalid_answer") return t("statusInvalid");
  return status;
}

function statusClass(status: string): string {
  if (status === "answered") return "rf-chip bg-mint/20 text-[#2a9a74]";
  if (status === "error" || status === "tool_failures" || status === "invalid_answer") {
    return "rf-chip bg-coral/15 text-coral";
  }
  return "rf-chip bg-sun/20 text-[#c48410]";
}

function formatDuration(
  ms: number,
  t: (key: string, values: { ms: number } | { seconds: string }) => string,
): string {
  if (ms < 1000) return t("durationMs", { ms });
  return t("durationSeconds", { seconds: (ms / 1000).toFixed(1) });
}

function formatWhen(value: string, locale: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString(locale);
}
