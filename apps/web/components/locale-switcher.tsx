"use client";

import { useLocale, useTranslations } from "next-intl";

import { usePathname, useRouter } from "@/i18n/navigation";
import type { AppLocale } from "@/i18n/routing";

export function LocaleSwitcher({ variant = "light" }: { variant?: "light" | "dark" }) {
  const locale = useLocale() as AppLocale;
  const pathname = usePathname();
  const router = useRouter();
  const t = useTranslations("common");

  const switchLocale = (next: AppLocale) => {
    if (next === locale) return;
    router.replace(pathname, { locale: next });
  };

  const muted = variant === "dark" ? "text-cream/40" : "text-ink/40";
  const active = variant === "dark" ? "font-bold text-cream" : "font-bold text-ink";

  return (
    <div className="flex flex-wrap items-center justify-center gap-x-1 text-sm">
      <button
        type="button"
        className={locale === "zh-CN" ? active : muted}
        onClick={() => switchLocale("zh-CN")}
        aria-pressed={locale === "zh-CN"}
      >
        {t("localeZh")}
      </button>
      <span className={`mx-2 ${muted}`}>|</span>
      <button
        type="button"
        className={locale === "en" ? active : muted}
        onClick={() => switchLocale("en")}
        aria-pressed={locale === "en"}
      >
        {t("localeEn")}
      </button>
    </div>
  );
}
