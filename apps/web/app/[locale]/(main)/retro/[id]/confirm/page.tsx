import { setRequestLocale } from "next-intl/server";

import { RetroConfirmView } from "@/components/retro-confirm-view";
import type { LocaleIdParams } from "@/types";

type Props = {
  params: LocaleIdParams;
};

export default async function ConfirmRetroPage({ params }: Props) {
  const { locale, id } = await params;
  setRequestLocale(locale);

  return <RetroConfirmView retroId={id} />;
}
