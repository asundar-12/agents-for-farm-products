// Thin typed wrapper around fetch. One place that knows the base URL, attaches
// the bearer token, and turns non-2xx responses into a typed error carrying the
// backend's `detail` message so the UI can show something human.

import type {
  AdminCustomer,
  AdminDashboard,
  CycleSummary,
  NonSubmitter,
  Order,
  Product,
  ShoppingList,
  Subscription,
  SubscriptionInput,
  Token,
  User,
  WeeklyCycle,
} from "./types";

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

  // A 401 on an authenticated request means the token we sent was rejected —
  // expired or invalid — so clear it and send the user back to sign in. But
  // login/register (auth: false) also 401 on bad credentials; those must fall
  // through to the real backend message ("Incorrect email or password") rather
  // than be mislabeled as an expired session.
  if (res.status === 401 && auth) {
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
  setDraftDetails: (data: { note?: string }) =>
    request<Order>("/orders/draft", { method: "PATCH", body: data }),
  submitDraft: () => request<Order>("/orders/draft/submit", { method: "POST" }),

  // --- order history ---
  orders: () => request<Order[]>("/orders"),
  order: (id: string) => request<Order>(`/orders/${id}`),

  // --- subscriptions ---
  subscriptions: () => request<Subscription[]>("/subscriptions"),
  subscription: (id: string) => request<Subscription>(`/subscriptions/${id}`),
  createSubscription: (data: SubscriptionInput) =>
    request<Subscription>("/subscriptions", { method: "POST", body: data }),
  updateSubscription: (id: string, data: Partial<SubscriptionInput>) =>
    request<Subscription>(`/subscriptions/${id}`, { method: "PATCH", body: data }),
  pauseSubscription: (id: string, resume_on: string | null) =>
    request<Subscription>(`/subscriptions/${id}/pause`, { method: "POST", body: { resume_on } }),
  resumeSubscription: (id: string) =>
    request<Subscription>(`/subscriptions/${id}/resume`, { method: "POST" }),
  cancelSubscription: (id: string) =>
    request<Subscription>(`/subscriptions/${id}/cancel`, { method: "POST" }),

  // --- account ---
  updateMe: (full_name: string) =>
    request<User>("/customers/me", { method: "PATCH", body: { full_name } }),

  // --- admin ---
  adminDashboard: () => request<AdminDashboard>("/admin/dashboard"),
  adminCurrentCycle: () => request<WeeklyCycle>("/admin/cycles/current"),
  adminCycles: () => request<WeeklyCycle[]>("/admin/cycles"),
  adminShoppingList: (cycleId: string) =>
    request<ShoppingList>(`/admin/cycles/${cycleId}/shopping-list`),
  adminNonSubmitters: (cycleId: string) =>
    request<NonSubmitter[]>(`/admin/cycles/${cycleId}/non-submitters`),
  adminCustomers: () => request<AdminCustomer[]>("/admin/customers"),
  adminAdjustLine: (cycleId: string, productId: string, quantity: number | null) =>
    request<ShoppingList>(`/admin/cycles/${cycleId}/lines/${productId}`, {
      method: "PATCH",
      body: { quantity },
    }),
  // Lifecycle transitions. Each is its own backend endpoint; `action` is the
  // URL suffix (aggregate, approve, reject, mark-ordered, mark-received, close).
  adminCycleAction: (cycleId: string, action: string) =>
    request<unknown>(`/admin/cycles/${cycleId}/${action}`, { method: "POST", body: {} }),
};

// --- Streaming assistant chat -------------------------------------------------
// The backend streams the AI reply as Server-Sent Events: a sequence of
// `data: <json>\n\n` frames. The first frame is `{session_id}`, then one frame
// per text chunk (a JSON string), then `{done: true}`. We read the response
// body as it arrives and hand each text chunk to `onDelta`, so the UI can type
// the answer out instead of waiting for the whole thing.
export interface ChatStreamHandlers {
  onSession?: (sessionId: string) => void;
  onDelta: (text: string) => void;
  signal?: AbortSignal;
}

export async function streamChat(
  message: string,
  sessionId: string | null,
  handlers: ChatStreamHandlers,
): Promise<void> {
  const token = getToken();
  const res = await fetch(`${API_BASE}/agent/chat/stream`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify({ message, session_id: sessionId }),
    signal: handlers.signal,
  });

  if (!res.ok || !res.body) {
    throw new ApiError(res.status, "The assistant is unavailable right now.");
  }

  // Read the raw byte stream and split it into whole lines. A single network
  // chunk can hold part of a line or several lines, so we keep a buffer and
  // only process up to the last complete newline.
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    const lines = buffer.split("\n");
    buffer = lines.pop() ?? ""; // last piece may be incomplete; keep it

    for (const line of lines) {
      if (!line.startsWith("data: ")) continue;
      const payload = line.slice("data: ".length);
      let frame: unknown;
      try {
        frame = JSON.parse(payload);
      } catch {
        continue;
      }
      if (typeof frame === "string") {
        handlers.onDelta(frame);
      } else if (frame && typeof frame === "object") {
        const obj = frame as { session_id?: string; done?: boolean };
        if (obj.session_id) handlers.onSession?.(obj.session_id);
        // `done` needs no handling — the loop ends when the body closes.
      }
    }
  }
}
