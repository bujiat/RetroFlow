import { setRequestLocale } from "next-intl/server";

import { LoginForm } from "@/components/login-form";
import type { LocaleParams } from "@/types";

type Props = {
  params: LocaleParams;
};

export default async function LoginPage({ params }: Props) {
  const { locale } = await params;
  setRequestLocale(locale);

  return <LoginForm />;
}
