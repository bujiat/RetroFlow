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
  const [asked, setAsked] = useState<string | null>(null);

  async function ask(nextQuestion?: string) {
    const q = (nextQuestion ?? question).trim();
    if (q.length < 2 || pending) return;
    setQuestion(q);
    setAsked(q);
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
    <div className="flex min-h-[calc(100vh-6rem)] flex-col">
      <div className="flex items-center gap-3">
        <div className="flex size-12 items-center justify-center rounded-2xl bg-plum/15 text-2xl">
          🤖
        </div>
        <div>
          <div className="flex items-center gap-2">
            <h1 className="rf-h1 text-[1.75rem]">{t("title")}</h1>
            <span className="size-2 rounded-full bg-mint" aria-hidden />
          </div>
          <p className="rf-lede">{t("lede")}</p>
        </div>
      </div>

      <div className="mt-8 flex flex-1 flex-col gap-4">
        {asked ? (
          <div className="flex justify-end">
            <p className="max-w-[80%] rounded-3xl rounded-br-md bg-coral px-4 py-3 text-sm font-semibold text-white">
              {asked}
            </p>
          </div>
        ) : null}

        {pending ? (
          <div className="flex items-start gap-3">
            <span className="flex size-9 items-center justify-center rounded-full bg-plum/15">🤖</span>
            <p className="rf-card px-4 py-3 text-sm text-ink/50">{t("asking")}</p>
          </div>
        ) : null}

        {error ? (
          <p role="alert" className="text-sm font-semibold text-coral">
            {error}
          </p>
        ) : null}

        {result && !pending ? (
          <div className="flex items-start gap-3">
            <span className="flex size-9 shrink-0 items-center justify-center rounded-full bg-plum/15">
              🤖
            </span>
            <div className="rf-card min-w-0 flex-1 space-y-4 p-5">
              <div className="flex items-center gap-2">
                <h2 className="text-sm font-bold text-ink">{t("answerHeading")}</h2>
                <span
                  className={
                    result.status === "answered"
                      ? "rf-chip bg-mint/20 text-[#2a9a74]"
                      : "rf-chip bg-sun/20 text-[#c48410]"
                  }
                >
                  {result.status === "answered" ? t("statusAnswered") : t("statusInsufficient")}
                </span>
              </div>
              <p className="whitespace-pre-wrap text-sm leading-relaxed text-ink">{result.answer}</p>

              {result.citations.length > 0 ? (
                <div className="space-y-2 border-t border-ink/8 pt-4">
                  <h3 className="text-xs font-bold tracking-wide text-ink/40 uppercase">
                    {t("citationsHeading")}
                  </h3>
                  <ul className="space-y-2">
                    {result.citations.map((c) => (
                      <li key={c.id} className="rounded-2xl bg-sand/60 px-3 py-2 text-sm">
                        <div className="flex flex-wrap items-baseline justify-between gap-2">
                          <span className="font-bold text-ink">{c.title}</span>
                          <span className="text-xs font-medium text-ink/40">{c.source_type}</span>
                        </div>
                        <p className="mt-1 text-xs leading-relaxed text-ink/60">{c.excerpt}</p>
                        {c.source_type === "action" ? (
                          <Link
                            href="/actions/board"
                            className="mt-2 inline-block text-xs font-bold text-plum underline-offset-2 hover:underline"
                          >
                            {t("openSource")}
                          </Link>
                        ) : null}
                        {c.source_type === "cluster" ? (
                          <Link
                            href="/trends"
                            className="mt-2 inline-block text-xs font-bold text-plum underline-offset-2 hover:underline"
                          >
                            {t("openSource")}
                          </Link>
                        ) : null}
                        {c.retro_id && (c.source_type === "chunk" || c.source_type === "problem") ? (
                          <Link
                            href={`/retro/${c.retro_id}/confirm`}
                            className="mt-2 inline-block text-xs font-bold text-plum underline-offset-2 hover:underline"
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
          </div>
        ) : null}
      </div>

      <div className="sticky bottom-0 mt-8 space-y-3 bg-cream/90 py-4 backdrop-blur-sm">
        <div className="flex flex-wrap gap-2">
          {EXAMPLE_KEYS.map((key) => (
            <button
              key={key}
              type="button"
              disabled={pending}
              onClick={() => void ask(t(`examples.${key}`))}
              className="rf-btn-secondary px-3 py-1.5 text-xs disabled:opacity-50"
            >
              {t(`examples.${key}`)}
            </button>
          ))}
        </div>
        <form
          className="rf-card flex items-end gap-2 p-3"
          onSubmit={(e) => {
            e.preventDefault();
            void ask();
          }}
        >
          <label className="sr-only" htmlFor="assistant-q">
            {t("questionLabel")}
          </label>
          <textarea
            id="assistant-q"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            rows={2}
            placeholder={t("placeholder")}
            className="rf-input min-h-[2.75rem] resize-none border-0 bg-transparent py-2"
          />
          <button
            type="submit"
            disabled={pending || question.trim().length < 2}
            className="rf-btn-primary shrink-0 px-5 py-2"
          >
            {pending ? t("asking") : t("ask")}
          </button>
        </form>
      </div>
    </div>
  );
}
