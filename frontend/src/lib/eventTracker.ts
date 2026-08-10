import { BASE_URL } from "@/api/client";
import { authStorage } from "@/lib/authStorage";
import type { EventPayload, EventsResponse } from "@/types/api";

type EventType = EventPayload["event_type"];

type OnTriggered = (res: EventsResponse) => void;

class EventTracker {
  private buffer: EventPayload[] = [];
  private intervalId: ReturnType<typeof setInterval> | null = null;
  private onTriggered: OnTriggered | null = null;
  /** Survives React StrictMode remount so the same course visit isn't double-logged. */
  private recentKeys = new Map<string, number>();

  setOnTriggered(fn: OnTriggered) {
    this.onTriggered = fn;
  }

  /** Drop pending events (call on login/signup/logout so accounts stay isolated). */
  clear() {
    this.buffer = [];
    this.recentKeys.clear();
  }

  track(event_type: EventType, raw_metadata: Record<string, unknown>) {
    // Never queue analytics without an authenticated session
    if (!authStorage.getToken()) return;
    this.buffer.push({ event_type, source: "udemy", raw_metadata });
    // Flush views/clicks immediately so Dashboard times aren't batched as "just now"
    if (event_type === "view" || event_type === "click" || this.buffer.length >= 5) {
      void this.flush();
    }
  }

  /**
   * Same event_type + courseId within windowMs is ignored.
   * Needed because React StrictMode mounts → unmounts → remounts in dev.
   */
  trackOnce(
    event_type: EventType,
    raw_metadata: Record<string, unknown>,
    // Short window to avoid double-logging from StrictMode remounts,
    // but small enough to not suppress normal rapid browsing.
    windowMs = 1200,
  ) {
    const courseId = String(raw_metadata.courseId ?? "");
    const key = `${event_type}:${courseId || JSON.stringify(raw_metadata)}`;
    const now = Date.now();
    const last = this.recentKeys.get(key) ?? 0;
    if (now - last < windowMs) return;
    this.recentKeys.set(key, now);
    this.track(event_type, raw_metadata);
  }

  async flush() {
    if (this.buffer.length === 0) return;
    const events = [...this.buffer];
    this.buffer = [];
    const token = authStorage.getToken();
    if (!token) return;
    try {
      const res = await fetch(`${BASE_URL}/events`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
          "ngrok-skip-browser-warning": "true",
        },
        body: JSON.stringify({ events }),
      });
      if (res.ok) {
        const data: EventsResponse = await res.json();
        if (data.triggered && this.onTriggered) {
          this.onTriggered(data);
        }
      }
    } catch (e) {
      console.debug("[eventTracker] flush error", e);
    }
  }

  private unloadFlush() {
    if (this.buffer.length === 0) return;
    const events = [...this.buffer];
    this.buffer = [];
    const token = authStorage.getToken();
    if (!token) return;
    // keepalive fetch preferred for authenticated unload flush
    fetch(`${BASE_URL}/events`, {
      method: "POST",
      keepalive: true,
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
        "ngrok-skip-browser-warning": "true",
      },
      body: JSON.stringify({ events }),
    }).catch(() => {});
  }

  private handleVisibilityChange = () => {
    if (document.visibilityState === "hidden") this.unloadFlush();
  };

  start() {
    this.intervalId = setInterval(() => this.flush(), 10_000);
    document.addEventListener("visibilitychange", this.handleVisibilityChange);
    window.addEventListener("pagehide", () => this.unloadFlush());
    window.addEventListener("beforeunload", () => this.unloadFlush());
  }

  stop() {
    if (this.intervalId) {
      clearInterval(this.intervalId);
      this.intervalId = null;
    }
    document.removeEventListener("visibilitychange", this.handleVisibilityChange);
    // Do not flush on stop/logout — avoids attaching leftover buffer to the wrong session
    this.clear();
  }
}

export const eventTracker = new EventTracker();
