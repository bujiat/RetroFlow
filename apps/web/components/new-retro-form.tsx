"use client";

import { useTranslations } from "next-intl";
import { useId, useState, type FormEvent } from "react";

import { Link, useRouter } from "@/i18n/navigation";
import { redirectToLoginIfUnauthorized } from "@/lib/api/client";
import { analyzeRetro, createRetro, type RetroType } from "@/lib/api/retros";

function todayIsoDate(): string {
  const now = new Date();
  const y = now.getFullYear();
  const m = String(now.getMonth() + 1).padStart(2, "0");
  const d = String(now.getDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
}

export function NewRetroForm() {
  const t = useTranslations("retroNew");
  const router = useRouter();

  const typeId = useId();
  const titleId = useId();
  const dateId = useId();
  const contentId = useId();

  const typeOptions: { value: RetroType; label: string }[] = [
    { value: "sprint", label: t("typeSprint") },
    { value: "incident", label: t("typeIncident") },
    { value: "release", label: t("typeRelease") },
  ];

  const [type, setType] = useState<RetroType>("sprint");
  const [title, setTitle] = useState("");
  const [reviewDate, setReviewDate] = useState(todayIsoDate);
  const [rawContent, setRawContent] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const [phase, setPhase] = useState<"idle" | "saving" | "analyzing">("idle");

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);

    const trimmedTitle = title.trim();
    const trimmedContent = rawContent.trim();

    if (!trimmedTitle) {
      setError(t("titleRequired"));
      return;
    }
    if (!reviewDate) {
      setError(t("dateRequired"));
      return;
    }
    if (!trimmedContent) {
      setError(t("contentRequired"));
      return;
    }

    setPending(true);
    setPhase("saving");
    try {
      const created = await createRetro({
        type,
        title: trimmedTitle,
        review_date: reviewDate,
        raw_content: trimmedContent,
      });

      setPhase("analyzing");
      try {
        await analyzeRetro(created.id);
      } catch (analyzeErr) {
        if (redirectToLoginIfUnauthorized(analyzeErr, router.replace)) return;
        // 分析失败也进确认页：展示 analysis_failed / 允许重试
      }

      router.push(`/retro/${created.id}/confirm`);
    } catch (err) {
      if (redirectToLoginIfUnauthorized(err, router.replace)) return;
      setError(t("createFailed"));
    } finally {
      setPending(false);
      setPhase("idle");
    }
  }

  const submitLabel =
    phase === "analyzing" ? t("analyzing") : phase === "saving" ? t("saving") : t("submitAnalyze");

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <div>
        <Link href="/retros" className="text-sm text-zinc-600 hover:text-zinc-950">
          {t("back")}
        </Link>
        <h1 className="mt-3 text-xl font-semibold tracking-tight text-zinc-950">
          {t("pageTitle")}
        </h1>
      </div>

      <form onSubmit={onSubmit} className="space-y-5">
        <fieldset className="space-y-2">
          <legend className="text-sm font-medium text-zinc-900">{t("typeLabel")}</legend>
          <div className="flex flex-wrap gap-4">
            {typeOptions.map((option) => (
              <label
                key={option.value}
                className="flex cursor-pointer items-center gap-2 text-sm text-zinc-800"
              >
                <input
                  type="radio"
                  name={typeId}
                  value={option.value}
                  checked={type === option.value}
                  onChange={() => setType(option.value)}
                />
                {option.label}
              </label>
            ))}
          </div>
        </fieldset>

        <div className="space-y-1.5">
          <label htmlFor={titleId} className="block text-sm font-medium text-zinc-900">
            {t("titleLabel")}
          </label>
          <input
            id={titleId}
            type="text"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            maxLength={200}
            className="w-full rounded-md border border-zinc-300 px-3 py-2 text-sm outline-none focus:border-zinc-900"
            autoComplete="off"
          />
        </div>

        <div className="space-y-1.5">
          <label htmlFor={dateId} className="block text-sm font-medium text-zinc-900">
            {t("dateLabel")}
          </label>
          <input
            id={dateId}
            type="date"
            value={reviewDate}
            onChange={(e) => setReviewDate(e.target.value)}
            className="w-full rounded-md border border-zinc-300 px-3 py-2 text-sm outline-none focus:border-zinc-900"
          />
        </div>

        <div className="space-y-1.5">
          <label htmlFor={contentId} className="block text-sm font-medium text-zinc-900">
            {t("contentLabel")}
          </label>
          <textarea
            id={contentId}
            value={rawContent}
            onChange={(e) => setRawContent(e.target.value)}
            rows={12}
            placeholder={t("contentPlaceholder")}
            className="w-full resize-y rounded-md border border-zinc-300 px-3 py-2 text-sm outline-none focus:border-zinc-900"
          />
        </div>

        {error ? <p className="text-sm text-red-600">{error}</p> : null}

        <button
          type="submit"
          disabled={pending}
          className="w-full rounded-md bg-zinc-900 px-3 py-2.5 text-sm font-medium text-white hover:bg-zinc-800 disabled:opacity-60"
        >
          {pending ? submitLabel : t("submitAnalyze")}
        </button>
      </form>
    </div>
  );
}
