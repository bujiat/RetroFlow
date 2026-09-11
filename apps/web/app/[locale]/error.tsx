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
      <p className="text-4xl">😵</p>
      <h1 className="rf-h1">{t("title")}</h1>
      <p className="rf-lede">{t("body")}</p>
      {error.digest ? <p className="text-xs text-ink/35">{error.digest}</p> : null}
      <button
        type="button"
        onClick={() => retry()}
        className="rf-btn-primary px-4 py-2"
      >
        {t("retry")}
      </button>
    </div>
  );
}
