"use client";

import { useTranslations } from "next-intl";
import { useState } from "react";

import { Link, useRouter } from "@/i18n/navigation";
import { failedRequestMessage, redirectToLoginIfUnauthorized } from "@/lib/api/client";
import { queryAssistant } from "@/lib/api/assistant";
import type { AssistantQueryResponse } from "@/types";

const EXAMPLE_KEYS = ["exDeploy", "exEvidence", "exRecurring"] as const;

export function AssistantView() {
  const t = useTranslations("assistant");
  const tCommon = useTranslations("common");
  const router = useRouter();
  const [question, setQuestion] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<AssistantQueryResponse | null>(null);

  async function ask(nextQuestion?: string) {
    const q = (nextQuestion ?? question).trim();
    if (q.length < 2 || pending) return;
    setQuestion(q);
    setPending(true);
    setError(null);
    try {
      const data = await queryAssistant(q);
      setResult(data);
    } catch (err) {
      if (redirectToLoginIfUnauthorized(err, router.replace)) return;
      setError(
        failedRequestMessage(err, {
          network: tCommon("networkError"),
          fallback: t("askFailed"),
        }),
      );
      setResult(null);
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="relative space-y-8">
      <div
        aria-hidden
        className="pointer-events-none absolute -left-8 -top-10 h-40 w-40 rounded-full bg-teal-200/40 blur-3xl"
      />
      <div
        aria-hidden
        className="pointer-events-none absolute -right-6 top-16 h-32 w-32 rounded-full bg-amber-200/35 blur-3xl"
      />

      <div className="relative space-y-2">
        <p className="text-xs font-medium uppercase tracking-[0.18em] text-teal-800/80">
          {t("eyebrow")}
        </p>
        <h1 className="text-2xl font-semibold tracking-tight text-zinc-950">{t("title")}</h1>
        <p className="max-w-xl text-sm leading-relaxed text-zinc-600">{t("lede")}</p>
      </div>

      <form
        className="relative space-y-3 rounded-2xl border border-teal-900/10 bg-white/80 p-4 shadow-sm backdrop-blur"
        onSubmit={(e) => {
          e.preventDefault();
          void ask();
        }}
      >
        <label className="block text-sm font-medium text-zinc-800" htmlFor="assistant-q">
          {t("questionLabel")}
        </label>
        <textarea
          id="assistant-q"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          rows={3}
          placeholder={t("placeholder")}
          className="w-full resize-y rounded-xl border border-zinc-200 bg-zinc-50/80 px-3 py-2 text-sm text-zinc-900 outline-none ring-teal-700/30 placeholder:text-zinc-400 focus:bg-white focus:ring-2"
        />
        <div className="flex flex-wrap items-center gap-2">
          <button
            type="submit"
            disabled={pending || question.trim().length < 2}
            className="rounded-full bg-zinc-950 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
          >
            {pending ? t("asking") : t("ask")}
          </button>
        </div>
      </form>

      <div className="relative flex flex-wrap gap-2">
        {EXAMPLE_KEYS.map((key) => (
          <button
            key={key}
            type="button"
            disabled={pending}
            onClick={() => void ask(t(`examples.${key}`))}
            className="rounded-full border border-zinc-200 bg-white px-3 py-1.5 text-xs text-zinc-700 transition hover:border-teal-700/40 hover:text-teal-900 disabled:opacity-50"
          >
            {t(`examples.${key}`)}
          </button>
        ))}
      </div>

      {error ? (
        <p role="alert" className="text-sm text-red-600">
          {error}
        </p>
      ) : null}

      {result ? (
        <div className="relative space-y-4 rounded-2xl border border-zinc-200 bg-white p-5">
          <div className="flex items-center gap-2">
            <h2 className="text-sm font-medium text-zinc-900">{t("answerHeading")}</h2>
            <span
              className={
                result.status === "answered"
                  ? "rounded-full bg-teal-50 px-2 py-0.5 text-xs text-teal-900"
                  : "rounded-full bg-amber-50 px-2 py-0.5 text-xs text-amber-900"
              }
            >
              {result.status === "answered" ? t("statusAnswered") : t("statusInsufficient")}
            </span>
          </div>
          <p className="whitespace-pre-wrap text-sm leading-relaxed text-zinc-800">
            {result.answer}
          </p>

          {result.citations.length > 0 ? (
            <div className="space-y-2 border-t border-zinc-100 pt-4">
              <h3 className="text-xs font-medium uppercase tracking-wide text-zinc-500">
                {t("citationsHeading")}
              </h3>
              <ul className="space-y-2">
                {result.citations.map((c) => (
                  <li key={c.id} className="rounded-xl bg-zinc-50 px-3 py-2 text-sm">
                    <div className="flex flex-wrap items-baseline justify-between gap-2">
                      <span className="font-medium text-zinc-900">{c.title}</span>
                      <span className="text-xs text-zinc-500">{c.source_type}</span>
                    </div>
                    <p className="mt-1 text-xs leading-relaxed text-zinc-600">{c.excerpt}</p>
                    {c.source_type === "action" ? (
                      <Link
                        href="/actions/board"
                        className="mt-2 inline-block text-xs text-teal-800 underline-offset-2 hover:underline"
                      >
                        {t("openSource")}
                      </Link>
                    ) : null}
                    {c.source_type === "cluster" ? (
                      <Link
                        href="/trends"
                        className="mt-2 inline-block text-xs text-teal-800 underline-offset-2 hover:underline"
                      >
                        {t("openSource")}
                      </Link>
                    ) : null}
                    {c.retro_id &&
                    (c.source_type === "chunk" || c.source_type === "problem") ? (
                      <Link
                        href={`/retro/${c.retro_id}/confirm`}
                        className="mt-2 inline-block text-xs text-teal-800 underline-offset-2 hover:underline"
                      >
                        {t("openSource")}
                      </Link>
                    ) : null}
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
