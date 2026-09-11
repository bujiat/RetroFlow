"use client";

import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";

import { useRouter } from "@/i18n/navigation";
import { failedRequestMessage, redirectToLoginIfUnauthorized } from "@/lib/api/client";
import { listRetros, type RetroListItem } from "@/lib/api/retros";

const TYPE_META: Record<string, { emoji: string; color: string; typeKey: "typeSprint" | "typeIncident" | "typeRelease" }> = {
  sprint: { emoji: "🚀", color: "#4AAFFF", typeKey: "typeSprint" },
  incident: { emoji: "⚙️", color: "#FF6B4A", typeKey: "typeIncident" },
  release: { emoji: "🎨", color: "#7C5CBF", typeKey: "typeRelease" },
};

const STATUS_STYLE: Record<string, { bg: string; color: string; dot: string }> = {
  published: { bg: "rgba(62,207,160,0.15)", color: "#2a9a74", dot: "#3ECFA0" },
  ready_for_review: { bg: "rgba(255,184,48,0.18)", color: "#c48410", dot: "#FFB830" },
  analysis_failed: { bg: "rgba(255,107,74,0.15)", color: "#e04a2c", dot: "#FF6B4A" },
  analyzing: { bg: "rgba(74,175,255,0.15)", color: "#2b7ec4", dot: "#4AAFFF" },
  draft: { bg: "rgba(45,31,20,0.08)", color: "#2D1F14", dot: "#2D1F14" },
};

function statusLabel(
  status: string,
  t: ReturnType<typeof useTranslations<"retros">>,
): string {
  if (
    status === "draft" ||
    status === "analyzing" ||
    status === "analysis_failed" ||
    status === "ready_for_review" ||
    status === "published"
  ) {
    return t(`status.${status}`);
  }
  return status;
}

export function RetrosList() {
  const t = useTranslations("retros");
  const tType = useTranslations("retroNew");
  const tCommon = useTranslations("common");
  const router = useRouter();
  const [items, setItems] = useState<RetroListItem[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const data = await listRetros();
        if (!cancelled) {
          setItems(data);
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
        setItems([]);
      }
    }

    void load();
    return () => {
      cancelled = true;
    };
  }, [router, t, tCommon]);

  return (
    <div className="space-y-6">
      <div className="flex items-end justify-between gap-4">
        <div>
          <h1 className="rf-h1">{t("title")}</h1>
          {items ? (
            <p className="rf-lede mt-1">{t("countLine", { count: items.length })}</p>
          ) : null}
        </div>
        <button type="button" onClick={() => router.push("/retro/new")} className="rf-btn-primary px-5 py-2.5">
          {t("new")}
        </button>
      </div>

      {error ? <p className="text-sm font-semibold text-coral">{error}</p> : null}

      {items === null ? (
        <p className="rf-lede">{t("loading")}</p>
      ) : items.length === 0 ? (
        <div className="rf-card px-6 py-12 text-center">
          <p className="text-4xl">📋</p>
          <p className="rf-lede mt-3">{t("empty")}</p>
        </div>
      ) : (
        <ul className="grid gap-4">
          {items.map((item) => {
            const meta = TYPE_META[item.type] ?? TYPE_META.sprint;
            const statusStyle = STATUS_STYLE[item.status] ?? STATUS_STYLE.draft;
            return (
              <li key={item.id} className="rf-card flex flex-col gap-3 overflow-hidden p-5 sm:flex-row sm:items-center">
                <button
                  type="button"
                  onClick={() => router.push(`/retro/${item.id}/confirm`)}
                  className="flex min-w-0 flex-1 items-center gap-4 py-1 text-left"
                >
                  <div
                    className="flex size-14 shrink-0 items-center justify-center rounded-2xl text-2xl"
                    style={{ background: `${meta.color}22` }}
                  >
                    {meta.emoji}
                  </div>
                  <span className="flex min-w-0 flex-1 flex-col gap-1.5">
                    <span className="font-extrabold text-ink">{item.title}</span>
                    <span className="flex flex-wrap items-center gap-2 text-sm font-medium text-ink/45">
                      <span
                        className="rf-chip"
                        style={{ background: `${meta.color}18`, color: meta.color }}
                      >
                        {tType(meta.typeKey)}
                      </span>
                      <span>{item.review_date}</span>
                    </span>
                  </span>
                </button>
                <div className="flex flex-wrap items-center gap-2 sm:shrink-0">
                  <span
                    className="rf-chip inline-flex items-center gap-1.5"
                    style={{ background: statusStyle.bg, color: statusStyle.color }}
                  >
                    <span className="size-1.5 rounded-full" style={{ background: statusStyle.dot }} />
                    {statusLabel(item.status, t)}
                  </span>
                  {item.status !== "published" ? (
                    <button
                      type="button"
                      onClick={() => router.push(`/retro/${item.id}/confirm`)}
                      className="rf-btn-ink px-4 py-2"
                    >
                      {t("publish")}
                    </button>
                  ) : null}
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
