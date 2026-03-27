/* eslint-disable react-refresh/only-export-components */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
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
  authFetch: (path: string, init?: RequestInit) => Promise<Response>;
};

const STORAGE_KEY = "km_admin_auth";

const AuthContext = createContext<AuthContextValue | null>(null);

type ApiErrorEnvelope = {
  error?: {
    code?: string;
    message?: string;
  };
  detail?: unknown;
};

class ApiHttpError extends Error {
  status: number;
  code?: string;
  detail?: unknown;

  constructor(status: number, message: string, code?: string, detail?: unknown) {
    super(message);
    this.name = "ApiHttpError";
    this.status = status;
    this.code = code;
    this.detail = detail;
  }
}

function isApiHttpError(error: unknown): error is ApiHttpError {
  return error instanceof ApiHttpError;
}

function toApiUrl(path: string): string {
  const isAbsolute = path.startsWith("http://") || path.startsWith("https://");
  if (isAbsolute) {
    return path;
  }

  const normalized = path.startsWith("/") ? path : `/${path}`;
  return `${API_ROOT}${normalized}`;
}

async function buildApiError(response: Response, fallback: string): Promise<ApiHttpError> {
  let payload: ApiErrorEnvelope | null = null;

  try {
    payload = (await response.json()) as ApiErrorEnvelope;
  } catch {
    payload = null;
  }

  const detailMessage = typeof payload?.detail === "string" ? payload.detail : undefined;
  const message = payload?.error?.message ?? detailMessage ?? fallback;

  return new ApiHttpError(response.status, message, payload?.error?.code, payload?.detail);
}

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
  const response = await fetch(toApiUrl("/auth/me"), {
    method: "GET",
    headers: {
      Authorization: `Bearer ${accessToken}`,
    },
  });

  if (!response.ok) {
    throw await buildApiError(response, "Failed to load current user");
  }

  return (await response.json()) as MePayload;
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [authState, setAuthState] = useState<AuthState>(() => readStoredState());
  const [isLoading, setIsLoading] = useState(true);
  const refreshInFlightRef = useRef<Promise<AuthState | null> | null>(null);

  const applyState = useCallback((nextState: AuthState) => {
    setAuthState(nextState);
    persistState(nextState);
  }, []);

  const clearState = useCallback(() => {
    const emptyState: AuthState = { accessToken: null, refreshToken: null, email: null, roles: [] };
    applyState(emptyState);
  }, [applyState]);

  const refreshSession = useCallback(async (): Promise<AuthState | null> => {
    const current = readStoredState();
    if (!current.refreshToken) {
      clearState();
      return null;
    }

    if (refreshInFlightRef.current) {
      return refreshInFlightRef.current;
    }

    refreshInFlightRef.current = (async () => {
      try {
        const refreshResponse = await fetch(toApiUrl("/auth/refresh"), {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ refresh_token: current.refreshToken }),
        });

        if (!refreshResponse.ok) {
          throw await buildApiError(refreshResponse, "Session refresh failed");
        }

        const refreshedTokens = (await refreshResponse.json()) as LoginPayload;
        const me = await fetchMe(refreshedTokens.access_token);

        const nextState: AuthState = {
          accessToken: refreshedTokens.access_token,
          refreshToken: refreshedTokens.refresh_token,
          email: me.email,
          roles: normalizeRoles(me.roles ?? []),
        };

        applyState(nextState);
        return nextState;
      } catch {
        clearState();
        return null;
      } finally {
        refreshInFlightRef.current = null;
      }
    })();

    return refreshInFlightRef.current;
  }, [applyState, clearState]);

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
      applyState(nextState);
    } catch (error) {
      if (isApiHttpError(error) && error.status === 401 && stored.refreshToken) {
        const refreshed = await refreshSession();
        if (refreshed) {
          return;
        }
      }
      clearState();
    } finally {
      setIsLoading(false);
    }
  }, [applyState, clearState, refreshSession]);

  useEffect(() => {
    void hydrate();
  }, [hydrate]);

  const login = useCallback(async (email: string, password: string) => {
    const response = await fetch(toApiUrl("/auth/login"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });

    if (!response.ok) {
      throw await buildApiError(response, response.status === 401 ? "Invalid credentials" : "Login failed");
    }

    const payload = (await response.json()) as LoginPayload;
    const me = await fetchMe(payload.access_token);

    const nextState: AuthState = {
      accessToken: payload.access_token,
      refreshToken: payload.refresh_token,
      email: me.email,
      roles: normalizeRoles(me.roles ?? []),
    };

    applyState(nextState);
  }, [applyState]);

  const logout = useCallback(async () => {
    const current = readStoredState();

    if (current.refreshToken) {
      await fetch(toApiUrl("/auth/logout"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_token: current.refreshToken }),
      }).catch(() => {
        return undefined;
      });
    }

    clearState();
  }, [clearState]);

  const authFetch = useCallback(
    async (path: string, init?: RequestInit): Promise<Response> => {
      const withToken = async (accessToken: string): Promise<Response> => {
        const headers = new Headers(init?.headers);
        headers.set("Authorization", `Bearer ${accessToken}`);
        return fetch(toApiUrl(path), {
          ...init,
          headers,
        });
      };

      const current = readStoredState();
      if (!current.accessToken) {
        throw new Error("Session expired. Please sign in again.");
      }

      let response = await withToken(current.accessToken);
      if (response.status !== 401) {
        return response;
      }

      const refreshed = await refreshSession();
      if (!refreshed?.accessToken) {
        throw new Error("Session expired. Please sign in again.");
      }

      response = await withToken(refreshed.accessToken);
      if (response.status === 401) {
        clearState();
        throw new Error("Session expired. Please sign in again.");
      }

      return response;
    },
    [clearState, refreshSession],
  );

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
      authFetch,
    };
  }, [authState.accessToken, authState.email, authState.roles, authFetch, isLoading, login, logout]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used inside AuthProvider");
  }
  return context;
}
