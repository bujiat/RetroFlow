"use client";

import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";

import { Link, useRouter } from "@/i18n/navigation";
import { failedRequestMessage, redirectToLoginIfUnauthorized } from "@/lib/api/client";
import {
  generateWeeklyReview,
  getCurrentWeeklyReview,
  saveWeeklyReview,
} from "@/lib/api/weekly-reviews";
import type { WeeklyReview, WeeklyReviewCitation } from "@/types";

type WeeklySections = {
  completed: string;
  risks: string;
  recurring: string;
  nextWeek: string;
};

function parseWeeklySections(markdown: string): WeeklySections {
  const buckets: Record<string, string[]> = {};
  let current = "";
  for (const raw of markdown.split("\n")) {
    const line = raw.trimEnd();
    if (line.startsWith("## ")) {
      current = line.slice(3).trim();
      if (!buckets[current]) buckets[current] = [];
      continue;
    }
    if (!current) continue;
    buckets[current].push(line);
  }
  const join = (key: string) => (buckets[key] ?? []).join("\n").trim();
  return {
    completed: join("本周完成"),
    risks: join("延期与风险"),
    recurring: join("重复问题"),
    nextWeek: join("下周重点"),
  };
}

function splitItems(text: string): string[] {
  return text
    .split("\n")
    .map((line) => line.replace(/^[-*•]\s+/, "").trim())
    .filter((line) => line.length > 0 && line !== "（暂无）");
}

function isPresent(text: string): boolean {
  const trimmed = text.trim();
  return trimmed.length > 0 && trimmed !== "（暂无）";
}

function citationMetrics(citations: WeeklyReviewCitation[]) {
  let verified = 0;
  let overdue = 0;
  let awaiting = 0;
  for (const c of citations) {
    if (c.source_type !== "action") continue;
    const excerpt = (c.excerpt ?? "").toLowerCase();
    if (excerpt.includes("verified")) verified += 1;
    else if (excerpt.includes("overdue")) overdue += 1;
    else if (excerpt.includes("awaiting")) awaiting += 1;
  }
  return { verified, overdue, awaiting, sources: citations.length };
}

