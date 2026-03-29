function resolveLoopbackHost(): string {
  if (typeof window === "undefined") {
    return "localhost";
  }

  const host = window.location.hostname;
  if (host === "localhost" || host === "127.0.0.1") {
    return host;
  }

  return "localhost";
}

function defaultApiBaseUrl(): string {
  return `http://${resolveLoopbackHost()}:8000`;
}

const rawBaseUrl = import.meta.env.VITE_API_BASE_URL ?? defaultApiBaseUrl();
const rawApiPrefix = import.meta.env.VITE_API_PREFIX ?? "/api/v1";

function trimTrailingSlash(value: string): string {
  return value.endsWith("/") ? value.slice(0, -1) : value;
}

function ensureLeadingSlash(value: string): string {
  return value.startsWith("/") ? value : `/${value}`;
}

function normalizeApiBaseUrl(value: string): string {
  const trimmed = value.trim();

  if (!trimmed) {
    return defaultApiBaseUrl();
  }

  if (trimmed.startsWith(":")) {
    return `http://${resolveLoopbackHost()}${trimmed}`;
  }

  if (trimmed.startsWith("//")) {
    return `http:${trimmed}`;
  }

  if (!/^https?:\/\//i.test(trimmed)) {
    return `http://${trimmed}`;
  }

  return trimmed;
}

export const API_BASE_URL = trimTrailingSlash(normalizeApiBaseUrl(rawBaseUrl));
export const API_PREFIX = ensureLeadingSlash(trimTrailingSlash(rawApiPrefix));
export const API_ROOT = `${API_BASE_URL}${API_PREFIX}`;
