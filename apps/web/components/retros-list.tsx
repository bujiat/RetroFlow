"use client";

import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";

import { useRouter } from "@/i18n/navigation";
import { failedRequestMessage, redirectToLoginIfUnauthorized } from "@/lib/api/client";
import { listRetros, type RetroListItem } from "@/lib/api/retros";

export function RetrosList() {
  const t = useTranslations("retros");
  const tCommon = useTranslations("common");
  const router = useRouter();
  const [items, setItems] = useState<RetroListItem[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const data = await listRetros();
        if (!cancelled) {
          setItems(data);
        }
      } catch (err) {
        if (cancelled) return;
        if (redirectToLoginIfUnauthorized(err, router.replace)) return;
        setError(
          failedRequestMessage(err, {
            network: tCommon("networkError"),
            fallback: t("loadFailed"),
          }),
        );
        setItems([]);
      }
    }

    void load();
    return () => {
      cancelled = true;
    };
  }, [router, t, tCommon]);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-4">
        <h1 className="text-xl font-semibold tracking-tight text-zinc-950">{t("title")}</h1>
        <button
          type="button"
          onClick={() => router.push("/retro/new")}
          className="rounded-md bg-zinc-900 px-3 py-2 text-sm font-medium text-white hover:bg-zinc-800"
        >
          {t("new")}
        </button>
      </div>

      {error ? <p className="text-sm text-red-600">{error}</p> : null}

      {items === null ? (
        <p className="text-sm text-zinc-500">{t("loading")}</p>
      ) : items.length === 0 ? (
        <p className="text-sm text-zinc-600">{t("empty")}</p>
      ) : (
        <ul className="divide-y border-y border-zinc-200">
          {items.map((item) => (
            <li key={item.id}>
              <button
                type="button"
                onClick={() => router.push(`/retro/${item.id}/confirm`)}
                className="flex w-full flex-col gap-1 py-4 text-left hover:bg-zinc-50"
              >
                <span className="font-medium text-zinc-950">{item.title}</span>
                <span className="text-sm text-zinc-500">
                  {item.review_date} · {item.status}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
