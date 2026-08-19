"use client";

import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";

import { Link, useRouter } from "@/i18n/navigation";
import {
  getMyWeek,
  listActionEvents,
  listActions,
  patchActionStatus,
  rejectAction,
  submitEvidence,
  verifyAction,
  type ActionEvent,
  type ActionItem,
  type MyWeek,
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

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-4">
        <h1 className="text-xl font-semibold tracking-tight text-zinc-950">{t("title")}</h1>
        <div className="flex items-center gap-4 text-sm">
          <Link href="/weekly-review" className="text-zinc-600 hover:text-zinc-950">
            {t("goWeeklyReview")}
          </Link>
          <Link href="/retros" className="text-zinc-600 hover:text-zinc-950">
            {t("backRetros")}
          </Link>
        </div>
      </div>

      <div
        role="tablist"
        aria-label={t("title")}
        className="flex gap-1 border-b border-zinc-200 text-sm"
      >
        <TabButton active={tab === "week"} onClick={() => setTab("week")}>
          {t("tabWeek")}
        </TabButton>
        <TabButton active={tab === "all"} onClick={() => setTab("all")}>
          {t("tabAll")}
        </TabButton>
      </div>

      {error ? (
        <p role="alert" className="text-sm text-red-600">
          {error}
        </p>
      ) : null}

      {tab === "week" ? (
        week === null ? (
          <p className="text-sm text-zinc-500">{t("loading")}</p>
        ) : weekEmpty ? (
          <p className="text-sm text-zinc-600">{t("weekEmpty")}</p>
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
        <p className="text-sm text-zinc-500">{t("loading")}</p>
      ) : items.length === 0 ? (
        <p className="text-sm text-zinc-600">{t("empty")}</p>
      ) : (
        <ul className="divide-y border-y border-zinc-200">
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
          ? "-mb-px border-b-2 border-zinc-950 px-3 py-2 font-medium text-zinc-950"
          : "px-3 py-2 text-zinc-500 hover:text-zinc-800"
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
    <section className="space-y-2">
      <h2 className="text-sm font-medium text-zinc-800">
        {title}
        <span className="ml-2 font-normal text-zinc-500">{items.length}</span>
      </h2>
      <ul className="divide-y border-y border-zinc-200">
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

  return (
    <li className="space-y-3 py-4">
      <div className="space-y-1">
        <p className="font-medium text-zinc-950">{item.title}</p>
        <p className="text-sm text-zinc-600">{item.description}</p>
        <p className="text-sm text-zinc-500">
          {item.owner} · {t("due")} {item.due_date} · {item.status}
        </p>
        <p className="text-sm text-zinc-600">
          <span className="font-medium">{t("successCriteria")}: </span>
          {item.success_criteria}
        </p>
      </div>

      {rowError ? (
        <p role="alert" className="text-sm text-red-600">
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
              className="rounded-md bg-zinc-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-zinc-800 disabled:opacity-60"
            >
              {t("start")}
            </button>
          ) : null}

          {item.status === "in_progress" ? (
            <button
              type="button"
              disabled={pending}
              onClick={() => void run(() => patchActionStatus(item.id, "open"))}
              className="rounded-md border border-zinc-300 bg-white px-3 py-1.5 text-sm text-zinc-800 hover:bg-zinc-50 disabled:opacity-60"
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
                className="rounded-md border border-zinc-300 bg-white px-3 py-1.5 text-sm text-zinc-800 hover:bg-zinc-50 disabled:opacity-60"
              >
                {t("submitEvidence")}
              </button>
              <button
                type="button"
                disabled={pending}
                onClick={() => void run(() => patchActionStatus(item.id, "cancelled"))}
                className="rounded-md border border-zinc-300 bg-white px-3 py-1.5 text-sm text-zinc-600 hover:bg-zinc-50 disabled:opacity-60"
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
                onClick={() => void run(() => verifyAction(item.id))}
                className="rounded-md bg-zinc-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-zinc-800 disabled:opacity-60"
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
                className="rounded-md border border-zinc-300 bg-white px-3 py-1.5 text-sm text-zinc-800 hover:bg-zinc-50 disabled:opacity-60"
              >
                {t("reject")}
              </button>
            </>
          ) : null}

          <button
            type="button"
            disabled={pending}
            onClick={() => void loadEvents()}
            className="rounded-md border border-transparent px-3 py-1.5 text-sm text-zinc-600 hover:text-zinc-950"
          >
            {events ? t("hideTimeline") : t("showTimeline")}
          </button>
        </div>
      ) : (
        <button
          type="button"
          onClick={() => void loadEvents()}
          className="text-sm text-zinc-600 hover:text-zinc-950"
        >
          {events ? t("hideTimeline") : t("showTimeline")}
        </button>
      )}

      {showEvidence ? (
        <form
          className="space-y-2 rounded-md border border-zinc-200 bg-zinc-50 p-3"
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
            <span className="font-medium text-zinc-800">{t("completionNote")}</span>
            <textarea
              required
              value={note}
              onChange={(e) => setNote(e.target.value)}
              rows={2}
              className="w-full rounded-md border border-zinc-300 bg-white px-2 py-1.5 outline-none focus:border-zinc-900"
            />
          </label>
          <label className="block space-y-1 text-sm">
            <span className="font-medium text-zinc-800">{t("evidenceText")}</span>
            <textarea
              value={evidenceText}
              onChange={(e) => setEvidenceText(e.target.value)}
              rows={2}
              className="w-full rounded-md border border-zinc-300 bg-white px-2 py-1.5 outline-none focus:border-zinc-900"
            />
          </label>
          <label className="block space-y-1 text-sm">
            <span className="font-medium text-zinc-800">{t("evidenceUrl")}</span>
            <input
              value={evidenceUrl}
              onChange={(e) => setEvidenceUrl(e.target.value)}
              placeholder="https://"
              className="w-full rounded-md border border-zinc-300 bg-white px-2 py-1.5 outline-none focus:border-zinc-900"
            />
          </label>
          <p className="text-xs text-zinc-500">{t("evidenceHint")}</p>
          <button
            type="submit"
            disabled={pending}
            className="rounded-md bg-zinc-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-zinc-800 disabled:opacity-60"
          >
            {t("applyVerify")}
          </button>
        </form>
      ) : null}

      {showReject ? (
        <form
          className="space-y-2 rounded-md border border-zinc-200 bg-zinc-50 p-3"
          onSubmit={(e) => {
            e.preventDefault();
            void run(() => rejectAction(item.id, rejectReason));
          }}
        >
          <label className="block space-y-1 text-sm">
            <span className="font-medium text-zinc-800">{t("rejectReason")}</span>
            <textarea
              required
              value={rejectReason}
              onChange={(e) => setRejectReason(e.target.value)}
              rows={2}
              className="w-full rounded-md border border-zinc-300 bg-white px-2 py-1.5 outline-none focus:border-zinc-900"
            />
          </label>
          <button
            type="submit"
            disabled={pending}
            className="rounded-md bg-zinc-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-zinc-800 disabled:opacity-60"
          >
            {t("confirmReject")}
          </button>
        </form>
      ) : null}

      {events ? (
        <ol className="space-y-2 border-l border-zinc-200 pl-3 text-sm text-zinc-600">
          {events.map((ev) => (
            <li key={ev.id}>
              <span className="font-medium text-zinc-800">{ev.event_type}</span>
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
                  className="text-zinc-900 underline-offset-2 hover:underline"
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
