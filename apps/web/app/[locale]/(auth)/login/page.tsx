import { setRequestLocale } from "next-intl/server";

import { LoginForm } from "@/components/login-form";
import type { LocaleParams } from "@/types";

type Props = {
  params: LocaleParams;
};

export default async function LoginPage({ params }: Props) {
  const { locale } = await params;
  setRequestLocale(locale);

  return (
    <main className="mx-auto flex w-full max-w-md flex-col px-6 pb-20 pt-10 sm:pt-16">
      <LoginForm />
    </main>
  );
}
