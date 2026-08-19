import { setRequestLocale } from "next-intl/server";

import { ActionsBoard } from "@/components/actions-board";
import type { LocaleParams } from "@/types";

type Props = {
  params: LocaleParams;
};

export default async function BoardPage({ params }: Props) {
  const { locale } = await params;
  setRequestLocale(locale);

  return <ActionsBoard />;
}
