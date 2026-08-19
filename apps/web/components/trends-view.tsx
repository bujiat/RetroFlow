"use client";

import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";

import { Link, useRouter } from "@/i18n/navigation";
import { failedRequestMessage, redirectToLoginIfUnauthorized } from "@/lib/api/client";
import { getTrendsSummary, type TrendsSummary } from "@/lib/api/trends";

function formatRate(rate: number | null): string {
  if (rate === null) return "—";
  return `${Math.round(rate * 100)}%`;
}

export function TrendsView() {
  const t = useTranslations("trends");
  const tCommon = useTranslations("common");
  const router = useRouter();
  const [data, setData] = useState<TrendsSummary | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const summary = await getTrendsSummary();
        if (!cancelled) {
          setData(summary);
          setError(null);
        }
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
    <div className="space-y-8">
      <div>
        <h1 className="text-xl font-semibold tracking-tight text-zinc-950">{t("title")}</h1>
      </div>

      {error ? <p className="text-sm text-red-600">{error}</p> : null}

      {data === null && !error ? (
        <p className="text-sm text-zinc-500">{t("loading")}</p>
      ) : null}

      {data ? (
        <>
          <dl className="grid gap-6 sm:grid-cols-3">
            <div>
              <dt className="text-xs font-medium uppercase tracking-wide text-zinc-500">
                {t("overdue")}
              </dt>
              <dd className="mt-1 text-3xl font-semibold tabular-nums text-zinc-950">
                {data.overdue_actions}
              </dd>
            </div>
            <div>
              <dt className="text-xs font-medium uppercase tracking-wide text-zinc-500">
                {t("recurringClusters")}
              </dt>
              <dd className="mt-1 text-3xl font-semibold tabular-nums text-zinc-950">
                {data.recurring_clusters}
              </dd>
            </div>
            <div>
              <dt className="text-xs font-medium uppercase tracking-wide text-zinc-500">
                {t("verificationRate")}
              </dt>
              <dd className="mt-1 text-3xl font-semibold tabular-nums text-zinc-950">
                {formatRate(data.verification_rate)}
              </dd>
            </div>
          </dl>

          <section className="space-y-2 text-sm text-zinc-600">
            <p>
              {t("awaitingVerify")}:{" "}
              <span className="font-medium text-zinc-900">{data.awaiting_verify}</span>
              {" · "}
              {t("awaitingWork")}:{" "}
              <span className="font-medium text-zinc-900">{data.awaiting_work}</span>
              {" · "}
              {t("verified")}:{" "}
              <span className="font-medium text-zinc-900">{data.verified_actions}</span>
            </p>
            <p>
              {t("publishedRetros")}:{" "}
              <span className="font-medium text-zinc-900">{data.published_retros}</span>
              {" · "}
              {t("keptProblems")}:{" "}
              <span className="font-medium text-zinc-900">{data.kept_problems}</span>
            </p>
          </section>

          <section className="space-y-3">
            <h2 className="text-sm font-medium text-zinc-900">{t("topClusters")}</h2>
            {data.top_clusters.length === 0 ? (
              <p className="text-sm text-zinc-500">{t("noClusters")}</p>
            ) : (
              <ul className="divide-y border-y border-zinc-200">
                {data.top_clusters.map((c) => (
                  <li key={c.id} className="flex items-baseline justify-between gap-4 py-3">
                    <p className="font-medium text-zinc-950">{c.title}</p>
                    <p className="shrink-0 text-sm tabular-nums text-zinc-500">
                      {t("occurrenceCount", { count: c.occurrence_count })}
                    </p>
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section className="space-y-3">
            <div className="flex items-center justify-between gap-4">
              <h2 className="text-sm font-medium text-zinc-900">{t("overdueList")}</h2>
              <Link href="/actions/board" className="text-sm text-zinc-600 hover:text-zinc-950">
                {t("goActions")}
              </Link>
            </div>
            {data.overdue_items.length === 0 ? (
              <p className="text-sm text-zinc-500">{t("noOverdue")}</p>
            ) : (
              <ul className="divide-y border-y border-zinc-200">
                {data.overdue_items.map((item) => (
                  <li key={item.id} className="py-3">
                    <p className="font-medium text-zinc-950">{item.title}</p>
                    <p className="text-sm text-zinc-500">
                      {item.owner} · {t("due")} {item.due_date} · {item.status}
                    </p>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </>
      ) : null}
    </div>
  );
}
