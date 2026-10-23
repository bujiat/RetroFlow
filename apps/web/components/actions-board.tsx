"use client";

import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";

import { useRouter } from "@/i18n/navigation";
import {
  getMyWeek,
  listActionEvents,
  listActions,
  patchActionStatus,
  rejectAction,
  submitEvidence,
  suggestVerification,
  verifyAction,
  type ActionEvent,
  type ActionItem,
  type MyWeek,
  type VerifySuggestion,
} from "@/lib/api/actions";
import { failedRequestMessage, redirectToLoginIfUnauthorized } from "@/lib/api/client";

type Tab = "week" | "all";

const EMPTY_WEEK: MyWeek = {
  overdue: [],
  due_this_week: [],
  awaiting_verify: [],
};

export function ActionsBoard() {
  const t = useTranslations("actionsBoard");
  const tCommon = useTranslations("common");
  const router = useRouter();
  const [tab, setTab] = useState<Tab>("week");
  const [items, setItems] = useState<ActionItem[] | null>(null);
  const [week, setWeek] = useState<MyWeek | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function loadAll() {
    const data = await listActions();
    setItems(data);
    setError(null);
  }

  async function loadWeek() {
    const data = await getMyWeek();
    setWeek(data);
    setError(null);
  }

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        if (tab === "week") {
          const data = await getMyWeek();
          if (!cancelled) {
            setWeek(data);
            setError(null);
          }
        } else {
          const data = await listActions();
          if (!cancelled) {
            setItems(data);
            setError(null);
          }
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
        if (tab === "week") setWeek(EMPTY_WEEK);
        else setItems([]);
      }
    }

    void load();
    return () => {
      cancelled = true;
    };
  }, [router, t, tCommon, tab]);

  function replaceInAll(updated: ActionItem) {
    setItems((prev) =>
      prev ? prev.map((row) => (row.id === updated.id ? updated : row)) : prev,
    );
  }

  async function afterMutation(updated: ActionItem) {
    if (tab === "week") {
      try {
        await loadWeek();
      } catch (err) {
        setError(
          failedRequestMessage(err, {
            network: tCommon("networkError"),
            fallback: t("loadFailed"),
          }),
        );
      }
      return;
    }
    replaceInAll(updated);
  }

  const weekEmpty =
    week !== null &&
    week.overdue.length === 0 &&
    week.due_this_week.length === 0 &&
    week.awaiting_verify.length === 0;

  const allCount = items?.length ?? 0;
  const verifiedCount = items?.filter((row) => row.status === "verified").length ?? 0;
  const progressPct = allCount > 0 ? Math.round((verifiedCount / allCount) * 100) : 0;

  return (
    <div className="space-y-6">
      <div className="flex items-end justify-between gap-4">
        <div>
          <h1 className="rf-h1">{t("title")} 🎯</h1>
          {tab === "all" && items && items.length > 0 ? (
            <p className="rf-lede mt-1">
              <span className="font-bold text-mint">{verifiedCount}</span>
              {" / "}
              {allCount}
            </p>
          ) : null}
        </div>
      </div>

      {tab === "all" && items && items.length > 0 ? (
        <div className="rf-card flex flex-col gap-5 p-5 sm:flex-row sm:items-center">
          <div className="min-w-0 flex-1 space-y-2">
            <div className="flex items-center justify-between text-sm font-bold text-ink">
              <span>{t("progress", { done: verifiedCount, total: allCount })}</span>
              <span className="font-display text-xl font-medium text-coral">{progressPct}%</span>
            </div>
            <div className="h-3 overflow-hidden rounded-full bg-ink/10">
              <div
                className="h-full rounded-full bg-linear-to-r from-coral to-sun"
                style={{ width: `${progressPct}%` }}
              />
            </div>
          </div>
          <div className="flex shrink-0 gap-5">
            <MiniStat
              n={items.filter((row) => row.status === "in_progress").length}
              label={t("status.in_progress")}
              color="#FF6B4A"
            />
            <MiniStat
              n={items.filter((row) => row.status === "open").length}
              label={t("status.open")}
              color="rgba(45,31,20,0.35)"
            />
            <MiniStat n={verifiedCount} label={t("status.verified")} color="#3ECFA0" />
          </div>
        </div>
      ) : null}

      {tab === "week" && week && !weekEmpty ? (
        <div className="rf-card flex flex-wrap gap-6 p-5">
          <MiniStat n={week.overdue.length} label={t("sectionOverdue")} color="#FF6B4A" />
          <MiniStat n={week.due_this_week.length} label={t("sectionDueThisWeek")} color="#FFB830" />
          <MiniStat n={week.awaiting_verify.length} label={t("sectionAwaitingVerify")} color="#3ECFA0" />
        </div>
      ) : null}

      <div
        role="tablist"
        aria-label={t("title")}
        className="flex w-fit gap-1 rounded-full bg-sand p-1 text-sm"
      >
        <TabButton active={tab === "week"} onClick={() => setTab("week")}>
          {t("tabWeek")}
        </TabButton>
        <TabButton active={tab === "all"} onClick={() => setTab("all")}>
          {t("tabAll")}
        </TabButton>
      </div>

      {error ? (
        <p role="alert" className="text-sm font-semibold text-coral">
          {error}
        </p>
      ) : null}

      {tab === "week" ? (
        week === null ? (
          <p className="rf-lede">{t("loading")}</p>
        ) : weekEmpty ? (
          <div className="rf-card px-6 py-12 text-center">
            <p className="text-4xl">🎯</p>
            <p className="rf-lede mt-3">{t("weekEmpty")}</p>
          </div>
        ) : (
          <div className="space-y-8">
            <WeekSection
              title={t("sectionOverdue")}
              items={week.overdue}
              onUpdated={(item) => void afterMutation(item)}
              onNeedReload={() => void loadWeek().catch(() => setError(t("loadFailed")))}
            />
            <WeekSection
              title={t("sectionDueThisWeek")}
              items={week.due_this_week}
              onUpdated={(item) => void afterMutation(item)}
              onNeedReload={() => void loadWeek().catch(() => setError(t("loadFailed")))}
            />
            <WeekSection
              title={t("sectionAwaitingVerify")}
              items={week.awaiting_verify}
              onUpdated={(item) => void afterMutation(item)}
              onNeedReload={() => void loadWeek().catch(() => setError(t("loadFailed")))}
            />
          </div>
        )
      ) : items === null ? (
        <p className="rf-lede">{t("loading")}</p>
      ) : items.length === 0 ? (
        <div className="rf-card px-6 py-12 text-center">
          <p className="text-4xl">🎯</p>
          <p className="rf-lede mt-3">{t("empty")}</p>
        </div>
      ) : (
        <ul className="grid gap-3">
          {items.map((item) => (
            <ActionRow
              key={item.id}
              item={item}
              onUpdated={(item) => void afterMutation(item)}
              onNeedReload={() => void loadAll().catch(() => setError(t("loadFailed")))}
            />
          ))}
        </ul>
      )}
    </div>
  );
}

