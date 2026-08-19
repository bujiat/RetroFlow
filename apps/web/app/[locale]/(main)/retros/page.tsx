import { setRequestLocale } from "next-intl/server";

import { RetrosList } from "@/components/retros-list";
import type { LocaleParams } from "@/types";

type Props = {
  params: LocaleParams;
};

export default async function RetrosPage({ params }: Props) {
  const { locale } = await params;
  setRequestLocale(locale);

  return <RetrosList />;
}
