import {
  createContext,
  useContext,
  useState,
  useCallback,
  useEffect,
  useRef,
  type ReactNode,
} from "react";
import { recommendationsApi } from "@/api/recommendations";
import { authStorage } from "@/lib/authStorage";
import { useAuth } from "@/contexts/AuthContext";
import type { RecommendationOut, EventsResponse } from "@/types/api";

interface RecommendationContextValue {
  recommendation: RecommendationOut | null;
  isLoading: boolean;
  isRefreshing: boolean;
  /** Brief nudge that the Browse panel just received a newer recommendation */
  justUpdated: boolean;
  toastOpen: boolean;
  dismissToast(): void;
  reloadLatest(silent?: boolean): Promise<void>;
  refreshNow(): Promise<void>;
  setFromEventBatch(res: EventsResponse): void;
}

const RecommendationContext = createContext<RecommendationContextValue | null>(null);

// Module-level lock to avoid duplicate status polls from multiple mounted
// RecommendationProvider instances (or StrictMode double-mounts) in the same
// browser tab. Ensures at most one network request runs at a time.
let __RECOMMENDATIONS_POLL_LOCK = false;
// Track how many RecommendationProvider instances are mounted in this tab.
let __RECOMMENDATION_PROVIDER_MOUNT_COUNT = 0;

function idsKey(ids: number[] | undefined | null) {
  return (ids ?? []).join(",");
}

function dismissKey(recId: number) {
  return `smartreco:toast-dismissed:${recId}`;
}

function wasDismissed(recId: number) {
  try {
    return sessionStorage.getItem(dismissKey(recId)) === "1";
  } catch {
    return false;
  }
}

function markDismissed(recId: number) {
  try {
    sessionStorage.setItem(dismissKey(recId), "1");
  } catch {
    // ignore
  }
}

function hasSession() {
  return Boolean(authStorage.getToken());
}

function isNewerRec(next: RecommendationOut, prev: RecommendationOut | null): boolean {
  if (!prev) return true;
  if (next.id !== prev.id) return true;
  if (next.generated_at !== prev.generated_at) return true;
  return idsKey(next.resource_ids) !== idsKey(prev.resource_ids);
}