function MiniStat({ n, label, color }: { n: number; label: string; color: string }) {
  return (
    <div className="text-center">
      <div className="font-display text-2xl leading-none" style={{ color }}>
        {n}
      </div>
      <div className="mt-1 text-[11px] font-semibold text-ink/45">{label}</div>
    </div>
  );
}

function TabButton({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      role="tab"
      aria-selected={active}
      onClick={onClick}
      className={
        active
          ? "rounded-full bg-white px-4 py-2 font-bold text-ink shadow-sm"
          : "rounded-full px-4 py-2 font-medium text-ink/45 hover:text-ink"
      }
    >
      {children}
    </button>
  );
}

function WeekSection({
  title,
  items,
  onUpdated,
  onNeedReload,
}: {
  title: string;
  items: ActionItem[];
  onUpdated: (item: ActionItem) => void;
  onNeedReload: () => void;
}) {
  if (items.length === 0) return null;
  return (
    <section className="space-y-3">
      <h2 className="font-display text-lg font-medium text-ink">
        {title}
        <span className="ml-2 text-base font-medium text-ink/40">{items.length}</span>
      </h2>
      <ul className="grid gap-3">
        {items.map((item) => (
          <ActionRow
            key={item.id}
            item={item}
            onUpdated={onUpdated}
            onNeedReload={onNeedReload}
          />
        ))}
      </ul>
    </section>
  );
}