export function WeeklyReviewView() {
  const t = useTranslations("weeklyReview");
  const tCommon = useTranslations("common");
  const router = useRouter();
  const [loading, setLoading] = useState(true);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [review, setReview] = useState<WeeklyReview | null>(null);
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState("");

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const saved = await getCurrentWeeklyReview();
        if (cancelled) return;
        setReview(saved);
        setDraft(saved.content_markdown);
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
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, [router, t, tCommon]);

  async function onGenerate() {
    if (pending) return;
    const hasContent = Boolean(review?.content_markdown?.trim()) || Boolean(draft.trim());
    if (hasContent && !window.confirm(t("regenConfirm"))) {
      return;
    }
    setPending(true);
    setError(null);
    try {
      const data = await generateWeeklyReview();
      setReview(data);
      setDraft(data.content_markdown);
      setEditing(false);
    } catch (err) {
      if (redirectToLoginIfUnauthorized(err, router.replace)) return;
      setError(t("generateFailed"));
    } finally {
      setPending(false);
    }
  }

  async function onSave() {
    if (!review || pending) return;
    const text = draft.trim();
    if (!text) {
      setError(t("emptyContent"));
      return;
    }
    setPending(true);
    setError(null);
    try {
      const saved = await saveWeeklyReview(review.week_start, {
        content_markdown: text,
        citation_ids: review.citations.map((citation) => citation.id),
      });
      setReview(saved);
      setDraft(saved.content_markdown);
      setEditing(false);
    } catch (err) {
      if (redirectToLoginIfUnauthorized(err, router.replace)) return;
      setError(t("saveFailed"));
    } finally {
      setPending(false);
    }
  }

  const rangeLabel =
    review != null ? `${review.week_start} – ${review.week_end}` : t("thisWeek");
  const hasReviewContent = Boolean(review?.content_markdown.trim());
  const sections = hasReviewContent ? parseWeeklySections(review!.content_markdown) : null;
  const metrics = review ? citationMetrics(review.citations) : null;
  const actionTotal = metrics
    ? Math.max(metrics.verified + metrics.overdue + metrics.awaiting, 1)
    : 1;
  const nextItems = sections ? splitItems(sections.nextWeek) : [];

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div
            className="inline-flex items-center gap-2 rounded-full px-3.5 py-1.5 text-xs font-bold text-coral"
            style={{
              background: "linear-gradient(135deg, #FF6B4A22, #FFB83022)",
              border: "1.5px solid #FFB83044",
            }}
          >
            <span>✨</span>
            {t("aiBadge")}
          </div>
          <h1 className="rf-h1 mt-3">
            {t("title")} <span aria-hidden>✨</span>
          </h1>
          <p className="rf-lede mt-1">{t("lede")}</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            disabled={pending || loading}
            onClick={() => void onGenerate()}
            className="rf-btn-primary px-4 py-2"
          >
            {hasReviewContent ? t("regenerate") : t("generate")}
          </button>
          {review && review.status !== "empty" ? (
            editing ? (
              <button
                type="button"
                disabled={pending}
                onClick={() => void onSave()}
                className="rf-btn-ink px-4 py-2"
              >
                {t("save")}
              </button>
            ) : (
              <>
                <button
                  type="button"
                  disabled={pending}
                  onClick={() => {
                    setDraft(review.content_markdown);
                    setEditing(true);
                  }}
                  className="rf-btn-secondary px-4 py-2"
                >
                  {t("edit")}
                </button>
                {!review.saved ? (
                  <button
                    type="button"
                    disabled={pending}
                    onClick={() => void onSave()}
                    className="rf-btn-secondary px-4 py-2"
                  >
                    {t("save")}
                  </button>
                ) : null}
              </>
            )
          ) : null}
        </div>
      </div>

      <div className="flex gap-2 overflow-x-auto pb-1">
        <span className="rounded-full bg-ink px-4 py-2 text-sm font-semibold text-cream">
          {t("thisWeek")}
        </span>
        <span className="rounded-full border-2 border-ink/10 bg-white px-4 py-2 text-sm font-medium text-ink/45">
          {rangeLabel}
        </span>
        {review?.saved ? (
          <span className="rounded-full bg-mint/20 px-4 py-2 text-sm font-bold text-[#2a9a74]">
            {t("savedBadge")}
          </span>
        ) : review?.status === "insufficient_evidence" ? (
          <span className="rounded-full bg-sun/20 px-4 py-2 text-sm font-bold text-[#c48410]">
            {t("insufficientEvidence")}
          </span>
        ) : review && review.status !== "empty" ? (
          <span className="rounded-full bg-sun/20 px-4 py-2 text-sm font-bold text-[#c48410]">
            {t("draftBadge")}
          </span>
        ) : null}
      </div>

      {error ? (
        <p role="alert" className="text-sm font-semibold text-coral">
          {error}
        </p>
      ) : null}

      {loading ? (
        <p className="rf-lede">{t("loading")}</p>
      ) : !review || !hasReviewContent ? (
        <div className="rf-card space-y-2 p-8 text-center">
          <p className="text-3xl">✨</p>
          <p className="font-bold text-ink">{t("emptyHint")}</p>
          <p className="rf-lede">{t("emptyHint2")}</p>
        </div>
      ) : editing ? (
        <textarea
          aria-label={t("contentLabel")}
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          rows={16}
          className="rf-input font-mono"
        />
      ) : (
        <>
          {metrics && (metrics.sources > 0 || metrics.verified + metrics.overdue + metrics.awaiting > 0) ? (
            <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
              <MetricCard
                emoji="✅"
                color="#FF6B4A"
                value={metrics.verified}
                total={actionTotal}
                label={t("metricVerified")}
              />
              <MetricCard
                emoji="🚧"
                color="#FFB830"
                value={metrics.overdue}
                total={actionTotal}
                label={t("metricOverdue")}
              />
              <MetricCard
                emoji="📬"
                color="#3ECFA0"
                value={metrics.awaiting}
                total={actionTotal}
                label={t("metricAwaiting")}
              />
              <MetricCard
                emoji="🔗"
                color="#4AAFFF"
                value={metrics.sources}
                total={Math.max(metrics.sources, 1)}
                label={t("metricSources")}
              />
            </div>
          ) : null}

          {sections ? (
            <div className="grid gap-3 sm:grid-cols-3">
              <HighlightCard
                emoji="🏆"
                color="#FFB830"
                bg="#FFF8E8"
                label={t("hlCompleted")}
                text={isPresent(sections.completed) ? sections.completed : "—"}
              />
              <HighlightCard
                emoji="🚧"
                color="#FF6B4A"
                bg="#FFF0EC"
                label={t("hlRisks")}
                text={isPresent(sections.risks) ? sections.risks : "—"}
              />
              <HighlightCard
                emoji="🔁"
                color="#3ECFA0"
                bg="#EDFAF5"
                label={t("hlRecurring")}
                text={isPresent(sections.recurring) ? sections.recurring : "—"}
              />
            </div>
          ) : null}

          {review.citations.length > 0 ? (
            <div className="rounded-3xl bg-ink p-6">
              <div className="mb-5 flex items-center gap-2.5">
                <div className="flex size-8 items-center justify-center rounded-xl bg-sun/20 text-base">
                  ✨
                </div>
                <h2 className="font-display text-xl font-normal text-cream">{t("insightsTitle")}</h2>
                <span className="ml-auto rounded-full bg-sun/15 px-2.5 py-1 text-xs font-semibold text-sun">
                  {t("insightsCount", { count: review.citations.length })}
                </span>
              </div>
              <ul className="flex flex-col gap-3">
                {review.citations.map((c) => (
                  <CitationInsight
                    key={c.id}
                    citation={c}
                    openLabel={t("openSource")}
                    badgeTrend={t("badgeTrend")}
                    badgeAdvice={t("badgeAdvice")}
                    badgeNote={t("badgeNote")}
                  />
                ))}
              </ul>
            </div>
          ) : null}

          {nextItems.length > 0 ? (
            <div className="rf-card p-6">
              <h2 className="font-display mb-4 text-xl font-medium text-ink">
                📌 {t("nextWeekTitle")}
              </h2>
              <ol className="flex flex-col gap-3">
                {nextItems.map((item, i) => (
                  <li key={`${item}-${i}`} className="flex items-start gap-3">
                    <span
                      className="mt-0.5 flex size-6 shrink-0 items-center justify-center rounded-full text-xs font-bold text-white"
                      style={{ background: ["#FF6B4A", "#FFB830", "#3ECFA0"][i % 3] }}
                    >
                      {i + 1}
                    </span>
                    <p className="text-sm font-medium leading-relaxed text-ink/70">{item}</p>
                  </li>
                ))}
              </ol>
            </div>
          ) : null}
        </>
      )}
    </div>
  );
}

