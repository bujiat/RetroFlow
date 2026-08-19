import { setRequestLocale } from "next-intl/server";

import { NewRetroForm } from "@/components/new-retro-form";
import type { LocaleParams } from "@/types";

type Props = {
  params: LocaleParams;
};

export default async function NewRetroPage({ params }: Props) {
  const { locale } = await params;
  setRequestLocale(locale);

  return <NewRetroForm />;
}
