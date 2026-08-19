"use client";

import { useTranslations } from "next-intl";
import { useEffect, useState, type ReactNode } from "react";

import { Link, useRouter } from "@/i18n/navigation";
import { failedRequestMessage, redirectToLoginIfUnauthorized } from "@/lib/api/client";
import {
  generateWeeklyReview,
  getCurrentWeeklyReview,
  saveWeeklyReview,
} from "@/lib/api/weekly-reviews";
import type { WeeklyReview, WeeklyReviewCitation } from "@/types";

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

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="space-y-1">
          <Link href="/actions/board" className="text-sm text-zinc-600 hover:text-zinc-950">
            {t("backWeek")}
          </Link>
          <h1 className="text-xl font-semibold tracking-tight text-zinc-950">{t("title")}</h1>
          <p className="text-sm text-zinc-500">{rangeLabel}</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            disabled={pending || loading}
            onClick={() => void onGenerate()}
            className="rounded-md bg-zinc-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-zinc-800 disabled:opacity-60"
          >
            {hasReviewContent ? t("regenerate") : t("generate")}
          </button>
          {review && review.status !== "empty" ? (
            editing ? (
              <button
                type="button"
                disabled={pending}
                onClick={() => void onSave()}
                className="rounded-md border border-zinc-300 bg-white px-3 py-1.5 text-sm text-zinc-800 hover:bg-zinc-50 disabled:opacity-60"
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
                  className="rounded-md border border-zinc-300 bg-white px-3 py-1.5 text-sm text-zinc-800 hover:bg-zinc-50 disabled:opacity-60"
                >
                  {t("edit")}
                </button>
                {!review.saved ? (
                  <button
                    type="button"
                    disabled={pending}
                    onClick={() => void onSave()}
                    className="rounded-md border border-zinc-300 bg-white px-3 py-1.5 text-sm text-zinc-800 hover:bg-zinc-50 disabled:opacity-60"
                  >
                    {t("save")}
                  </button>
                ) : null}
              </>
            )
          ) : null}
        </div>
      </div>

      {error ? (
        <p role="alert" className="text-sm text-red-600">
          {error}
        </p>
      ) : null}

      {loading ? (
        <p className="text-sm text-zinc-500">{t("loading")}</p>
      ) : !review || !hasReviewContent ? (
        <div className="space-y-2">
          <p className="text-sm text-zinc-600">{t("emptyHint")}</p>
          <p className="text-sm text-zinc-500">{t("emptyHint2")}</p>
        </div>
      ) : (
        <div className="space-y-6">
          {review.saved ? (
            <p className="text-xs text-zinc-500">{t("savedBadge")}</p>
          ) : review.status === "insufficient_evidence" ? (
            <p className="text-xs text-amber-800">{t("insufficientEvidence")}</p>
          ) : review.status === "ok" ? (
            <p className="text-xs text-amber-800">{t("draftBadge")}</p>
          ) : null}

          {editing ? (
            <textarea
              aria-label={t("contentLabel")}
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              rows={16}
              className="w-full rounded-md border border-zinc-300 bg-white px-3 py-2 font-mono text-sm text-zinc-900 outline-none focus:border-zinc-900"
            />
          ) : (
            <WeeklyMarkdown text={review.content_markdown} />
          )}

          {review.citations.length > 0 ? (
            <section className="space-y-2 border-t border-zinc-200 pt-4">
              <h2 className="text-sm font-medium text-zinc-800">{t("citations")}</h2>
              <ol className="list-decimal space-y-2 pl-5 text-sm text-zinc-600">
                {review.citations.map((c) => (
                  <CitationItem key={c.id} citation={c} openLabel={t("openSource")} />
                ))}
              </ol>
            </section>
          ) : null}
        </div>
      )}
    </div>
  );
}

function WeeklyMarkdown({ text }: { text: string }) {
  const blocks: ReactNode[] = [];
  let listItems: string[] = [];
  let key = 0;

  function flushList() {
    if (listItems.length === 0) return;
    blocks.push(
      <ul key={`ul-${key++}`} className="list-disc space-y-1 pl-5 text-sm text-zinc-700">
        {listItems.map((item, i) => (
          <li key={i}>{item}</li>
        ))}
      </ul>,
    );
    listItems = [];
  }

  for (const raw of text.split("\n")) {
    const line = raw.trimEnd();
    if (line.startsWith("## ")) {
      flushList();
      blocks.push(
        <h2 key={`h-${key++}`} className="pt-2 text-sm font-semibold text-zinc-950">
          {line.slice(3).trim()}
        </h2>,
      );
      continue;
    }
    if (line.startsWith("- ") || line.startsWith("* ")) {
      listItems.push(line.slice(2).trim());
      continue;
    }
    if (line.trim() === "") {
      flushList();
      continue;
    }
    flushList();
    blocks.push(
      <p key={`p-${key++}`} className="text-sm leading-relaxed text-zinc-700">
        {line.trim()}
      </p>,
    );
  }
  flushList();

  return <div className="space-y-2">{blocks}</div>;
}

function CitationItem({
  citation: c,
  openLabel,
}: {
  citation: WeeklyReviewCitation;
  openLabel: string;
}) {
  let href: "/actions/board" | "/trends" | `/retro/${string}/confirm` | null = null;
  if (c.source_type === "action" || c.source_type === "event") {
    href = "/actions/board";
  } else if (c.source_type === "cluster") {
    href = "/trends";
  } else if (c.retro_id) {
    href = `/retro/${c.retro_id}/confirm`;
  }

  return (
    <li>
      <span className="font-medium text-zinc-800">{c.title}</span>
      <span className="text-zinc-400"> · {c.source_type}</span>
      {c.excerpt ? <p className="text-zinc-500">{c.excerpt}</p> : null}
      {href ? (
        <Link href={href} className="text-zinc-900 underline-offset-2 hover:underline">
          {openLabel}
        </Link>
      ) : null}
    </li>
  );
}