function MetricCard({
  emoji,
  color,
  value,
  total,
  label,
}: {
  emoji: string;
  color: string;
  value: number;
  total: number;
  label: string;
}) {
  const pct = Math.round((value / Math.max(total, 1)) * 100);
  return (
    <div className="rf-card p-5">
      <div className="mb-2 text-2xl">{emoji}</div>
      <div className="font-display leading-none" style={{ color, fontSize: 28 }}>
        {value}
        <span className="text-sm text-ink/30">/{total}</span>
      </div>
      <div className="mt-1 mb-2.5 text-xs font-semibold text-ink/50">{label}</div>
      <div className="h-1.5 overflow-hidden rounded-full bg-ink/10">
        <div className="h-full rounded-full" style={{ width: `${pct}%`, background: color }} />
      </div>
    </div>
  );
}

function HighlightCard({
  emoji,
  color,
  bg,
  label,
  text,
}: {
  emoji: string;
  color: string;
  bg: string;
  label: string;
  text: string;
}) {
  return (
    <div className="rounded-3xl p-5" style={{ background: bg, border: `2px solid ${color}22` }}>
      <div className="mb-3 text-2xl">{emoji}</div>
      <div className="mb-2 text-xs font-extrabold" style={{ color }}>
        {label}
      </div>
      <p className="whitespace-pre-wrap text-[13px] font-medium leading-relaxed text-ink">{text}</p>
    </div>
  );
}

function CitationInsight({
  citation: c,
  openLabel,
  badgeTrend,
  badgeAdvice,
  badgeNote,
}: {
  citation: WeeklyReviewCitation;
  openLabel: string;
  badgeTrend: string;
  badgeAdvice: string;
  badgeNote: string;
}) {
  let href: "/actions/board" | "/trends" | `/retro/${string}/confirm` | null = null;
  if (c.source_type === "action" || c.source_type === "event") {
    href = "/actions/board";
  } else if (c.source_type === "cluster") {
    href = "/trends";
  } else if (c.retro_id) {
    href = `/retro/${c.retro_id}/confirm`;
  }

  const badge =
    c.source_type === "cluster"
      ? { label: badgeTrend, color: "#FF6B4A", bg: "rgba(255,107,74,0.2)" }
      : c.source_type === "event"
        ? { label: badgeAdvice, color: "#FFB830", bg: "rgba(255,184,48,0.2)" }
        : { label: badgeNote, color: "#3ECFA0", bg: "rgba(62,207,160,0.2)" };

  return (
    <li className="rounded-2xl border border-white/8 bg-white/5 p-4">
      <div className="mb-2 flex flex-wrap items-center gap-2">
        <span className="text-xl">
          {c.source_type === "cluster" ? "🔄" : c.source_type === "event" ? "💡" : "🎉"}
        </span>
        <span
          className="rounded-full px-2.5 py-0.5 text-xs font-bold"
          style={{ background: badge.bg, color: badge.color }}
        >
          {badge.label}
        </span>
        <span className="text-sm font-bold text-cream">{c.title}</span>
      </div>
      {c.excerpt ? (
        <p className="text-[13px] font-medium leading-relaxed text-cream/60">{c.excerpt}</p>
      ) : null}
      {href ? (
        <Link href={href} className="mt-2 inline-block text-xs font-bold text-sun hover:underline">
          {openLabel}
        </Link>
      ) : null}
    </li>
  );
}
