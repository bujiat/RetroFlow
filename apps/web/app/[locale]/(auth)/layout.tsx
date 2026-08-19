import { getTranslations } from "next-intl/server";

import { LocaleSwitcher } from "@/components/locale-switcher";
import { Link } from "@/i18n/navigation";

export default async function AuthLayout({ children }: { children: React.ReactNode }) {
  const tc = await getTranslations("common");

  return (
    <div className="min-h-screen bg-[linear-gradient(180deg,#fafafa_0%,#ffffff_45%,#f4f4f5_100%)]">
      <header className="px-6 py-4">
        <div className="mx-auto flex max-w-5xl items-center justify-between">
          <Link
            href="/"
            className="text-sm font-semibold tracking-wide text-zinc-900 transition-colors hover:text-zinc-600"
          >
            ← {tc("brand")}
          </Link>
          <LocaleSwitcher />
        </div>
      </header>
      {children}
    </div>
  );
}
