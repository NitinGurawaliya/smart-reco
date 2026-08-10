import { useMemo } from "react";
import { RefreshCw, BookOpen } from "lucide-react";
import { useRecommendation } from "@/contexts/RecommendationContext";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import type { RecommendationOut } from "@/types/api";
import { cn } from "@/lib/utils";
import { ResourceCardGrid } from "@/components/RecommendationCard";

function snapshotTags(rec: RecommendationOut | null): string[] {
  const cats = rec?.source_summary?.top_categories;
  if (cats && cats.length > 0) return cats.slice(0, 5);
  const themes = (rec?.match_meta ?? [])
    .map((m) => m.theme)
    .filter((t): t is string => Boolean(t));
  return themes.slice(0, 5);
}

function dominantPattern(rec: RecommendationOut): string {
  const fromSummary = rec.source_summary?.dominant_pattern;
  if (fromSummary) return fromSummary;
  const meta = rec.match_meta ?? [];
  const explicit = meta.find((m) => m.dominant_pattern)?.dominant_pattern;
  if (explicit) return explicit;
  const themes = meta.map((m) => m.theme).filter(Boolean) as string[];
  if (themes.length) return themes.slice(0, 2).join(" and ");
  return "your interests";
}

/** Ambient free-path panel on Browse — always reflects shared RecommendationContext. */
export function BrowseRecommendationPanel() {
  const { recommendation, isLoading, isRefreshing, justUpdated, refreshNow } =
    useRecommendation();

  const tags = useMemo(() => snapshotTags(recommendation), [recommendation]);
  const hero = recommendation?.resources?.[0];
  const secondary = recommendation?.resources?.slice(1, 3) ?? [];

  return (
    <aside
      className={cn(
        "  p-4 sm:p-5 transition-shadow duration-500",
        justUpdated
          ? "border-[#0F8B8D] shadow-lg shadow-[#0F8B8D]/20 ring-2 ring-[#0F8B8D]/25"
          : "border-[#D1CAB8]",
      )}
      aria-live="polite"
    >
      <div className="flex items-start justify-between gap-3 mb-3">
        <div className="min-w-0">
          <p className="text-[16px] font-semibold uppercase tracking-wider text-[#0F8B8D] flex items-center gap-1.5">
            Free Resources based on your interests 
            {justUpdated && (
              <span className="ml-1 rounded-full bg-[#0F8B8D] px-2 py-0.5 text-[10px] font-semibold normal-case tracking-normal text-white animate-fade-in">
                Updated
              </span>
            )}
          </p>
          {recommendation && (
            <p className="text-xs text-[#9CA3AF] mt-0.5">
              Focused on {dominantPattern(recommendation)}
            </p>
          )}
        </div>
        <Button
          variant="outline"
          size="sm"
          className="shrink-0 h-8 gap-1.5"
          disabled={isRefreshing}
          onClick={() => void refreshNow()}
        >
          <RefreshCw className={cn("h-3.5 w-3.5", isRefreshing && "animate-spin")} />
          {isRefreshing ? "Updating…" : "Refresh"}
        </Button>
      </div>

      {isLoading && !recommendation ? (
        <div className="space-y-2">
          <Skeleton className="h-4 w-2/3" />
          <Skeleton className="h-20 w-full rounded-xl" />
        </div>
      ) : recommendation && hero ? (
        <div className="space-y-3">
          {tags.length > 0 && (
            <div className="flex flex-wrap gap-1.5">
              {tags.map((t) => (
                <span
                  key={t}
                  className="px-2 py-0.5 rounded-full bg-[#e6f4f4] text-[11px] font-medium text-[#0a6e70]"
                >
                  {t}
                </span>
              ))}
            </div>
          )}

          <p className="font-display text-base sm:text-lg font-semibold text-[#0B1F33] leading-snug">
            {recommendation.narrative}
          </p>

          <ResourceCardGrid hero={hero} secondary={secondary} />
        </div>
      ) : (
        <div className="flex gap-3 items-start text-sm text-[#6B7280]">
          <BookOpen className="h-5 w-5 text-[#D1CAB8] shrink-0 mt-0.5" />
          <p>
            Still getting a feel for what you&apos;re into. Keep browsing related courses — a free
            path will settle here when a clear interest emerges.
          </p>
        </div>
      )}
    </aside>
  );
}