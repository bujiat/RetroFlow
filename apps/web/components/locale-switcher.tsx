"use client";

import { useLocale, useTranslations } from "next-intl";

import { usePathname, useRouter } from "@/i18n/navigation";
import type { AppLocale } from "@/i18n/routing";

export function LocaleSwitcher() {
  const locale = useLocale() as AppLocale;
  const pathname = usePathname();
  const router = useRouter();
  const t = useTranslations("common");

  const switchLocale = (next: AppLocale) => {
    if (next === locale) return;
    router.replace(pathname, { locale: next });
  };

  return (
    <div className="flex items-center text-sm">
      <button
        type="button"
        className={locale === "zh-CN" ? "font-medium text-zinc-900" : "text-zinc-600"}
        onClick={() => switchLocale("zh-CN")}
        aria-pressed={locale === "zh-CN"}
      >
        {t("localeZh")}
      </button>
      <span className="mx-2 text-zinc-400">|</span>
      <button
        type="button"
        className={locale === "en" ? "font-medium text-zinc-900" : "text-zinc-600"}
        onClick={() => switchLocale("en")}
        aria-pressed={locale === "en"}
      >
        {t("localeEn")}
      </button>
    </div>
  );
}
