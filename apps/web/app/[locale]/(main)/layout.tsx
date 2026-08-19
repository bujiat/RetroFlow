import { getTranslations } from "next-intl/server";

import { AuthGate } from "@/components/auth-gate";
import { LocaleSwitcher } from "@/components/locale-switcher";
import { LogoutButton } from "@/components/logout-button";
import { Link } from "@/i18n/navigation";

export default async function MainLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const t = await getTranslations("nav");

  const nav = [
    { href: "/retros" as const, label: t("retros") },
    { href: "/actions/board" as const, label: t("actions") },
    { href: "/weekly-review" as const, label: t("weeklyReview") },
    { href: "/trends" as const, label: t("trends") },
    { href: "/assistant" as const, label: t("assistant") },
  ];

  return (
    <AuthGate>
      <div className="min-h-full">
        <header className="border-b px-6 py-4">
          <div className="mx-auto flex max-w-5xl items-center justify-between gap-4">
            <Link href="/retros" className="font-semibold">
              RetroFlow
            </Link>
            <nav className="flex flex-wrap items-center gap-6 text-sm">
              {nav.map((item) => (
                <Link key={item.href} href={item.href}>
                  {item.label}
                </Link>
              ))}
              <LocaleSwitcher />
              <LogoutButton />
            </nav>
          </div>
        </header>
        <main className="mx-auto max-w-5xl px-6 py-8">{children}</main>
      </div>
    </AuthGate>
  );
}
