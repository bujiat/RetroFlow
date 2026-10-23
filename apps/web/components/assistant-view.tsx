"use client";

import { useLocale, useTranslations } from "next-intl";
import { useEffect, useRef, useState } from "react";

import { Link, useRouter } from "@/i18n/navigation";
import { applyAgentEvent, emptyWorkbench, type PendingCard, type ToolStep, type WorkbenchState } from "@/lib/agent-run";
import { confirmOperation, rejectOperation, streamAgentChat } from "@/lib/api/agent";
import { ApiError, failedRequestMessage, isAbortError, redirectToLoginIfUnauthorized } from "@/lib/api/client";
import type { AgentAnswerStatus, AssistantCitation } from "@/types";

const EXAMPLE_KEYS = ["exDeploy", "exEvidence", "exRecurring"] as const;

const TOOL_LABELS: Record<string, string> = {
  search_retro_content: "toolSearch",
  find_similar_problems: "toolSimilar",
  list_actions: "toolListActions",
  get_action_history: "toolHistory",
  get_trends: "toolTrends",
  read_github_pr: "toolGithub",
  propose_action: "toolProposeAction",
  propose_status_change: "toolProposeStatus",
};

export function AssistantView() {
  const t = useTranslations("assistant");
  const tCommon = useTranslations("common");
  const locale = useLocale();
  const router = useRouter();
  const abortRef = useRef<AbortController | null>(null);
  const busyRef = useRef<string | null>(null);
  const [question, setQuestion] = useState("");
  const [asked, setAsked] = useState<string | null>(null);
  const [streaming, setStreaming] = useState(false);
  const [requestError, setRequestError] = useState<string | null>(null);
  const [run, setRun] = useState<WorkbenchState>(emptyWorkbench);
  const [openSteps, setOpenSteps] = useState<Record<string, boolean>>({});
  const [busyId, setBusyId] = useState<string | null>(null);

  useEffect(() => {
    return () => abortRef.current?.abort();
  }, []);

  async function ask(nextQuestion?: string) {
    const q = (nextQuestion ?? question).trim();
    if (q.length < 2 || streaming) return;
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    setQuestion(q);
    setAsked(q);
    setStreaming(true);
    setRequestError(null);
    setRun(emptyWorkbench());
    setOpenSteps({});
    try {
      await streamAgentChat(
        q,
        (event) => setRun((current) => applyAgentEvent(current, event)),
        controller.signal,
      );
      setRun((current) =>
        current.answer || current.errorCode
          ? current
          : { ...current, errorCode: "agent_chat_failed" },
      );
    } catch (err) {
      if (isAbortError(err)) return;
      if (redirectToLoginIfUnauthorized(err, router.replace)) return;
      setRequestError(
        failedRequestMessage(err, {
          network: tCommon("networkError"),
          fallback: t("askFailed"),
        }),
      );
    } finally {
      if (abortRef.current === controller) setStreaming(false);
    }
  }

  async function confirm(card: PendingCard) {
    if (card.locked || card.resolution !== "open" || busyRef.current) return;
    busyRef.current = card.id;
    setBusyId(`${card.id}:confirm`);
    try {
      const result = await confirmOperation(card.id);
      patchPending(card.id, {
        resolution: "approved",
        actionTitle: result.action.title,
        notice: null,
        locked: true,
      });
    } catch (err) {
      if (redirectToLoginIfUnauthorized(err, router.replace)) return;
      patchPending(card.id, failurePatch(err, t("confirmFailed"), t));
    } finally {
      busyRef.current = null;
      setBusyId(null);
    }
  }

  async function reject(card: PendingCard) {
    if (card.locked || card.resolution !== "open" || busyRef.current) return;
    busyRef.current = card.id;
    setBusyId(`${card.id}:reject`);
    try {
      await rejectOperation(card.id);
      patchPending(card.id, { resolution: "rejected", notice: null, locked: true });
    } catch (err) {
      if (redirectToLoginIfUnauthorized(err, router.replace)) return;
      patchPending(card.id, failurePatch(err, t("rejectFailed"), t));
    } finally {
      busyRef.current = null;
      setBusyId(null);
    }
  }

  function patchPending(id: string, patch: Partial<PendingCard>) {
    setRun((current) => ({
      ...current,
      pendings: current.pendings.map((item) => (item.id === id ? { ...item, ...patch } : item)),
    }));
  }

  const streamError = run.errorCode ? streamErrorText(run.errorCode, t) : null;

  return (
    <div className="flex min-h-[calc(100vh-6rem)] flex-col">
      <div className="flex items-center gap-3">
        <div className="flex size-12 items-center justify-center rounded-2xl bg-plum/15 text-2xl">
          🤖
        </div>
        <div>
          <div className="flex items-center gap-2">
            <h1 className="rf-h1 text-[1.75rem]">{t("title")}</h1>
            <span className="size-2 rounded-full bg-mint" aria-hidden />
          </div>
          <p className="rf-lede">{t("lede")}</p>
          <Link
            href="/assistant/runs"
            className="mt-1 inline-block text-xs font-bold text-plum underline-offset-2 hover:underline"
          >
            {t("runsLink")}
          </Link>
        </div>
      </div>

      <div className="mt-8 flex flex-1 flex-col gap-4">
        {asked ? (
          <div className="flex justify-end">
            <p className="max-w-[80%] rounded-3xl rounded-br-md bg-coral px-4 py-3 text-sm font-semibold text-white">
              {asked}
            </p>
          </div>
        ) : null}

        {streaming && run.steps.length === 0 && !run.answer ? (
          <div className="flex items-start gap-3">
            <span className="flex size-9 items-center justify-center rounded-full bg-plum/15">🤖</span>
            <p className="rf-card px-4 py-3 text-sm text-ink/50">{t("asking")}</p>
          </div>
        ) : null}

        {run.steps.length > 0 ? (
          <section className="rf-card space-y-2 p-4" aria-label={t("stepsHeading")}>
            <h2 className="text-xs font-bold tracking-wide text-ink/40 uppercase">{t("stepsHeading")}</h2>
            <ol className="space-y-2">
              {run.steps.map((step, index) => (
                <li key={step.key}>
                  <ToolCard
                    step={step}
                    index={index}
                    open={openSteps[step.key] === true}
                    label={toolLabel(step.name, t)}
                    onToggle={() =>
                      setOpenSteps((current) => ({ ...current, [step.key]: !current[step.key] }))
                    }
                    runningLabel={t("toolRunning")}
                    okLabel={t("toolOk")}
                    failedLabel={t("toolFailed")}
                    argumentsLabel={t("argumentsLabel")}
                    summaryLabel={t("summaryLabel")}
                    expandLabel={t("expandStep")}
                    collapseLabel={t("collapseStep")}
                  />
                </li>
              ))}
            </ol>
          </section>
        ) : null}

        {run.pendings.map((card) => (
          <PendingOperationCard
            key={card.id}
            card={card}
            busy={busyId !== null}
            title={toolLabel(card.toolName, t)}
            heading={t("pendingHeading")}
            expiresLabel={t("expires", { time: formatExpiry(card.expiresAt, locale) })}
            confirmLabel={busyId === `${card.id}:confirm` ? t("confirming") : t("confirm")}
            rejectLabel={busyId === `${card.id}:reject` ? t("rejecting") : t("reject")}
            confirmedLabel={
              card.actionTitle
                ? t("createdAction", { title: card.actionTitle })
                : t("confirmed")
            }
            rejectedLabel={t("rejectedDone")}
            openActionLabel={t("openAction")}
            onConfirm={() => void confirm(card)}
            onReject={() => void reject(card)}
          />
        ))}

        {requestError || streamError ? (
          <p role="alert" className="text-sm font-semibold text-coral">
            {requestError ?? streamError}
          </p>
        ) : null}

        {run.answer ? (
          <div className="flex items-start gap-3">
            <span className="flex size-9 shrink-0 items-center justify-center rounded-full bg-plum/15">
              🤖
            </span>
            <div className="rf-card min-w-0 flex-1 space-y-4 p-5">
              <div className="flex items-center gap-2">
                <h2 className="text-sm font-bold text-ink">{t("answerHeading")}</h2>
                <span className={statusClass(run.answer.status)}>{statusLabel(run.answer.status, t)}</span>
              </div>
              <p className="whitespace-pre-wrap text-sm leading-relaxed text-ink">{run.answer.answer}</p>
              {run.answer.citations.length > 0 ? (
                <CitationList
                  citations={run.answer.citations}
                  heading={t("citationsHeading")}
                  openLabel={t("openSource")}
                />
              ) : null}
            </div>
          </div>
        ) : null}
      </div>

      <div className="sticky bottom-0 mt-8 space-y-3 bg-cream/90 py-4 backdrop-blur-sm">
        <div className="flex flex-wrap gap-2">
          {EXAMPLE_KEYS.map((key) => (
            <button
              key={key}
              type="button"
              disabled={streaming}
              onClick={() => void ask(t(`examples.${key}`))}
              className="rf-btn-secondary px-3 py-1.5 text-xs disabled:opacity-50"
            >
              {t(`examples.${key}`)}
            </button>
          ))}
        </div>
        <form
          className="rf-card flex items-end gap-2 p-3"
          onSubmit={(e) => {
            e.preventDefault();
            void ask();
          }}
        >
          <label className="sr-only" htmlFor="assistant-q">
            {t("questionLabel")}
          </label>
          <textarea
            id="assistant-q"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            rows={2}
            placeholder={t("placeholder")}
            className="rf-input min-h-[2.75rem] resize-none border-0 bg-transparent py-2"
          />
          <button
            type="submit"
            disabled={streaming || question.trim().length < 2}
            className="rf-btn-primary shrink-0 px-5 py-2"
          >
            {streaming ? t("asking") : t("ask")}
          </button>
        </form>
      </div>
    </div>
  );
}

