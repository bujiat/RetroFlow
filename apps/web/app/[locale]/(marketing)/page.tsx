import { getTranslations, setRequestLocale } from "next-intl/server";

import { HomeDemo } from "@/components/home-demo";
import { LocaleSwitcher } from "@/components/locale-switcher";
import { Link } from "@/i18n/navigation";
import type { LocaleParams } from "@/types";

type Props = {
  params: LocaleParams;
};

type Feature = {
  icon: string;
  color: string;
  title: string;
  desc: string;
};

export default async function HomePage({ params }: Props) {
  const { locale } = await params;
  setRequestLocale(locale);

  const t = await getTranslations("home");
  const tc = await getTranslations("common");
  const demoHistory = t.raw("demoHistory") as string[];
  const features = t.raw("features") as Feature[];

  return (
    <div className="relative min-h-screen overflow-hidden bg-cream">
      <div className="rf-blob -top-24 -right-16 size-[28rem] bg-[radial-gradient(circle,#FF6B4A_0%,transparent_70%)] opacity-20" />
      <div className="rf-blob top-40 -left-20 size-80 bg-[radial-gradient(circle,#FFB830_0%,transparent_70%)] opacity-25" />
      <div className="rf-blob right-[18%] bottom-40 size-56 bg-[radial-gradient(circle,#3ECFA0_0%,transparent_70%)] opacity-15" />

      <header className="relative z-10 px-6 py-5">
        <div className="mx-auto flex max-w-5xl items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="flex size-10 items-center justify-center rounded-2xl bg-linear-to-br from-coral to-sun text-lg text-white">
              🔁
            </div>
            <div>
              <div className="text-sm font-extrabold text-ink">{tc("brand")}</div>
              <div className="text-[10px] font-medium tracking-widest text-ink/35">RETRO STUDIO</div>
            </div>
          </div>
          <div className="flex items-center gap-4">
            <LocaleSwitcher />
            <Link href="/login" className="rf-btn-primary hidden px-5 py-2 sm:inline-flex">
              {t("ctaPrimary")}
            </Link>
          </div>
        </div>
      </header>

      <main className="relative z-10 mx-auto max-w-5xl px-6 pb-8 pt-10 sm:pt-16">
        <div className="mx-auto max-w-3xl text-center">
          <p className="rf-chip mx-auto inline-flex bg-sand text-ink/60">{t("badge")}</p>
          <h1 className="font-display mt-6 text-balance text-4xl font-medium tracking-tight text-ink sm:text-6xl">
            {t("titleLead")}
            <br />
            <em className="text-coral italic">{t("titleAccent")}</em>
          </h1>
          <p className="mt-5 max-w-xl mx-auto text-pretty text-base font-medium text-ink/55 sm:text-lg">
            {t("subtitle")}
          </p>

          <div className="mt-10 flex flex-wrap items-center justify-center gap-3">
            <Link href="/login" className="rf-btn-primary px-7 py-3">
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
          <p className="mt-4 text-sm font-medium text-ink/45">{t("demoAccount")}</p>
        </div>

        <h2 className="font-display mt-20 text-center text-2xl font-medium text-ink">
          {t("featuresHeading")}
        </h2>
        <ul className="mt-8 grid gap-4 sm:grid-cols-2">
          {features.map((feature) => (
            <li key={feature.title} className="rf-card p-6">
              <div
                className="flex size-12 items-center justify-center rounded-2xl text-2xl"
                style={{ background: `${feature.color}22` }}
              >
                {feature.icon}
              </div>
              <h3 className="mt-4 text-lg font-extrabold text-ink">{feature.title}</h3>
              <p className="mt-2 text-sm font-medium leading-relaxed text-ink/55">{feature.desc}</p>
            </li>
          ))}
        </ul>
      </main>

      <section className="relative z-10 mx-auto mt-8 max-w-5xl px-6 pb-16">
        <div className="overflow-hidden rounded-[2rem] bg-ink px-8 py-10 text-center sm:px-12 sm:py-12">
          <p className="text-xs font-bold tracking-[0.18em] text-cream/40 uppercase">
            {t("ctaStripEyebrow")}
          </p>
          <p className="font-display mt-3 text-3xl font-medium text-cream sm:text-4xl">
            {t("ctaStripTitle")}
          </p>
          <Link href="/login" className="rf-btn-primary mt-8 inline-flex px-8 py-3">
            {t("ctaPrimary")}
          </Link>
        </div>
      </section>
    </div>
  );
}
