const rawBaseUrl = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";
const rawApiPrefix = import.meta.env.VITE_API_PREFIX ?? "/api/v1";

function trimTrailingSlash(value: string): string {
  return value.endsWith("/") ? value.slice(0, -1) : value;
}

function ensureLeadingSlash(value: string): string {
  return value.startsWith("/") ? value : `/${value}`;
}

export const API_BASE_URL = trimTrailingSlash(rawBaseUrl);
export const API_PREFIX = ensureLeadingSlash(trimTrailingSlash(rawApiPrefix));
export const API_ROOT = `${API_BASE_URL}${API_PREFIX}`;
