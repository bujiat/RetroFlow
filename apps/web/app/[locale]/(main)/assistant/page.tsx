import { setRequestLocale } from "next-intl/server";

import { AssistantView } from "@/components/assistant-view";
import type { LocaleParams } from "@/types";

type Props = {
  params: LocaleParams;
};

export default async function AssistantPage({ params }: Props) {
  const { locale } = await params;
  setRequestLocale(locale);

  return <AssistantView />;
}
