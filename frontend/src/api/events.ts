import { apiFetch } from "./client";
import type { EventPayload, EventsResponse, EventOut } from "@/types/api";

export const eventsApi = {
  post(events: EventPayload[]) {
    return apiFetch<EventsResponse>("/events", {
      method: "POST",
      body: JSON.stringify({ events }),
    });
  },
  list(limit = 50) {
    return apiFetch<EventOut[]>(`/events?limit=${limit}`);
  },
};
