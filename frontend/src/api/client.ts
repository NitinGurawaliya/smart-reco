/*
 * SmartReco API client
 * Endpoints used:
 *   POST /auth/signup
 *   POST /auth/login
 *   GET  /auth/me
 *   POST /events
 *   GET  /events?limit=N
 *   GET  /recommendations/latest
 *   GET  /catalog
 *   GET  /catalog/:id
 *   POST /catalog
 *   PUT  /catalog/:id
 *   DELETE /catalog/:id
 *   POST /catalog/:id/resync
 */

import { authStorage } from "@/lib/authStorage";

const BASE_URL = (import.meta.env.VITE_API_URL as string | undefined) ?? "http://localhost:8000";

export { BASE_URL };

export function parseError(data: unknown): string {
  if (typeof data === "object" && data !== null) {
    const d = data as Record<string, unknown>;
    if (typeof d.detail === "string") return d.detail;
    if (Array.isArray(d.detail)) {
      return d.detail
        .map((e: unknown) => {
          if (typeof e === "object" && e !== null && "msg" in e) return (e as { msg: string }).msg;
          return String(e);
        })
        .join("; ");
    }
  }
  return "An unexpected error occurred.";
}

export async function apiFetch<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = authStorage.getToken();
  const headers: Record<string, string> = {
    ...(options.body ? { "Content-Type": "application/json" } : {}),
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    "ngrok-skip-browser-warning": "true",
    ...(options.headers as Record<string, string> | undefined),
  };

  const res = await fetch(`${BASE_URL}${path}`, { ...options, headers });

  if (res.status === 401) {
    // Only hard-redirect when a session existed — otherwise public pages
    // (login) calling protected APIs would infinite-reload /login.
    const hadToken = Boolean(token);
    const path = window.location.pathname;
    const onAuthPage = path === "/login" || path === "/signup" || path === "/";
    authStorage.clear();
    if (hadToken && !onAuthPage) {
      window.location.href = "/login";
    }
    throw new Error("Unauthorized");
  }

  if (res.status === 204) return undefined as unknown as T;

  const data = await res.json();

  if (!res.ok) {
    throw new Error(parseError(data));
  }

  return data as T;
}