function ToolCard({
  step,
  index,
  open,
  label,
  onToggle,
  runningLabel,
  okLabel,
  failedLabel,
  argumentsLabel,
  summaryLabel,
  expandLabel,
  collapseLabel,
}: {
  step: ToolStep;
  index: number;
  open: boolean;
  label: string;
  onToggle: () => void;
  runningLabel: string;
  okLabel: string;
  failedLabel: string;
  argumentsLabel: string;
  summaryLabel: string;
  expandLabel: string;
  collapseLabel: string;
}) {
  const status = step.ok === null ? runningLabel : step.ok ? okLabel : failedLabel;
  const preview = step.summary ? step.summary.slice(0, 80) : "";
  return (
    <div className="rounded-2xl bg-sand/60">
      <button
        type="button"
        aria-expanded={open}
        onClick={onToggle}
        className="flex w-full items-start justify-between gap-3 px-3 py-2 text-left"
      >
        <span className="min-w-0">
          <span className="block text-sm font-bold text-ink">
            {index + 1}. {label}
          </span>
          {!open && preview ? (
            <span className="mt-1 block truncate text-xs text-ink/50">{preview}</span>
          ) : null}
        </span>
        <span className="flex shrink-0 items-center gap-2">
          <span className={step.ok === false ? "rf-chip bg-coral/15 text-coral" : "rf-chip bg-white text-ink/60"}>
            {status}
          </span>
          <span className="text-xs font-bold text-plum">{open ? collapseLabel : expandLabel}</span>
        </span>
      </button>
      {open ? (
        <div className="space-y-2 border-t border-ink/8 px-3 py-2">
          <div>
            <p className="text-xs font-bold text-ink/40">{argumentsLabel}</p>
            <pre className="mt-1 overflow-x-auto text-xs leading-relaxed whitespace-pre-wrap text-ink/70">
              {JSON.stringify(step.arguments, null, 2)}
            </pre>
          </div>
          {step.summary ? (
            <div>
              <p className="text-xs font-bold text-ink/40">{summaryLabel}</p>
              <p className="mt-1 text-xs leading-relaxed whitespace-pre-wrap text-ink/70">{step.summary}</p>
            </div>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

function PendingOperationCard({
  card,
  busy,
  title,
  heading,
  expiresLabel,
  confirmLabel,
  rejectLabel,
  confirmedLabel,
  rejectedLabel,
  openActionLabel,
  onConfirm,
  onReject,
}: {
  card: PendingCard;
  busy: boolean;
  title: string;
  heading: string;
  expiresLabel: string;
  confirmLabel: string;
  rejectLabel: string;
  confirmedLabel: string;
  rejectedLabel: string;
  openActionLabel: string;
  onConfirm: () => void;
  onReject: () => void;
}) {
  const closed = card.resolution !== "open" || card.locked;
  return (
    <section className="rf-card space-y-3 border-coral/30 p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-xs font-bold tracking-wide text-coral uppercase">{heading}</h2>
        <span className="text-xs font-medium text-ink/40">{expiresLabel}</span>
      </div>
      <p className="text-sm font-bold text-ink">{title}</p>
      <p className="text-sm leading-relaxed text-ink/70">{card.summary}</p>
      {card.resolution === "approved" ? (
        <div className="space-y-2">
          <p className="text-sm font-bold text-[#2a9a74]">{confirmedLabel}</p>
          <Link href="/actions/board" className="text-xs font-bold text-plum underline-offset-2 hover:underline">
            {openActionLabel}
          </Link>
        </div>
      ) : null}
      {card.resolution === "rejected" ? (
        <p className="text-sm font-bold text-ink/50">{rejectedLabel}</p>
      ) : null}
      {card.notice ? (
        <p role="alert" className="text-sm font-semibold text-coral">
          {card.notice}
        </p>
      ) : null}
      {card.resolution === "open" ? (
        <div className="flex gap-2">
          <button type="button" disabled={closed || busy} onClick={onConfirm} className="rf-btn-primary px-4 py-2 text-sm">
            {confirmLabel}
          </button>
          <button
            type="button"
            disabled={closed || busy}
            onClick={onReject}
            className="rf-btn-secondary px-4 py-2 text-sm disabled:opacity-50"
          >
            {rejectLabel}
          </button>
        </div>
      ) : null}
    </section>
  );
}

function CitationList({
  citations,
  heading,
  openLabel,
}: {
  citations: AssistantCitation[];
  heading: string;
  openLabel: string;
}) {
  return (
    <div className="space-y-2 border-t border-ink/8 pt-4">
      <h3 className="text-xs font-bold tracking-wide text-ink/40 uppercase">{heading}</h3>
      <ul className="space-y-2">
        {citations.map((citation) => (
          <li key={citation.id} className="rounded-2xl bg-sand/60 px-3 py-2 text-sm">
            <div className="flex flex-wrap items-baseline justify-between gap-2">
              <span className="font-bold text-ink">{citation.title}</span>
              <span className="text-xs font-medium text-ink/40">{citation.source_type}</span>
            </div>
            <p className="mt-1 text-xs leading-relaxed text-ink/60">{citation.excerpt}</p>
            <SourceLink citation={citation} label={openLabel} />
          </li>
        ))}
      </ul>
    </div>
  );
}

function SourceLink({ citation, label }: { citation: AssistantCitation; label: string }) {
  const className = "mt-2 inline-block text-xs font-bold text-plum underline-offset-2 hover:underline";
  if (citation.source_type === "action") {
    return (
      <Link href="/actions/board" className={className}>
        {label}
      </Link>
    );
  }
  if (citation.source_type === "cluster") {
    return (
      <Link href="/trends" className={className}>
        {label}
      </Link>
    );
  }
  if (
    citation.source_type === "pull_request" &&
    citation.href_hint?.startsWith("https://github.com/")
  ) {
    return (
      <a href={citation.href_hint} className={className} target="_blank" rel="noreferrer">
        {label}
      </a>
    );
  }
  if (citation.retro_id && (citation.source_type === "chunk" || citation.source_type === "problem")) {
    return (
      <Link href={`/retro/${citation.retro_id}/confirm`} className={className}>
        {label}
      </Link>
    );
  }
  return null;
}

function toolLabel(name: string, t: (key: string) => string): string {
  const key = TOOL_LABELS[name];
  return key ? t(key) : name;
}

function statusLabel(status: AgentAnswerStatus, t: (key: string) => string): string {
  if (status === "answered") return t("statusAnswered");
  if (status === "max_steps") return t("statusMaxSteps");
  if (status === "tool_failures") return t("statusToolFailures");
  return t("statusInsufficient");
}

function statusClass(status: string): string {
  if (status === "answered") return "rf-chip bg-mint/20 text-[#2a9a74]";
  if (status === "tool_failures") return "rf-chip bg-coral/15 text-coral";
  return "rf-chip bg-sun/20 text-[#c48410]";
}

function streamErrorText(code: string, t: (key: string) => string): string {
  if (code === "llm_timeout") return t("errorLlmTimeout");
  if (code === "assistant_schema_invalid") return t("errorSchema");
  return t("askFailed");
}

function failurePatch(
  err: unknown,
  fallback: string,
  t: (key: string) => string,
): Partial<PendingCard> {
  const code = err instanceof ApiError ? err.code : null;
  if (code === "operation_expired") {
    return { notice: t("operationExpired"), locked: true };
  }
  if (code === "operation_already_resolved") {
    return { notice: t("operationResolved"), locked: true };
  }
  if (code === "operation_not_found") {
    return { notice: t("operationMissing"), locked: true };
  }
  return { notice: fallback };
}

function formatExpiry(value: string, locale: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString(locale);
}
