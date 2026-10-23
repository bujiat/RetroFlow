import { setRequestLocale } from "next-intl/server";

import { AgentRunsView } from "@/components/agent-runs-view";
import type { LocaleParams } from "@/types";

type Props = {
  params: LocaleParams;
};

export default async function AgentRunsPage({ params }: Props) {
  const { locale } = await params;
  setRequestLocale(locale);

  return <AgentRunsView />;
}
