"use client";

import { useEffect, useId, useRef, useState } from "react";

type HomeDemoProps = {
  ctaLabel: string;
  closeLabel: string;
  heading: string;
  summary: string;
  problemTitle: string;
  problem: string;
  source: string;
  historyTitle: string;
  history: string[];
  evidenceTitle: string;
  evidence: string;
  askTitle: string;
  askQ: string;
  askA: string;
};

export function HomeDemo({
  ctaLabel,
  closeLabel,
  heading,
  summary,
  problemTitle,
  problem,
  source,
  historyTitle,
  history,
  evidenceTitle,
  evidence,
  askTitle,
  askQ,
  askA,
}: HomeDemoProps) {
  const [open, setOpen] = useState(false);
  const titleId = useId();
  const closeRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!open) return;

    closeRef.current?.focus();

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };

    document.addEventListener("keydown", onKeyDown);
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";

    return () => {
      document.removeEventListener("keydown", onKeyDown);
      document.body.style.overflow = previousOverflow;
    };
  }, [open]);

  return (
    <>
      <button
        type="button"
        className="rounded-md border border-zinc-300 px-6 py-2.5 text-sm font-medium text-zinc-800 transition-colors hover:border-zinc-400 hover:bg-zinc-50"
        onClick={() => setOpen(true)}
      >
        {ctaLabel}
      </button>

      {open ? (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-zinc-950/45 p-4"
          role="presentation"
          onClick={() => setOpen(false)}
        >
          <div
            className="max-h-[90vh] w-full max-w-2xl overflow-y-auto rounded-lg border border-zinc-200 bg-white p-5"
            role="dialog"
            aria-modal="true"
            aria-labelledby={titleId}
            onClick={(event) => event.stopPropagation()}
          >
            <div className="flex items-start justify-between gap-4">
              <div>
                <h2 id={titleId} className="text-sm font-semibold text-zinc-900">
                  {heading}
                </h2>
                <p className="mt-1 text-sm text-zinc-600">{summary}</p>
              </div>
              <button
                ref={closeRef}
                type="button"
                className="rounded-md px-3 py-2 text-sm text-zinc-600 hover:bg-zinc-100"
                onClick={() => setOpen(false)}
                aria-label={closeLabel}
              >
                ✕
              </button>
            </div>

            <div className="mt-4 grid gap-3">
              <section className="rounded-md border border-zinc-200 p-4">
                <h3 className="text-sm font-semibold text-zinc-900">{problemTitle}</h3>
                <p className="mt-2 text-sm text-zinc-700">{problem}</p>
                <p className="mt-2 text-xs text-zinc-500">{source}</p>
              </section>

              <section className="rounded-md border border-zinc-200 p-4">
                <h3 className="text-sm font-semibold text-zinc-900">{historyTitle}</h3>
                <ul className="mt-2 grid gap-2 text-sm text-zinc-700">
                  {history.map((item) => (
                    <li key={item}>• {item}</li>
                  ))}
                </ul>
              </section>

              <section className="rounded-md border border-zinc-200 p-4">
                <h3 className="text-sm font-semibold text-zinc-900">{evidenceTitle}</h3>
                <p className="mt-2 rounded-md bg-zinc-50 p-3 text-sm text-zinc-800">{evidence}</p>
              </section>

              <section className="rounded-md border border-zinc-200 p-4">
                <h3 className="text-sm font-semibold text-zinc-900">{askTitle}</h3>
                <p className="mt-2 text-sm text-zinc-700">
                  <span className="font-medium">Q:</span> {askQ}
                </p>
                <p className="mt-3 rounded-md bg-zinc-50 p-3 text-sm text-zinc-800">
                  <span className="font-medium">A:</span> {askA}
                </p>
              </section>
            </div>
          </div>
        </div>
      ) : null}
    </>
  );
}
