"use client";

import { useLocale, useTranslations } from "next-intl";
import { useEffect, useId, useState, type FormEvent } from "react";

import { useRouter } from "@/i18n/navigation";
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
    <div>
      <h1 className="text-center text-2xl font-semibold tracking-tight text-zinc-950">
        {isLogin ? t("loginTitle") : t("registerTitle")}
      </h1>

      <form onSubmit={onSubmit} className="mt-10 flex flex-col gap-5">
        <div className="flex flex-col gap-2 text-left">
          <label htmlFor={emailId} className="text-sm font-medium text-zinc-800">
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
            className="rounded-md border border-zinc-300 bg-white px-3 py-2.5 text-sm text-zinc-900 outline-none transition-colors placeholder:text-zinc-400 focus:border-zinc-500"
            placeholder="you@example.com"
          />
        </div>

        <div className="flex flex-col gap-2 text-left">
          <label htmlFor={passwordId} className="text-sm font-medium text-zinc-800">
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
            className="rounded-md border border-zinc-300 bg-white px-3 py-2.5 text-sm text-zinc-900 outline-none transition-colors placeholder:text-zinc-400 focus:border-zinc-500"
          />
        </div>

        {!isLogin ? (
          <div className="flex flex-col gap-2 text-left">
            <label htmlFor={confirmId} className="text-sm font-medium text-zinc-800">
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
              className="rounded-md border border-zinc-300 bg-white px-3 py-2.5 text-sm text-zinc-900 outline-none transition-colors placeholder:text-zinc-400 focus:border-zinc-500"
            />
          </div>
        ) : null}

        {error ? <p className="text-sm text-red-600">{error}</p> : null}

        {isLogin ? (
          <div className="rounded-md border border-zinc-200 bg-zinc-50 px-3 py-3 text-left text-sm text-zinc-600">
            <p>{t("demoHint")}</p>
            <p className="mt-1 font-mono text-zinc-800">
              {DEMO_EMAIL} / {DEMO_PASSWORD}
            </p>
            <button
              type="button"
              className="mt-2 text-zinc-900 underline-offset-4 hover:underline"
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

        <button
          type="submit"
          disabled={pending}
          className="mt-2 rounded-md bg-zinc-900 px-6 py-2.5 text-sm font-medium text-white transition-colors hover:bg-zinc-800 disabled:opacity-60"
        >
          {isLogin ? t("submitLogin") : t("submitRegister")}
        </button>
      </form>

      <p className="mt-6 text-center text-sm text-zinc-600">
        <button
          type="button"
          className="underline-offset-4 hover:text-zinc-900 hover:underline"
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
  );
}
