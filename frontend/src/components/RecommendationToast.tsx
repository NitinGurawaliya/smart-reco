import { Sparkles, X } from "lucide-react";
import { useRecommendation } from "@/contexts/RecommendationContext";

/**
 * Lightweight update signal only — full path lives in the Browse panel.
 * Must not show recommendation content that isn't also in shared context/panel.
 */
export function RecommendationToast() {
  const { toastOpen, justUpdated, dismissToast, recommendation } = useRecommendation();

  if (!toastOpen || !recommendation || !justUpdated) return null;

  return (
    <div
      className="fixed bottom-4 right-4 z-50 w-[min(100vw-2rem,18rem)] animate-fade-in"
      role="status"
      aria-live="polite"
    >
      <div className="rounded-xl border border-[#0F8B8D]/40 bg-white shadow-lg px-3 py-2.5 flex items-start gap-2">
        <Sparkles className="h-4 w-4 text-[#0F8B8D] shrink-0 mt-0.5" />
        <p className="flex-1 text-sm text-[#0B1F33] leading-snug">
          Free path updated — see the panel on Browse.
        </p>
        <button
          type="button"
          onClick={dismissToast}
          className="text-[#9CA3AF] hover:text-[#0B1F33] p-0.5"
          aria-label="Dismiss"
        >
          <X className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
}
