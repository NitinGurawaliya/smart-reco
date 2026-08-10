import { createContext, useContext, useState, useEffect, useCallback, type ReactNode } from "react";
import { authApi } from "@/api/auth";
import { authStorage } from "@/lib/authStorage";
import { eventTracker } from "@/lib/eventTracker";
import type { User, TokenResponse } from "@/types/api";

interface AuthContextValue {
  user: User | null;
  token: string | null;
  isLoading: boolean;
  login(email: string, password: string): Promise<TokenResponse>;
  signup(email: string, password: string): Promise<TokenResponse>;
  logout(): void;
  refreshMe(): Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(authStorage.getUser());
  const [token, setToken] = useState<string | null>(authStorage.getToken());
  const [isLoading, setIsLoading] = useState(false);

  const store = useCallback((res: TokenResponse) => {
    eventTracker.clear();
    authStorage.setToken(res.access_token);
    authStorage.setUser(res.user);
    setToken(res.access_token);
    setUser(res.user);
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    setIsLoading(true);
    try {
      const res = await authApi.login(email, password);
      store(res);
      return res;
    } finally {
      setIsLoading(false);
    }
  }, [store]);

  const signup = useCallback(async (email: string, password: string) => {
    setIsLoading(true);
    try {
      const res = await authApi.signup(email, password);
      store(res);
      return res;
    } finally {
      setIsLoading(false);
    }
  }, [store]);

  const logout = useCallback(() => {
    eventTracker.clear();
    authStorage.clear();
    setUser(null);
    setToken(null);
  }, []);

  const refreshMe = useCallback(async () => {
    try {
      const u = await authApi.me();
      authStorage.setUser(u);
      setUser(u);
    } catch {
      logout();
    }
  }, [logout]);

  // On mount, if we have a token but no user, refresh
  useEffect(() => {
    if (authStorage.getToken() && !authStorage.getUser()) {
      refreshMe();
    }
  }, [refreshMe]);

  return (
    <AuthContext.Provider value={{ user, token, isLoading, login, signup, logout, refreshMe }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
