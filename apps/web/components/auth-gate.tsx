"use client";

import { useTranslations } from "next-intl";
import { useEffect, useSyncExternalStore } from "react";

import { useRouter } from "@/i18n/navigation";
import { getAccessToken } from "@/lib/auth-token";

export function AuthGate({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const t = useTranslations("authGate");
  const hydrated = useSyncExternalStore(
    () => () => undefined,
    () => true,
    () => false,
  );
  const hasToken = hydrated && Boolean(getAccessToken());

  useEffect(() => {
    if (hydrated && !hasToken) {
      router.replace("/login");
    }
  }, [hasToken, hydrated, router]);

  if (!hasToken) {
    return <p className="text-sm text-zinc-500">{t("checking")}</p>;
  }

  return children;
}
