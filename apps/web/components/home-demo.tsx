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
        className="rf-btn-secondary px-7 py-3"
        onClick={() => setOpen(true)}
      >
        {ctaLabel}
      </button>

      {open ? (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-ink/40 p-4"
          role="presentation"
          onClick={() => setOpen(false)}
        >
          <div
            className="rf-card max-h-[90vh] w-full max-w-2xl overflow-y-auto p-6"
            role="dialog"
            aria-modal="true"
            aria-labelledby={titleId}
            onClick={(event) => event.stopPropagation()}
          >
            <div className="flex items-start justify-between gap-4">
              <div>
                <h2 id={titleId} className="font-display text-lg font-medium text-ink">
                  {heading}
                </h2>
                <p className="mt-1 text-sm font-medium text-ink/55">{summary}</p>
              </div>
              <button
                ref={closeRef}
                type="button"
                className="rounded-full px-3 py-2 text-sm font-bold text-ink/50 hover:bg-sand"
                onClick={() => setOpen(false)}
                aria-label={closeLabel}
              >
                ✕
              </button>
            </div>

            <div className="mt-4 grid gap-3">
              <section className="rounded-2xl border-2 border-ink/6 bg-sand/40 p-4">
                <h3 className="text-sm font-bold text-ink">{problemTitle}</h3>
                <p className="mt-2 text-sm text-ink/80">{problem}</p>
                <p className="mt-2 text-xs font-medium text-ink/40">{source}</p>
              </section>

              <section className="rounded-2xl border-2 border-ink/6 bg-sand/40 p-4">
                <h3 className="text-sm font-bold text-ink">{historyTitle}</h3>
                <ul className="mt-2 grid gap-2 text-sm text-ink/80">
                  {history.map((item) => (
                    <li key={item}>• {item}</li>
                  ))}
                </ul>
              </section>

              <section className="rounded-2xl border-2 border-ink/6 bg-sand/40 p-4">
                <h3 className="text-sm font-bold text-ink">{evidenceTitle}</h3>
                <p className="mt-2 rounded-xl bg-white p-3 text-sm text-ink">{evidence}</p>
              </section>

              <section className="rounded-2xl border-2 border-ink/6 bg-sand/40 p-4">
                <h3 className="text-sm font-bold text-ink">{askTitle}</h3>
                <p className="mt-2 text-sm text-ink/80">
                  <span className="font-medium">Q:</span> {askQ}
                </p>
                <p className="mt-3 rounded-xl bg-white p-3 text-sm text-ink">
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
