import { setRequestLocale } from "next-intl/server";

import { WeeklyReviewView } from "@/components/weekly-review-view";
import type { LocaleParams } from "@/types";

type Props = {
  params: LocaleParams;
};

export default async function WeeklyReviewPage({ params }: Props) {
  const { locale } = await params;
  setRequestLocale(locale);

  return <WeeklyReviewView />;
}
