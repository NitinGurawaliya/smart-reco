import { ExternalLink } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { YoutubeIcon } from "@/components/ui/youtube";
import type { RecommendedResourceOut } from "@/types/api";

export function ResourceCard({
  resource,
  isHero = false,
}: {
  resource: RecommendedResourceOut;
  isHero?: boolean;
}) {
  return (
    <a
      href={resource.youtube_url}
      target="_blank"
      rel="noopener noreferrer"
      className="group block bg-white border border-[#D1CAB8] rounded-lg p-5 hover:-translate-y-0.5 hover:shadow-md transition-all duration-200"
    >
      <div className="flex items-start justify-between gap-3 mb-3">
        <div className="flex-1 min-w-0">
          <h3 className="font-display font-semibold text-[#0B1F33] text-base leading-snug line-clamp-2 group-hover:text-[#0F8B8D] transition-colors">
            {resource.title}
          </h3>
          {resource.because && (
            <p className="text-xs text-[#0F8B8D] mt-0.5 line-clamp-1">{resource.because}</p>
          )}
        </div>
        <span className="shrink-0 flex items-center gap-1 font-semibold text-[#0F8B8D] text-sm">
          <YoutubeIcon /> Free
        </span>
      </div>

      <p className="text-sm text-[#6B7280] line-clamp-2 mb-4">{resource.description}</p>

      <div className="flex items-center justify-between">
        <span className="inline-flex items-center gap-1 text-xs font-semibold text-[#0F8B8D]">
          Watch free <ExternalLink className="h-3 w-3" />
        </span>
        <div className="flex items-center gap-1.5">
          <Badge variant="outline" className="text-[10px] px-2 py-0">{resource.level}</Badge>
          <Badge className="text-[10px] px-2 py-0 bg-[#e6f4f4] text-[#0a6e70]">{resource.category}</Badge>
        </div>
      </div>

      {isHero && (
        <div className="mt-3 pt-3 border-t border-[#D1CAB8]/60">
          <span className="text-[10px] font-semibold uppercase tracking-wider text-[#0F8B8D]">Top pick</span>
        </div>
      )}
    </a>
  );
}

export function ResourceCardGrid({
  hero,
  secondary,
}: {
  hero: RecommendedResourceOut;
  secondary: RecommendedResourceOut[];
}) {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
      <ResourceCard resource={hero} isHero />
      {secondary.map((r) => (
        <ResourceCard key={r.id} resource={r} />
      ))}
    </div>
  );
}