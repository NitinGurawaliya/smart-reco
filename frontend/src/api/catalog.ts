import { apiFetch } from "./client";
import type { FreeResourceOut, CatalogCreatePayload } from "@/types/api";

export const catalogApi = {
  list() {
    return apiFetch<FreeResourceOut[]>("/catalog");
  },
  get(id: number) {
    return apiFetch<FreeResourceOut>(`/catalog/${id}`);
  },
  create(payload: CatalogCreatePayload) {
    return apiFetch<FreeResourceOut>("/catalog", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },
  update(id: number, payload: Partial<CatalogCreatePayload>) {
    return apiFetch<FreeResourceOut>(`/catalog/${id}`, {
      method: "PUT",
      body: JSON.stringify(payload),
    });
  },
  delete(id: number) {
    return apiFetch<void>(`/catalog/${id}`, { method: "DELETE" });
  },
  resync(id: number) {
    return apiFetch<FreeResourceOut>(`/catalog/${id}/resync`, { method: "POST" });
  },
};
