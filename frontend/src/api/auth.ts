import { apiFetch } from "./client";
import type { TokenResponse, User } from "@/types/api";

export const authApi = {
  signup(email: string, password: string) {
    return apiFetch<TokenResponse>("/auth/signup", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    });
  },
  login(email: string, password: string) {
    return apiFetch<TokenResponse>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    });
  },
  me() {
    return apiFetch<User>("/auth/me");
  },
};
