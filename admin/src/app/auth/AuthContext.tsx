/* eslint-disable react-refresh/only-export-components */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import { API_ROOT } from "../../shared/config/env";

type Role = "admin" | "moderator" | "user";

type AuthState = {
  accessToken: string | null;
  refreshToken: string | null;
  email: string | null;
  roles: Role[];
};

type LoginPayload = {
  access_token: string;
  refresh_token: string;
};

type MePayload = {
  email: string;
  roles: string[];
};

type AuthContextValue = {
  isLoading: boolean;
  isAuthenticated: boolean;
  email: string | null;
  roles: Role[];
  isAdminLike: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
};

const STORAGE_KEY = "km_admin_auth";

const AuthContext = createContext<AuthContextValue | null>(null);

function normalizeRoles(rawRoles: string[]): Role[] {
  const mapped = rawRoles.map((role) => role.toLowerCase()).filter(Boolean);
  const unique = Array.from(new Set(mapped));
  return unique.filter((role): role is Role => role === "admin" || role === "moderator" || role === "user");
}

function readStoredState(): AuthState {
  if (typeof window === "undefined") {
    return { accessToken: null, refreshToken: null, email: null, roles: [] };
  }

  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) {
      return { accessToken: null, refreshToken: null, email: null, roles: [] };
    }
    const parsed = JSON.parse(raw) as AuthState;
    return {
      accessToken: parsed.accessToken ?? null,
      refreshToken: parsed.refreshToken ?? null,
      email: parsed.email ?? null,
      roles: parsed.roles ?? [],
    };
  } catch {
    return { accessToken: null, refreshToken: null, email: null, roles: [] };
  }
}

function persistState(state: AuthState): void {
  if (typeof window === "undefined") {
    return;
  }
  localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
}

async function fetchMe(accessToken: string): Promise<MePayload> {
  const response = await fetch(`${API_ROOT}/auth/me`, {
    method: "GET",
    headers: {
      Authorization: `Bearer ${accessToken}`,
    },
  });

  if (!response.ok) {
    throw new Error("Failed to load current user");
  }

  return (await response.json()) as MePayload;
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [authState, setAuthState] = useState<AuthState>(() => readStoredState());
  const [isLoading, setIsLoading] = useState(true);

  const clearState = useCallback(() => {
    const emptyState: AuthState = { accessToken: null, refreshToken: null, email: null, roles: [] };
    setAuthState(emptyState);
    persistState(emptyState);
  }, []);

  const hydrate = useCallback(async () => {
    const stored = readStoredState();
    if (!stored.accessToken) {
      setIsLoading(false);
      return;
    }

    try {
      const me = await fetchMe(stored.accessToken);
      const nextState: AuthState = {
        ...stored,
        email: me.email,
        roles: normalizeRoles(me.roles ?? []),
      };
      setAuthState(nextState);
      persistState(nextState);
    } catch {
      clearState();
    } finally {
      setIsLoading(false);
    }
  }, [clearState]);

  useEffect(() => {
    void hydrate();
  }, [hydrate]);

  const login = useCallback(async (email: string, password: string) => {
    const response = await fetch(`${API_ROOT}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });

    if (!response.ok) {
      const message = response.status === 401 ? "Invalid credentials" : "Login failed";
      throw new Error(message);
    }

    const payload = (await response.json()) as LoginPayload;
    const me = await fetchMe(payload.access_token);

    const nextState: AuthState = {
      accessToken: payload.access_token,
      refreshToken: payload.refresh_token,
      email: me.email,
      roles: normalizeRoles(me.roles ?? []),
    };

    setAuthState(nextState);
    persistState(nextState);
  }, []);

  const logout = useCallback(async () => {
    if (authState.refreshToken) {
      await fetch(`${API_ROOT}/auth/logout`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_token: authState.refreshToken }),
      }).catch(() => {
        return undefined;
      });
    }

    clearState();
  }, [authState.refreshToken, clearState]);

  const value = useMemo<AuthContextValue>(() => {
    const isAuthenticated = Boolean(authState.accessToken);
    const isAdminLike = authState.roles.includes("admin") || authState.roles.includes("moderator");

    return {
      isLoading,
      isAuthenticated,
      email: authState.email,
      roles: authState.roles,
      isAdminLike,
      login,
      logout,
    };
  }, [authState.accessToken, authState.email, authState.roles, isLoading, login, logout]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used inside AuthProvider");
  }
  return context;
}
