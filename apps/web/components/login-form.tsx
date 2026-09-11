"use client";

import { useLocale, useTranslations } from "next-intl";
import { useEffect, useId, useState, type FormEvent } from "react";

import { LocaleSwitcher } from "@/components/locale-switcher";
import { Link, useRouter } from "@/i18n/navigation";
import type { AppLocale } from "@/i18n/routing";
import { login as loginRequest, register as registerRequest } from "@/lib/api/auth";
import { ApiError } from "@/lib/api/client";
import { getAccessToken, setAccessToken } from "@/lib/auth-token";

type AuthMode = "login" | "register";

const DEMO_EMAIL = "demo@example.com";
const DEMO_PASSWORD = "demo1234";

export function LoginForm() {
  const [mode, setMode] = useState<AuthMode>("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  const emailId = useId();
  const passwordId = useId();
  const confirmId = useId();
  const locale = useLocale() as AppLocale;
  const router = useRouter();
  const t = useTranslations("auth");
  const tc = useTranslations("common");
  const th = useTranslations("home");

  const isLogin = mode === "login";

  useEffect(() => {
    if (getAccessToken()) {
      router.replace("/retros");
    }
  }, [router]);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);

    if (!isLogin && password !== confirmPassword) {
      setError(t("passwordMismatch"));
      return;
    }

    setPending(true);
    try {
      const result = isLogin
        ? await loginRequest({ email, password })
        : await registerRequest({ email, password, locale });
      setAccessToken(result.access_token);
      router.push("/retros");
    } catch (err) {
      if (err instanceof Error && err.message.includes("NEXT_PUBLIC_API_BASE_URL")) {
        setError(t("apiBaseMissing"));
        return;
      }

      const code = err instanceof ApiError ? err.code : null;
      switch (code) {
        case "email_already_registered":
          setError(t("emailTaken"));
          break;
        case "email_not_registered":
          setError(t("emailNotRegistered"));
          break;
        case "incorrect_password":
          setError(t("incorrectPassword"));
          break;
        case "network_error":
          setError(t("networkError"));
          break;
        default:
          setError(isLogin ? t("loginFailed") : t("registerFailed"));
      }
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="flex min-h-screen">
      <aside className="relative hidden w-[42%] overflow-hidden bg-ink lg:flex lg:flex-col lg:justify-between p-10">
        <div className="pointer-events-none absolute -top-16 -right-10 size-64 rounded-full bg-[radial-gradient(circle,#FF6B4A_0%,transparent_70%)] opacity-40" />
        <div className="pointer-events-none absolute bottom-10 -left-10 size-52 rounded-full bg-[radial-gradient(circle,#FFB830_0%,transparent_70%)] opacity-25" />
        <Link href="/" className="relative z-10 flex items-center gap-3">
          <div className="flex size-11 items-center justify-center rounded-2xl bg-linear-to-br from-coral to-sun text-xl text-white">
            🔁
          </div>
          <div>
            <div className="text-lg font-extrabold text-cream">{tc("brand")}</div>
            <div className="text-[10px] font-medium tracking-widest text-cream/40">RETRO STUDIO</div>
          </div>
        </Link>
        <div className="relative z-10 space-y-4">
          <p className="font-display text-7xl leading-none text-coral/80">{t("quoteMark")}</p>
          <p className="font-display text-4xl leading-tight font-medium text-cream">{th("title")}</p>
          <p className="max-w-sm text-sm font-medium leading-relaxed text-cream/55">{th("subtitle")}</p>
        </div>
        <p className="relative z-10 text-xs font-medium text-cream/30">{th("demoAccount")}</p>
      </aside>

      <section className="flex flex-1 flex-col">
        <div className="flex items-center justify-between px-6 py-4 lg:px-10">
          <Link href="/" className="text-sm font-semibold text-ink/50 hover:text-ink lg:invisible">
            ← {tc("brand")}
          </Link>
          <LocaleSwitcher />
        </div>
        <div className="flex flex-1 items-center justify-center px-6 pb-16">
          <div className="w-full max-w-[400px]">
            <p className="text-xs font-bold tracking-[0.16em] text-ink/35 uppercase">
              {isLogin ? t("welcomeBack") : t("createAccount")}
            </p>
            <h1 className="rf-h1 mt-2 text-[1.75rem]">
              {isLogin ? t("loginTitle") : t("registerTitle")}
            </h1>

            <form onSubmit={onSubmit} className="mt-8 flex flex-col gap-5">
              <div className="flex flex-col gap-2 text-left">
                <label htmlFor={emailId} className="text-sm font-bold text-ink">
                  {t("email")}
                </label>
                <input
                  id={emailId}
                  name="email"
                  type="email"
                  autoComplete="email"
                  required
                  value={email}
                  onChange={(event) => setEmail(event.target.value)}
                  className="rf-input"
                  placeholder="you@example.com"
                />
              </div>

              <div className="flex flex-col gap-2 text-left">
                <label htmlFor={passwordId} className="text-sm font-bold text-ink">
                  {t("password")}
                </label>
                <input
                  id={passwordId}
                  name="password"
                  type="password"
                  autoComplete={isLogin ? "current-password" : "new-password"}
                  required
                  minLength={6}
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  className="rf-input"
                />
              </div>

              {!isLogin ? (
                <div className="flex flex-col gap-2 text-left">
                  <label htmlFor={confirmId} className="text-sm font-bold text-ink">
                    {t("confirmPassword")}
                  </label>
                  <input
                    id={confirmId}
                    name="confirmPassword"
                    type="password"
                    autoComplete="new-password"
                    required
                    minLength={6}
                    value={confirmPassword}
                    onChange={(event) => setConfirmPassword(event.target.value)}
                    className="rf-input"
                  />
                </div>
              ) : null}

              {error ? <p className="text-sm font-semibold text-coral">{error}</p> : null}

              {isLogin ? (
                <div className="rounded-2xl border-2 border-ink/6 bg-sand/50 px-4 py-3 text-left text-sm text-ink/70">
                  <p>{t("demoHint")}</p>
                  <p className="mt-1 font-mono text-ink">
                    {DEMO_EMAIL} / {DEMO_PASSWORD}
                  </p>
                  <button
                    type="button"
                    className="mt-2 font-bold text-coral underline-offset-4 hover:underline"
                    onClick={() => {
                      setEmail(DEMO_EMAIL);
                      setPassword(DEMO_PASSWORD);
                      setError(null);
                    }}
                  >
                    {t("demoFill")}
                  </button>
                </div>
              ) : null}

              <button type="submit" disabled={pending} className="rf-btn-primary mt-1 py-3">
                {isLogin ? t("submitLogin") : t("submitRegister")}
              </button>
            </form>

            <p className="mt-6 text-center text-sm font-medium text-ink/50">
              <button
                type="button"
                className="font-bold text-ink underline-offset-4 hover:text-coral hover:underline"
                onClick={() => {
                  setMode(isLogin ? "register" : "login");
                  setConfirmPassword("");
                  setError(null);
                }}
              >
                {isLogin ? t("toRegister") : t("toLogin")}
              </button>
            </p>
          </div>
        </div>
      </section>
    </div>
  );
}
