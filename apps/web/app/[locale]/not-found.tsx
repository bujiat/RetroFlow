import { getTranslations } from "next-intl/server";

import { Link } from "@/i18n/navigation";

export default async function LocaleNotFound() {
  const t = await getTranslations("notFoundPage");

  return (
    <div className="mx-auto max-w-lg space-y-3 px-6 py-16">
      <h1 className="text-xl font-semibold text-zinc-950">{t("title")}</h1>
      <p className="text-sm text-zinc-600">{t("body")}</p>
      <Link href="/" className="text-sm text-zinc-900 underline-offset-2 hover:underline">
        {t("home")}
      </Link>
    </div>
  );
}
