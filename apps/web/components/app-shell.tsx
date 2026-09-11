"use client";

import { useTranslations } from "next-intl";
import { useState } from "react";

import { LocaleSwitcher } from "@/components/locale-switcher";
import { LogoutButton } from "@/components/logout-button";
import { Link, usePathname } from "@/i18n/navigation";

const NAV = [
  { href: "/retros" as const, labelKey: "retros", icon: "📋", color: "#FF6B4A" },
  { href: "/actions/board" as const, labelKey: "actions", icon: "🎯", color: "#FFB830" },
  { href: "/weekly-review" as const, labelKey: "weeklyReview", icon: "✨", color: "#3ECFA0" },
  { href: "/trends" as const, labelKey: "trends", icon: "📈", color: "#4AAFFF" },
  { href: "/assistant" as const, labelKey: "assistant", icon: "🤖", color: "#7C5CBF" },
] as const;

function navActive(pathname: string, href: string): boolean {
  if (href === "/retros") {
    return pathname === "/retros" || pathname.startsWith("/retros/") || pathname.startsWith("/retro/");
  }
  return pathname === href || pathname.startsWith(`${href}/`);
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const t = useTranslations("nav");
  const tc = useTranslations("common");
  const pathname = usePathname();
  const [collapsed, setCollapsed] = useState(false);
  const showLabels = !collapsed;

  return (
    <div className="flex h-dvh overflow-hidden bg-cream">
      <aside
        className="relative flex h-full shrink-0 flex-col overflow-y-auto"
        style={{
          width: collapsed ? 68 : undefined,
          background: "#2D1F14",
        }}
        data-expanded={showLabels ? "true" : "false"}
      >
        <div
          className={collapsed ? "flex h-full w-[68px] flex-col" : "flex h-full w-[68px] flex-col md:w-[216px]"}
        >
          <div className="pointer-events-none absolute top-3 right-3 h-20 w-20 rounded-full opacity-10 bg-[radial-gradient(circle,#FF6B4A_0%,transparent_70%)]" />
          <Link
            href="/retros"
            className="flex h-[68px] shrink-0 items-center gap-3 border-b border-white/[0.07] px-4"
          >
            <div className="flex size-10 shrink-0 items-center justify-center rounded-2xl bg-linear-to-br from-coral to-sun text-xl text-white">
              🔁
            </div>
            {showLabels ? (
              <div className="hidden md:block">
                <div className="text-sm leading-tight font-extrabold text-cream">{tc("brand")}</div>
                <div className="text-[10px] font-medium tracking-wide text-cream/40">RETRO STUDIO</div>
              </div>
            ) : null}
          </Link>
          <nav className="flex flex-1 flex-col gap-1.5 px-3 py-5">
            {NAV.map((item) => {
              const active = navActive(pathname, item.href);
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  title={t(item.labelKey)}
                  className="relative flex items-center gap-3 overflow-hidden rounded-2xl px-3.5 py-2.5 transition-all"
                  style={{
                    background: active ? `${item.color}22` : "transparent",
                    border: active ? `1.5px solid ${item.color}44` : "1.5px solid transparent",
                    justifyContent: showLabels ? undefined : "center",
                  }}
                >
                  <span className="shrink-0 text-lg">{item.icon}</span>
                  {showLabels ? (
                    <span
                      className="hidden whitespace-nowrap text-sm md:inline"
                      style={{
                        fontWeight: active ? 700 : 500,
                        color: active ? item.color : "rgba(255,251,245,0.55)",
                      }}
                    >
                      {t(item.labelKey)}
                    </span>
                  ) : null}
                  {active && showLabels ? (
                    <span
                      className="ml-auto hidden size-1.5 shrink-0 rounded-full md:block"
                      style={{ background: item.color }}
                    />
                  ) : null}
                </Link>
              );
            })}
          </nav>
          <div className="shrink-0 space-y-2 border-t border-white/[0.07] p-3">
            <div className="rounded-2xl bg-white/5 px-2 py-2 md:px-3">
              <LocaleSwitcher variant="dark" />
            </div>
            <LogoutButton variant="dark" />
            <button
              type="button"
              onClick={() => setCollapsed((v) => !v)}
              className="hidden w-full items-center justify-center rounded-xl bg-white/5 py-2 text-sm text-cream/35 md:flex"
            >
              {collapsed ? "→" : "←"}
            </button>
          </div>
        </div>
      </aside>
      <main className="min-w-0 flex-1 overflow-auto">{children}</main>
    </div>
  );
}
