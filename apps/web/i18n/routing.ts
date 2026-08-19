import { defineRouting } from "next-intl/routing";

export const routing = defineRouting({
  locales: ["zh-CN", "en"],
  defaultLocale: "zh-CN",
  localePrefix: "always",
  localeCookie: false,
});

export type AppLocale = (typeof routing.locales)[number];
