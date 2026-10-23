import { setRequestLocale } from "next-intl/server";

import { AgentRunDetailView } from "@/components/agent-run-detail-view";
import type { LocaleIdParams } from "@/types";

type Props = {
  params: LocaleIdParams;
};

export default async function AgentRunDetailPage({ params }: Props) {
  const { locale, id } = await params;
  setRequestLocale(locale);

  return <AgentRunDetailView runId={id} />;
}