type ActionRowProps = {
  item: ActionItem;
  onUpdated: (item: ActionItem) => void;
  onNeedReload: () => void;
};

function ActionRow({ item, onUpdated, onNeedReload }: ActionRowProps) {
  const t = useTranslations("actionsBoard");
  const router = useRouter();
  const [pending, setPending] = useState(false);
  const [rowError, setRowError] = useState<string | null>(null);
  const [showEvidence, setShowEvidence] = useState(false);
  const [showReject, setShowReject] = useState(false);
  const [note, setNote] = useState("");
  const [evidenceText, setEvidenceText] = useState("");
  const [evidenceUrl, setEvidenceUrl] = useState("");
  const [rejectReason, setRejectReason] = useState("");
  const [events, setEvents] = useState<ActionEvent[] | null>(null);
  const [suggestion, setSuggestion] = useState<VerifySuggestion | null>(null);

  async function run(fn: () => Promise<ActionItem>) {
    setPending(true);
    setRowError(null);
    try {
      const updated = await fn();
      onUpdated(updated);
      setShowEvidence(false);
      setShowReject(false);
      setNote("");
      setEvidenceText("");
      setEvidenceUrl("");
      setRejectReason("");
      setEvents(null);
    } catch (err) {
      if (redirectToLoginIfUnauthorized(err, router.replace)) return;
      setRowError(t("actionFailed"));
      onNeedReload();
    } finally {
      setPending(false);
    }
  }

  async function suggest() {
    setPending(true);
    setRowError(null);
    setSuggestion(null);
    try {
      setSuggestion(await suggestVerification(item.id));
    } catch (err) {
      if (redirectToLoginIfUnauthorized(err, router.replace)) return;
      setRowError(t("suggestFailed"));
    } finally {
      setPending(false);
    }
  }
  async function loadEvents() {
    if (events) {
      setEvents(null);
      return;
    }
    try {
      setEvents(await listActionEvents(item.id));
    } catch (err) {
      if (redirectToLoginIfUnauthorized(err, router.replace)) return;
      setRowError(t("eventsFailed"));
    }
  }

  const terminal = item.status === "verified" || item.status === "cancelled";
  const done = item.status === "verified";
  const ownerInitial = (item.owner.trim()[0] ?? "?").toUpperCase();
  const avatarHue =
    ["#FF6B4A", "#FFB830", "#3ECFA0", "#7C5CBF", "#4AAFFF"][
      Array.from(item.owner).reduce((sum, ch) => sum + ch.charCodeAt(0), 0) % 5
    ];
  const statusChip =
    item.status === "verified"
      ? { bg: "rgba(62,207,160,0.15)", color: "#2a9a74" }
      : item.status === "evidence_submitted"
        ? { bg: "rgba(255,184,48,0.18)", color: "#c48410" }
        : item.status === "in_progress"
          ? { bg: "rgba(74,175,255,0.15)", color: "#2b7ec4" }
          : item.status === "cancelled"
            ? { bg: "rgba(45,31,20,0.08)", color: "#8a7a6e" }
            : { bg: "rgba(255,107,74,0.12)", color: "#e04a2c" };
  const statusKey =
    item.status === "open" ||
    item.status === "in_progress" ||
    item.status === "evidence_submitted" ||
    item.status === "verified" ||
    item.status === "cancelled"
      ? item.status
      : null;

  return (
    <li
      className="rf-card space-y-3 p-5"
      style={
        done
          ? { background: "rgba(62,207,160,0.04)", borderColor: "rgba(62,207,160,0.2)" }
          : undefined
      }
    >
      <div className="flex items-start gap-3">
        <span
          className="rf-check mt-0.5"
          style={
            done
              ? { background: "#3ECFA0", color: "white" }
              : { border: "2px solid rgba(45,31,20,0.15)", color: "transparent" }
          }
          aria-hidden
        >
          {done ? "✓" : ""}
        </span>
        <div className="min-w-0 flex-1 space-y-1">
          <div className="flex items-start justify-between gap-3">
            <p className={`font-extrabold text-ink ${done ? "line-through opacity-50" : ""}`}>
              {item.title}
            </p>
            <span className="rf-avatar" style={{ background: avatarHue }} title={item.owner}>
              {ownerInitial}
            </span>
          </div>
          <p className="flex flex-wrap items-center gap-2 text-sm font-medium text-ink/45">
            <span>
              {t("due")} {item.due_date}
            </span>
            <span
              className="rf-chip"
              style={{ background: statusChip.bg, color: statusChip.color }}
            >
              {statusKey ? t(`status.${statusKey}`) : item.status}
            </span>
          </p>
        </div>
      </div>

      {rowError ? (
        <p role="alert" className="text-sm font-semibold text-coral">
          {rowError}
        </p>
      ) : null}

      {!terminal ? (
        <div className="flex flex-wrap gap-2">
          {item.status === "open" ? (
            <button
              type="button"
              disabled={pending}
              onClick={() => void run(() => patchActionStatus(item.id, "in_progress"))}
              className="rf-btn-primary px-4 py-1.5"
            >
              {t("start")}
            </button>
          ) : null}

          {item.status === "in_progress" ? (
            <button
              type="button"
              disabled={pending}
              onClick={() => void run(() => patchActionStatus(item.id, "open"))}
              className="rf-btn-secondary px-3 py-1.5 disabled:opacity-60"
            >
              {t("backToOpen")}
            </button>
          ) : null}

          {item.status === "open" || item.status === "in_progress" ? (
            <>
              <button
                type="button"
                disabled={pending}
                onClick={() => {
                  setShowEvidence((v) => !v);
                  setShowReject(false);
                }}
                className="rf-btn-secondary px-3 py-1.5 disabled:opacity-60"
              >
                {t("submitEvidence")}
              </button>
              <button
                type="button"
                disabled={pending}
                onClick={() => void run(() => patchActionStatus(item.id, "cancelled"))}
                className="rf-btn-secondary px-3 py-1.5 text-ink/60 disabled:opacity-60"
              >
                {t("cancel")}
              </button>
            </>
          ) : null}

          {item.status === "evidence_submitted" ? (
            <>
              <button
                type="button"
                disabled={pending}
                onClick={() => void suggest()}
                className="rf-btn-secondary px-3 py-1.5 disabled:opacity-60"
              >
                {t("suggest")}
              </button>
              <button
                type="button"
                disabled={pending}
                onClick={() => void run(() => verifyAction(item.id))}
                className="rf-btn-primary px-4 py-1.5"
              >
                {t("verify")}
              </button>
              <button
                type="button"
                disabled={pending}
                onClick={() => {
                  setShowReject((v) => !v);
                  setShowEvidence(false);
                }}
                className="rf-btn-secondary px-3 py-1.5 disabled:opacity-60"
              >
                {t("reject")}
              </button>
            </>
          ) : null}

          <button
            type="button"
            disabled={pending}
            onClick={() => void loadEvents()}
            className="px-3 py-1.5 text-sm font-semibold text-ink/50 hover:text-ink"
          >
            {events ? t("hideTimeline") : t("showTimeline")}
          </button>
        </div>
      ) : (
        <button
          type="button"
          onClick={() => void loadEvents()}
          className="text-sm font-semibold text-ink/50 hover:text-ink"
        >
          {events ? t("hideTimeline") : t("showTimeline")}
        </button>
      )}

      {suggestion && item.status === "evidence_submitted" ? (
        <div className="space-y-2 rounded-2xl bg-sand/60 p-3 text-sm">
          <p className="font-bold text-ink">
            {suggestion.decision === "pass" ? t("suggestPass") : t("suggestReject")}
          </p>
          <p className="text-ink/80">{suggestion.reason}</p>
          <ul className="list-disc space-y-1 pl-4 text-ink/60">
            {suggestion.evidence.map((quote, index) => (
              <li key={`${quote}-${index}`}>{quote}</li>
            ))}
          </ul>
          <p className="text-xs font-medium text-ink/40">{t("suggestHint")}</p>
        </div>
      ) : null}

      {showEvidence ? (
        <form
          className="space-y-2 rounded-2xl bg-sand/60 p-3"
          onSubmit={(e) => {
            e.preventDefault();
            if (!evidenceText.trim() && !evidenceUrl.trim()) {
              setRowError(t("evidenceHint"));
              return;
            }
            void run(() =>
              submitEvidence(item.id, {
                completion_note: note.trim(),
                evidence_text: evidenceText.trim() || null,
                evidence_url: evidenceUrl.trim() || null,
              }),
            );
          }}
        >
          <label className="block space-y-1 text-sm">
            <span className="font-bold text-ink">{t("completionNote")}</span>
            <textarea
              required
              value={note}
              onChange={(e) => setNote(e.target.value)}
              rows={2}
              className="rf-input"
            />
          </label>
          <label className="block space-y-1 text-sm">
            <span className="font-bold text-ink">{t("evidenceText")}</span>
            <textarea
              value={evidenceText}
              onChange={(e) => setEvidenceText(e.target.value)}
              rows={2}
              className="rf-input"
            />
          </label>
          <label className="block space-y-1 text-sm">
            <span className="font-bold text-ink">{t("evidenceUrl")}</span>
            <input
              value={evidenceUrl}
              onChange={(e) => setEvidenceUrl(e.target.value)}
              placeholder="https://"
              className="rf-input"
            />
          </label>
          <p className="text-xs font-medium text-ink/40">{t("evidenceHint")}</p>
          <button type="submit" disabled={pending} className="rf-btn-primary px-4 py-1.5">
            {t("applyVerify")}
          </button>
        </form>
      ) : null}

      {showReject ? (
        <form
          className="space-y-2 rounded-2xl bg-sand/60 p-3"
          onSubmit={(e) => {
            e.preventDefault();
            void run(() => rejectAction(item.id, rejectReason));
          }}
        >
          <label className="block space-y-1 text-sm">
            <span className="font-bold text-ink">{t("rejectReason")}</span>
            <textarea
              required
              value={rejectReason}
              onChange={(e) => setRejectReason(e.target.value)}
              rows={2}
              className="rf-input"
            />
          </label>
          <button type="submit" disabled={pending} className="rf-btn-primary px-4 py-1.5">
            {t("confirmReject")}
          </button>
        </form>
      ) : null}

      {events ? (
        <ol className="space-y-2 border-l-2 border-ink/10 pl-3 text-sm text-ink/60">
          {events.map((ev) => (
            <li key={ev.id}>
              <span className="font-bold text-ink">{ev.event_type}</span>
              {ev.from_status || ev.to_status
                ? ` · ${ev.from_status ?? "—"} → ${ev.to_status ?? "—"}`
                : null}
              {ev.note ? <p>{ev.note}</p> : null}
              {ev.evidence_text ? <p>{ev.evidence_text}</p> : null}
              {ev.evidence_url ? (
                <a
                  href={ev.evidence_url}
                  target="_blank"
                  rel="noreferrer"
                  className="font-semibold text-coral underline-offset-2 hover:underline"
                >
                  {ev.evidence_url}
                </a>
              ) : null}
            </li>
          ))}
        </ol>
      ) : null}
    </li>
  );
}
