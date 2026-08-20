import { getTranslations, setRequestLocale } from "next-intl/server";

import { HomeDemo } from "@/components/home-demo";
import { LocaleSwitcher } from "@/components/locale-switcher";
import { Link } from "@/i18n/navigation";
import type { LocaleParams } from "@/types";

type Props = {
  params: LocaleParams;
};

export default async function HomePage({ params }: Props) {
  const { locale } = await params;
  setRequestLocale(locale);

  const t = await getTranslations("home");
  const tc = await getTranslations("common");
  const questions = t.raw("questions") as string[];
  const demoHistory = t.raw("demoHistory") as string[];

  return (
    <div className="min-h-screen bg-[linear-gradient(180deg,#fafafa_0%,#ffffff_45%,#f4f4f5_100%)]">
      <header className="px-6 py-4">
        <div className="mx-auto flex max-w-5xl items-center justify-between">
          <div className="text-sm font-semibold tracking-wide text-zinc-900">{tc("brand")}</div>
          <LocaleSwitcher />
        </div>
      </header>

      <main className="mx-auto flex max-w-3xl flex-col items-center px-6 pb-20 pt-16 text-center sm:pt-24">
        <h1 className="text-balance text-3xl font-semibold tracking-tight text-zinc-950 sm:text-4xl">
          {t("title")}
        </h1>
        <p className="mt-4 max-w-xl text-pretty text-base text-zinc-600 sm:text-lg">{t("subtitle")}</p>

        <div className="mt-10 flex flex-wrap items-center justify-center gap-3">
          <Link
            href="/login"
            className="rounded-md bg-zinc-900 px-6 py-2.5 text-sm font-medium text-white transition-colors hover:bg-zinc-800"
          >
            {t("ctaPrimary")}
          </Link>
          <HomeDemo
            ctaLabel={t("ctaSecondary")}
            closeLabel={tc("close")}
            heading={t("demoHeading")}
            summary={t("demoSummary")}
            problemTitle={t("demoProblemTitle")}
            problem={t("demoProblem")}
            source={t("demoSource")}
            historyTitle={t("demoHistoryTitle")}
            history={demoHistory}
            evidenceTitle={t("demoEvidenceTitle")}
            evidence={t("demoEvidence")}
            askTitle={t("demoAskTitle")}
            askQ={t("demoAskQ")}
            askA={t("demoAskA")}
          />
        </div>

        <p className="mt-4 text-sm text-zinc-500">{t("demoAccount")}</p>

        <ul className="mt-14 grid w-full gap-3 text-left text-sm text-zinc-700 sm:grid-cols-3 sm:gap-4">
          {questions.map((item) => (
            <li
              key={item}
              className="rounded-md border border-zinc-200/80 bg-white/70 px-4 py-3 leading-relaxed"
            >
              {item}
            </li>
          ))}
        </ul>
      </main>
    </div>
  );
}
