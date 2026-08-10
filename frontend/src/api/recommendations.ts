import { apiFetch } from "./client";
import type { AgentStatus, LatestRecommendationResponse } from "@/types/api";

export const recommendationsApi = {
  latest() {
    return apiFetch<LatestRecommendationResponse>("/recommendations/latest");
  },
  status() {
    return apiFetch<AgentStatus>("/recommendations/status");
  },
  refresh() {
    return apiFetch<LatestRecommendationResponse>("/recommendations/refresh", {
      method: "POST",
    });
  },
};
