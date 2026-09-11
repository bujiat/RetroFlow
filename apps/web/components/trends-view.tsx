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

const MIX_COLORS = {
  verified: "#3ECFA0",
  awaitingVerify: "#FFB830",
  awaitingWork: "#4AAFFF",
  overdue: "#FF6B4A",
} as const;

const CLUSTER_COLORS = ["#FF6B4A", "#FFB830", "#3ECFA0", "#4AAFFF", "#7C5CBF"];

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

  const mix = data
    ? [
        { key: "verified", n: data.verified_actions, color: MIX_COLORS.verified, label: t("verified") },
        {
          key: "awaitingVerify",
          n: data.awaiting_verify,
          color: MIX_COLORS.awaitingVerify,
          label: t("awaitingVerify"),
        },
        {
          key: "awaitingWork",
          n: data.awaiting_work,
          color: MIX_COLORS.awaitingWork,
          label: t("awaitingWork"),
        },
        { key: "overdue", n: data.overdue_actions, color: MIX_COLORS.overdue, label: t("overdue") },
      ]
    : [];
  const mixTotal = mix.reduce((sum, row) => sum + row.n, 0);
  const clusterMax = data
    ? Math.max(...data.top_clusters.map((c) => c.occurrence_count), 1)
    : 1;

  return (
    <div className="space-y-5">
      <div>
        <h1 className="rf-h1">
          {t("title")} <span aria-hidden>📈</span>
        </h1>
        <p className="rf-lede mt-1">{t("lede")}</p>
      </div>

      {error ? <p className="text-sm font-semibold text-coral">{error}</p> : null}

      {data === null && !error ? <p className="rf-lede">{t("loading")}</p> : null}

      {data ? (
        <>
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            <StatCard
              emoji="✅"
              color="#3ECFA0"
              value={formatRate(data.verification_rate)}
              label={t("verificationRate")}
            />
            <StatCard emoji="⏰" color="#FF6B4A" value={String(data.overdue_actions)} label={t("overdue")} />
            <StatCard
              emoji="🔁"
              color="#7C5CBF"
              value={String(data.recurring_clusters)}
              label={t("recurringClusters")}
            />
            <StatCard
              emoji="📋"
              color="#4AAFFF"
              value={String(data.published_retros)}
              label={t("publishedRetros")}
            />
          </div>

          <div className="rf-card p-6">
            <h2 className="mb-5 text-[15px] font-extrabold text-ink">✅ {t("mixTitle")}</h2>
            {mixTotal === 0 ? (
              <p className="rf-lede">{t("noOverdue")}</p>
            ) : (
              <>
                <div className="flex h-14 overflow-hidden rounded-2xl">
                  {mix.map((row) =>
                    row.n === 0 ? null : (
                      <div
                        key={row.key}
                        title={`${row.label} ${row.n}`}
                        style={{ width: `${(row.n / mixTotal) * 100}%`, background: row.color }}
                      />
                    ),
                  )}
                </div>
                <ul className="mt-5 grid grid-cols-2 gap-3 sm:grid-cols-4">
                  {mix.map((row) => (
                    <li key={row.key} className="flex items-baseline gap-2">
                      <span className="size-2.5 shrink-0 rounded-full" style={{ background: row.color }} />
                      <span className="text-xs font-semibold text-ink/50">{row.label}</span>
                      <span className="font-display ml-auto text-xl font-medium text-ink">{row.n}</span>
                    </li>
                  ))}
                </ul>
              </>
            )}
          </div>

          <div className="grid gap-4 lg:grid-cols-2">
            <div className="rf-card p-6">
              <h2 className="mb-5 text-[15px] font-extrabold text-ink">🎯 {t("clusterChartTitle")}</h2>
              {data.top_clusters.length === 0 ? (
                <p className="rf-lede">{t("noClusters")}</p>
              ) : (
                <ul className="space-y-3">
                  {data.top_clusters.map((c, i) => (
                    <li key={c.id}>
                      <div className="mb-1 flex items-baseline justify-between gap-3">
                        <p className="truncate text-sm font-bold text-ink">{c.title}</p>
                        <p className="shrink-0 text-xs font-semibold tabular-nums text-ink/45">
                          {t("occurrenceCount", { count: c.occurrence_count })}
                        </p>
                      </div>
                      <div className="h-2.5 overflow-hidden rounded-full bg-ink/8">
                        <div
                          className="h-full rounded-full"
                          style={{
                            width: `${(c.occurrence_count / clusterMax) * 100}%`,
                            background: CLUSTER_COLORS[i % CLUSTER_COLORS.length],
                          }}
                        />
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </div>

            <div className="rf-card p-6">
              <div className="mb-5 flex items-center justify-between gap-3">
                <h2 className="text-[15px] font-extrabold text-ink">⏰ {t("overdueList")}</h2>
                <Link href="/actions/board" className="text-sm font-semibold text-coral hover:underline">
                  {t("goActions")}
                </Link>
              </div>
              {data.overdue_items.length === 0 ? (
                <p className="rf-lede">{t("noOverdue")}</p>
              ) : (
                <ul className="space-y-3">
                  {data.overdue_items.map((item) => (
                    <li key={item.id} className="flex items-center gap-3 rounded-2xl bg-sand/50 px-3 py-2.5">
                      <span className="rf-avatar bg-coral text-xs">{item.owner.trim()[0]?.toUpperCase() ?? "?"}</span>
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-sm font-bold text-ink">{item.title}</p>
                        <p className="text-xs font-medium text-ink/45">
                          {item.owner} · {t("due")} {item.due_date}
                        </p>
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>
        </>
      ) : null}
    </div>
  );
}

function StatCard({
  emoji,
  color,
  value,
  label,
}: {
  emoji: string;
  color: string;
  value: string;
  label: string;
}) {
  return (
    <div className="rf-card p-5">
      <div className="mb-3 flex items-center justify-between">
        <span className="text-xl">{emoji}</span>
        <span className="size-2 rounded-full" style={{ background: color }} />
      </div>
      <div className="font-display text-[28px] leading-none text-ink">{value}</div>
      <div className="mt-1 text-xs font-semibold text-ink/50">{label}</div>
    </div>
  );
}
