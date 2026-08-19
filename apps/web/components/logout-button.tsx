"use client";

import { useTranslations } from "next-intl";

import { useRouter } from "@/i18n/navigation";
import { clearAccessToken } from "@/lib/auth-token";

export function LogoutButton() {
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
      className="text-sm text-zinc-600 hover:text-zinc-950"
    >
      {t("logout")}
    </button>
  );
}
