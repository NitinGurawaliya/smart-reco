export interface User {
  id: number;
  email: string;
  role: "user" | "admin";
  created_at: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: "bearer";
  user: User;
}

export interface EventPayload {
  event_type: "view" | "search" | "click" | "time_spent";
  source: "udemy";
  raw_metadata: Record<string, unknown>;
}

export interface EventOut {
  id: number;
  user_id: number;
  event_type: string;
  source: string;
  raw_metadata: Record<string, unknown>;
  created_at: string;
}

export interface EventsResponse {
  inserted: number;
  triggered: boolean;
  trigger_reason: string | null;
  recommendation: RecommendationOut | null;
}

export interface FreeResourceOut {
  id: number;
  title: string;
  description: string;
  topic_tags: string[];
  youtube_url: string;
  level: string;
  category: string;
  sync_status: "pending" | "synced" | "failed";
  created_at: string;
  updated_at: string;
}

export interface RecommendedResourceOut extends FreeResourceOut {
  because?: string | null;
}

export interface RecommendationSourceSummary {
  family?: string | null;
  dominant_pattern?: string;
  themes?: string[];
  top_categories?: string[];
  family_counts?: Record<string, number>;
  event_count?: number;
}

export interface RecommendationOut {
  id: number;
  user_id: number;
  narrative: string;
  resource_ids: number[];
  trigger_reason: string;
  generated_at: string;
  expires_at: string;
  resources: RecommendedResourceOut[];
  match_meta?: { theme?: string; dominant_pattern?: string; resource_id?: number; because?: string }[];
  source_summary?: RecommendationSourceSummary;
}

export interface LatestRecommendationResponse {
  recommendation: RecommendationOut | null;
}

export interface AgentStatus {
  has_recommendation: boolean;
  new_event_count: number;
  threshold: number;
  events_until_next: number;
  cooldown_seconds: number;
  cooldown_remaining_seconds: number;
  ready_to_run: boolean;
  blocked_by_cooldown: boolean;
  last_generated_at: string | null;
  last_trigger_reason: string | null;
  expires_at: string | null;
  resource_ids: number[];
  status_label: string;
}

export interface CatalogCreatePayload {
  title: string;
  description: string;
  topic_tags: string[];
  youtube_url: string;
  level: string;
  category: string;
}

export interface MockCourse {
  id: string;
  title: string;
  instructor: string;
  price: number;
  rating: number;
  students: number;
  category: string;
  level: string;
  shortDescription: string;
  topics: string[];
}
