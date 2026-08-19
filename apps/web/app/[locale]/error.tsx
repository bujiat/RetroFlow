"use client";

import { useTranslations } from "next-intl";

export default function LocaleError({
  error,
  retry,
}: {
  error: Error & { digest?: string };
  retry: () => void;
}) {
  const t = useTranslations("errorPage");

  return (
    <div className="mx-auto max-w-lg space-y-3 px-6 py-16">
      <h1 className="text-xl font-semibold text-zinc-950">{t("title")}</h1>
      <p className="text-sm text-zinc-600">{t("body")}</p>
      {error.digest ? <p className="text-xs text-zinc-400">{error.digest}</p> : null}
      <button
        type="button"
        onClick={() => retry()}
        className="rounded-md bg-zinc-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-zinc-800"
      >
        {t("retry")}
      </button>
    </div>
  );
}
