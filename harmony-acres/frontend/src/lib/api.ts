// Thin typed wrapper around fetch. One place that knows the base URL, attaches
// the bearer token, and turns non-2xx responses into a typed error carrying the
// backend's `detail` message so the UI can show something human.

import type { CycleSummary, Order, Product, Token, User } from "./types";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

const TOKEN_KEY = "ha_token";

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string | null) {
  if (typeof window === "undefined") return;
  if (token) window.localStorage.setItem(TOKEN_KEY, token);
  else window.localStorage.removeItem(TOKEN_KEY);
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
    this.name = "ApiError";
  }
}

interface RequestOptions {
  method?: string;
  body?: unknown;
  // Some calls (login/register) run before there's a token; auth defaults on.
  auth?: boolean;
}

async function request<T>(path: string, opts: RequestOptions = {}): Promise<T> {
  const { method = "GET", body, auth = true } = opts;
  const headers: Record<string, string> = { "Content-Type": "application/json" };

  if (auth) {
    const token = getToken();
    if (token) headers.Authorization = `Bearer ${token}`;
  }

  const res = await fetch(`${API_BASE}${path}`, {
    method,
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
  });

  if (res.status === 401) {
    // Token missing/expired. Clear it so guards send the user back to /login.
    setToken(null);
    throw new ApiError(401, "Your session has expired. Please sign in again.");
  }

  if (!res.ok) {
    // FastAPI puts the human message under `detail`; fall back to the status.
    let detail = `Request failed (${res.status})`;
    try {
      const data = await res.json();
      if (typeof data?.detail === "string") detail = data.detail;
    } catch {
      /* non-JSON error body — keep the generic message */
    }
    throw new ApiError(res.status, detail);
  }

  // 204 and other empty bodies would blow up res.json(); guard for them.
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export const api = {
  // --- auth ---
  register: (data: { email: string; password: string; full_name: string }) =>
    request<User>("/auth/register", { method: "POST", body: data, auth: false }),
  login: (data: { email: string; password: string }) =>
    request<Token>("/auth/login", { method: "POST", body: data, auth: false }),
  me: () => request<User>("/customers/me"),

  // --- cycle ---
  currentCycle: () => request<CycleSummary>("/cycles/current"),

  // --- catalog ---
  products: () => request<Product[]>("/products"),

  // --- draft / order ---
  draft: () => request<Order>("/orders/draft"),
  setItem: (product_id: string, quantity: number) =>
    request<Order>("/orders/draft/items", {
      method: "PUT",
      body: { product_id, quantity },
    }),
  setDraftDetails: (data: { pickup_location?: string; note?: string }) =>
    request<Order>("/orders/draft", { method: "PATCH", body: data }),
  submitDraft: () => request<Order>("/orders/draft/submit", { method: "POST" }),
};
