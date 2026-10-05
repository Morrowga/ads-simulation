"use client";

/** Auth context: access token in memory, `me` from the API, login/logout helpers. */
import { QueryClient, QueryClientProvider, useQuery, useQueryClient } from "@tanstack/react-query";
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { api, getAccessToken, onTokenChange, post, refreshAccessToken, setAccessToken } from "./api";
import { isAppError } from "./errors";
import type { MeOut, TokenOut } from "./types";

interface AuthContextValue {
  /** null while the initial refresh is running */
  ready: boolean;
  token: string | null;
  me: MeOut | null | undefined;
  isAdmin: boolean;
  login: (email: string, password: string) => Promise<TokenOut>;
  logout: () => Promise<void>;
  refetchMe: () => Promise<unknown>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function makeQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 15_000,
        retry: (count, error) => {
          if (isAppError(error) && error.status >= 400 && error.status < 500) return false;
          return count < 2;
        },
        refetchOnWindowFocus: false,
      },
    },
  });
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(getAccessToken());
  const [ready, setReady] = useState(false);
  const queryClient = useQueryClient();

  useEffect(() => onTokenChange(setToken), []);

  useEffect(() => {
    // On first load: try to get an access token from the refresh cookie.
    let cancelled = false;
    refreshAccessToken().finally(() => {
      if (!cancelled) setReady(true);
    });
    return () => {
      cancelled = true;
    };
  }, []);

  const meQuery = useQuery({
    queryKey: ["me"],
    queryFn: () => api<MeOut>("/me"),
    enabled: ready && !!token,
  });

  const login = useCallback(
    async (email: string, password: string) => {
      const data = await post<TokenOut>("/auth/login", { email, password });
      setAccessToken(data.access_token);
      await queryClient.invalidateQueries({ queryKey: ["me"] });
      return data;
    },
    [queryClient],
  );

  const logout = useCallback(async () => {
    try {
      await post("/auth/logout");
    } catch {
      // the cookie is cleared server-side; a failed call must not block logging out locally
    }
    setAccessToken(null);
    queryClient.clear();
  }, [queryClient]);

  const value = useMemo<AuthContextValue>(
    () => ({
      ready,
      token,
      me: token ? meQuery.data : null,
      isAdmin: !!token && meQuery.data?.role === "admin",
      login,
      logout,
      refetchMe: () => queryClient.invalidateQueries({ queryKey: ["me"] }),
    }),
    [ready, token, meQuery.data, login, logout, queryClient],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}

export function Providers({ children }: { children: ReactNode }) {
  const [client] = useState(makeQueryClient);
  return (
    <QueryClientProvider client={client}>
      <AuthProvider>{children}</AuthProvider>
    </QueryClientProvider>
  );
}
