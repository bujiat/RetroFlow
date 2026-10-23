"use client";

import { useLocale, useTranslations } from "next-intl";
import { useEffect, useState } from "react";

import { Link, useRouter } from "@/i18n/navigation";
import { listAgentRuns } from "@/lib/api/agent";
import { failedRequestMessage, redirectToLoginIfUnauthorized } from "@/lib/api/client";
import type { AgentRunSummary } from "@/types";

export function AgentRunsView() {
  const t = useTranslations("agentRuns");
  const tCommon = useTranslations("common");
  const locale = useLocale();
  const router = useRouter();
  const [items, setItems] = useState<AgentRunSummary[] | null>(null);
  const [limited, setLimited] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const data = await listAgentRuns();
        if (cancelled) return;
        setItems(data.items);
        setLimited(data.limited);
        setError(null);
      } catch (err) {
        if (cancelled) return;
        if (redirectToLoginIfUnauthorized(err, router.replace)) return;
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
  }, [router, t, tCommon]);

  return (
    <div className="mx-auto flex w-full max-w-3xl flex-col gap-6">
      <div>
        <Link href="/assistant" className="text-xs font-bold text-plum underline-offset-2 hover:underline">
          {t("backAssistant")}
        </Link>
        <h1 className="rf-h1 mt-2 text-[1.75rem]">{t("title")}</h1>
        <p className="rf-lede">{t("lede")}</p>
      </div>

      {error ? (
        <p role="alert" className="text-sm font-semibold text-coral">
          {error}
        </p>
      ) : null}

      {items === null && !error ? <p className="rf-lede">{t("loading")}</p> : null}

      {items && items.length === 0 ? (
        <div className="rf-card space-y-3 p-5">
          <p className="text-sm text-ink/70">{t("empty")}</p>
          <Link href="/assistant" className="text-sm font-bold text-plum underline-offset-2 hover:underline">
            {t("openAssistant")}
          </Link>
        </div>
      ) : null}

      {items && items.length > 0 ? (
        <ul className="space-y-3">
          {items.map((item) => (
            <li key={item.id}>
              <Link href={`/assistant/runs/${item.id}`} className="rf-card block space-y-2 p-4">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <span className={statusClass(item.status)}>{statusText(item.status, t)}</span>
                  <time className="text-xs font-medium text-ink/40" dateTime={item.created_at}>
                    {formatWhen(item.created_at, locale)}
                  </time>
                </div>
                <p className="line-clamp-2 text-sm font-bold text-ink">
                  {item.question || "—"}
                </p>
                <p className="text-xs font-medium text-ink/50">
                  {formatDuration(item.duration_ms, t)}
                  {" · "}
                  {t("promptTokens")} {item.prompt_tokens}
                  {" · "}
                  {t("completionTokens")} {item.completion_tokens}
                </p>
              </Link>
            </li>
          ))}
        </ul>
      ) : null}

      {limited ? <p className="text-xs font-medium text-ink/40">{t("limited")}</p> : null}
    </div>
  );
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

function formatDuration(ms: number, t: (key: string, values: { ms: number } | { seconds: string }) => string): string {
  if (ms < 1000) return t("durationMs", { ms });
  return t("durationSeconds", { seconds: (ms / 1000).toFixed(1) });
}

function formatWhen(value: string, locale: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString(locale);
}
