import { getTranslations } from "next-intl/server";

import { Link } from "@/i18n/navigation";

export default async function LocaleNotFound() {
  const t = await getTranslations("notFoundPage");

  return (
    <div className="mx-auto max-w-lg space-y-3 px-6 py-16">
      <p className="text-4xl">🧭</p>
      <h1 className="rf-h1">{t("title")}</h1>
      <p className="rf-lede">{t("body")}</p>
      <Link href="/" className="text-sm font-bold text-coral underline-offset-2 hover:underline">
        {t("home")}
      </Link>
    </div>
  );
}
