"use client";

import { useTranslations } from "next-intl";

import { useRouter } from "@/i18n/navigation";
import { clearAccessToken } from "@/lib/auth-token";

export function LogoutButton({ variant = "light" }: { variant?: "light" | "dark" }) {
  const router = useRouter();
  const t = useTranslations("common");

  function onLogout() {
    clearAccessToken();
    router.replace("/login");
  }

  return (
    <button
      type="button"
      onClick={onLogout}
      className={
        variant === "dark"
          ? "w-full rounded-xl py-2 text-sm font-semibold text-cream/55 hover:bg-white/5 hover:text-cream"
          : "text-sm font-semibold text-ink/50 hover:text-ink"
      }
    >
      {t("logout")}
    </button>
  );
}
