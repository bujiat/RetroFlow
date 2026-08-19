import { setRequestLocale } from "next-intl/server";

import { TrendsView } from "@/components/trends-view";
import type { LocaleParams } from "@/types";

type Props = {
  params: LocaleParams;
};

export default async function TrendsPage({ params }: Props) {
  const { locale } = await params;
  setRequestLocale(locale);

  return <TrendsView />;
}