export function RecommendationProvider({ children }: { children: ReactNode }) {
  const { user, token } = useAuth();
  const [recommendation, setRecommendation] = useState<RecommendationOut | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [justUpdated, setJustUpdated] = useState(false);
  const [toastOpen, setToastOpen] = useState(false);
  const recommendationRef = useRef<RecommendationOut | null>(null);
  const lastGeneratedAt = useRef<string | null>(null);
  const highlightTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const applyRecommendation = useCallback(
    (rec: RecommendationOut | null, opts?: { announce?: boolean; source?: string }) => {
      const announce = Boolean(opts?.announce);
      const source = opts?.source ?? "unknown";
      if (!rec) {
        console.info("[PIPE FE] APPLY_REC null", { source });
        recommendationRef.current = null;
        lastGeneratedAt.current = null;
        setRecommendation(null);
        return;
      }

      const prev = recommendationRef.current;
      const newer = isNewerRec(rec, prev);
      recommendationRef.current = rec;
      lastGeneratedAt.current = rec.generated_at;
      console.debug("[PIPE FE] APPLY_REC", {
        source,
        announce,
        newer,
        id: rec.id,
        generated_at: rec.generated_at,
        resource_ids: rec.resource_ids,
        trigger_reason: rec.trigger_reason,
      });
      setRecommendation(rec);

      // Visible timing log to measure latency from trigger to UI apply
      try {
        console.debug("[PIPE FE] APPLY_REC_TIMING", {
          ts: new Date().toISOString(),
          source,
          id: rec.id,
          newer,
        });
      } catch {
        // noop
      }

      if (announce && newer && !wasDismissed(rec.id)) {
        setJustUpdated(true);
        setToastOpen(true);
        if (highlightTimer.current) clearTimeout(highlightTimer.current);
        highlightTimer.current = setTimeout(() => setJustUpdated(false), 4500);
      }
    },
    [],
  );

  const reloadLatest = useCallback(
    async (silent = false) => {
      if (!hasSession()) return;
      if (!silent) setIsLoading(true);
      try {
        const res = await recommendationsApi.latest();
        applyRecommendation(res.recommendation, { announce: false, source: "reloadLatest" });
      } catch {
        // silently fail
      } finally {
        if (!silent) setIsLoading(false);
      }
    },
    [applyRecommendation],
  );

  const refreshNow = useCallback(async () => {
    if (!hasSession()) return;
    setIsRefreshing(true);
    try {
      const res = await recommendationsApi.refresh();
      if (res.recommendation) {
        applyRecommendation(res.recommendation, { announce: true, source: "refreshNow" });
      }
    } catch {
      // keep previous
    } finally {
      setIsRefreshing(false);
    }
  }, [applyRecommendation]);

  const setFromEventBatch = useCallback(
    (res: EventsResponse) => {
      console.debug("[PIPE FE] EVENT_BATCH", {
        triggered: res.triggered,
        trigger_reason: res.trigger_reason,
        inserted: res.inserted,
        has_rec: Boolean(res.recommendation),
        rec_id: res.recommendation?.id,
        generated_at: res.recommendation?.generated_at,
      });
      if (!res.triggered || !hasSession()) return;
      if (res.recommendation) {
        applyRecommendation(res.recommendation, { announce: true, source: "event_response" });
        return;
      }
      void (async () => {
        try {
          const latest = await recommendationsApi.latest();
          if (latest.recommendation) {
            applyRecommendation(latest.recommendation, {
              announce: true,
              source: "event_triggered_latest_fetch",
            });
          }
        } catch {
          // ignore
        }
      })();
    },
    [applyRecommendation],
  );

  const dismissToast = useCallback(() => {
    if (recommendationRef.current) markDismissed(recommendationRef.current.id);
    setToastOpen(false);
  }, []);

  useEffect(() => {
    __RECOMMENDATION_PROVIDER_MOUNT_COUNT += 1;
    if (__RECOMMENDATION_PROVIDER_MOUNT_COUNT > 1) {
      console.warn("[PIPE FE] MULTIPLE_RECOMMENDATION_PROVIDERS", {
        count: __RECOMMENDATION_PROVIDER_MOUNT_COUNT,
      });
    }
    if (!user || !token) {
      applyRecommendation(null, { announce: false });
      setToastOpen(false);
      setJustUpdated(false);
      return;
    }

    void reloadLatest(true);

    const id = window.setInterval(async () => {
      if (!hasSession()) return;
      if (__RECOMMENDATIONS_POLL_LOCK) {
        console.debug("[PIPE FE] STATUS_POLL_SKIPPED_LOCK");
        return;
      }
      __RECOMMENDATIONS_POLL_LOCK = true;
      try {
        console.debug("[PIPE FE] STATUS_POLL_RUN", { ts: new Date().toISOString() });
        const s = await recommendationsApi.status();
        const gen = s.last_generated_at;
        if (gen && gen !== lastGeneratedAt.current) {
          console.debug("[PIPE FE] POLL_NEW_GEN", { gen, prev: lastGeneratedAt.current });
          const res = await recommendationsApi.latest();
          if (res.recommendation) {
            applyRecommendation(res.recommendation, { announce: true, source: "status_poll" });
          }
        }
      } catch {
        // ignore
      } finally {
        __RECOMMENDATIONS_POLL_LOCK = false;
      }
    }, 15_000);

    return () => {
      window.clearInterval(id);
      if (highlightTimer.current) clearTimeout(highlightTimer.current);
      __RECOMMENDATION_PROVIDER_MOUNT_COUNT = Math.max(0, __RECOMMENDATION_PROVIDER_MOUNT_COUNT - 1);
    };
  }, [user, token, reloadLatest, applyRecommendation]);

  return (
    <RecommendationContext.Provider
      value={{
        recommendation,
        isLoading,
        isRefreshing,
        justUpdated,
        toastOpen,
        dismissToast,
        reloadLatest,
        refreshNow,
        setFromEventBatch,
      }}
    >
      {children}
    </RecommendationContext.Provider>
  );
}

export function useRecommendation() {
  const ctx = useContext(RecommendationContext);
  if (!ctx) throw new Error("useRecommendation must be used within RecommendationProvider");
  return ctx;
}
