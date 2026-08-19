import { getAccessToken, clearAccessToken } from "@/lib/auth-token";

function apiBaseUrl(): string {
  const base = process.env.NEXT_PUBLIC_API_BASE_URL;
  if (!base) {
    throw new Error("NEXT_PUBLIC_API_BASE_URL is not set");
  }
  return base.replace(/\/$/, "");
}

export class ApiError extends Error {
  readonly status: number;
  readonly code: string | null;

  constructor(status: number, code: string | null, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
  }
}

type ErrorBody = {
  detail?: string | { code?: string; message?: string } | Array<{ msg?: string }>;
};

async function parseError(response: Response, fallback: string): Promise<ApiError> {
  try {
    const data = (await response.json()) as ErrorBody;
    const detail = data.detail;

    if (typeof detail === "string") {
      return new ApiError(response.status, null, detail);
    }

    if (detail && !Array.isArray(detail) && typeof detail.code === "string") {
      return new ApiError(
        response.status,
        detail.code,
        typeof detail.message === "string" ? detail.message : detail.code,
      );
    }
  } catch {
    /* ignore */
  }

  return new ApiError(response.status, null, fallback);
}

export function isUnauthorized(err: unknown): boolean {
  return (
    err instanceof ApiError &&
    (err.status === 401 ||
      err.code === "not_authenticated" ||
      err.code === "invalid_token")
  );
}

export function redirectToLoginIfUnauthorized(
  err: unknown,
  replace: (href: string) => void,
): boolean {
  if (!isUnauthorized(err)) return false;
  clearAccessToken();
  replace("/login");
  return true;
}

export function isNetworkError(err: unknown): boolean {
  return err instanceof ApiError && err.code === "network_error";
}

export function failedRequestMessage(
  err: unknown,
  messages: { network: string; fallback: string; missingApi?: string },
): string {
  if (err instanceof Error && err.message.includes("NEXT_PUBLIC_API_BASE_URL")) {
    return messages.missingApi ?? messages.network;
  }
  if (isNetworkError(err)) {
    return messages.network;
  }
  return messages.fallback;
}

export async function apiRequest<T>(
  path: string,
  init: {
    method: "GET" | "POST" | "PATCH" | "PUT" | "DELETE";
    body?: unknown;
    /**
     * 默认 true：从 localStorage 带 Bearer。
     * 仅登录/注册等公开接口传 false。
     */
    auth?: boolean;
    fallbackError: string;
  },
): Promise<T> {
  const headers: HeadersInit = {
    Accept: "application/json",
  };
  if (init.body !== undefined) {
    headers["Content-Type"] = "application/json";
  }
  if (init.auth !== false) {
    const token = getAccessToken();
    if (token) {
      headers.Authorization = `Bearer ${token}`;
    }
  }

  const response = await fetch(`${apiBaseUrl()}${path}`, {
    method: init.method,
    headers,
    body: init.body !== undefined ? JSON.stringify(init.body) : undefined,
    cache: "no-store",
  }).catch(() => {
    throw new ApiError(0, "network_error", "network_error");
  });

  if (!response.ok) {
    throw await parseError(response, init.fallbackError);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return response.json() as Promise<T>;
}
