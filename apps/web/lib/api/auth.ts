import { apiRequest } from "@/lib/api/client";

type AuthUser = {
  id: string;
  email: string;
  locale: string;
};

export type AuthResponse = {
  access_token: string;
  token_type: string;
  user: AuthUser;
};

export function register(input: {
  email: string;
  password: string;
  locale: string;
}): Promise<AuthResponse> {
  return apiRequest<AuthResponse>("/auth/register", {
    method: "POST",
    body: input,
    auth: false,
    fallbackError: "register_failed",
  });
}

export function login(input: {
  email: string;
  password: string;
}): Promise<AuthResponse> {
  return apiRequest<AuthResponse>("/auth/login", {
    method: "POST",
    body: input,
    auth: false,
    fallbackError: "login_failed",
  });
}
