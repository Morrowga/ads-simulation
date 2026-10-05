/**
 * Fetch wrapper: bearer access token kept in memory, one automatic refresh on 401 (refresh token
 * lives in an httpOnly cookie set by the API), errors mapped to AppError, uploads with progress.
 */
import { API_URL } from "./config";
import { AppError, toAppError } from "./errors";
import type { TokenOut } from "./types";

export const AUTH_HINT_COOKIE = "advar_auth";

let accessToken: string | null = null;
let refreshPromise: Promise<string | null> | null = null;
const listeners = new Set<(token: string | null) => void>();

export function getAccessToken(): string | null {
  return accessToken;
}

export function setAccessToken(token: string | null): void {
  accessToken = token;
  if (typeof document !== "undefined") {
    // UX-only hint for the middleware redirect; the API is the real gate.
    document.cookie = token
      ? `${AUTH_HINT_COOKIE}=1; path=/; max-age=${60 * 60 * 24 * 30}; samesite=lax`
      : `${AUTH_HINT_COOKIE}=; path=/; max-age=0; samesite=lax`;
  }
  listeners.forEach((fn) => fn(token));
}

export function onTokenChange(fn: (token: string | null) => void): () => void {
  listeners.add(fn);
  return () => listeners.delete(fn);
}

/** Refresh the access token once, de-duplicated across concurrent callers. */
export async function refreshAccessToken(): Promise<string | null> {
  if (!refreshPromise) {
    refreshPromise = (async () => {
      try {
        const res = await fetch(`${API_URL}/auth/refresh`, { method: "POST", credentials: "include" });
        if (!res.ok) {
          setAccessToken(null);
          return null;
        }
        const data = (await res.json()) as TokenOut;
        setAccessToken(data.access_token);
        return data.access_token;
      } catch {
        setAccessToken(null);
        return null;
      } finally {
        refreshPromise = null;
      }
    })();
  }
  return refreshPromise;
}

export interface RequestOptions {
  method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  body?: unknown;
  query?: Record<string, string | number | boolean | null | undefined>;
  signal?: AbortSignal;
  /** internal: set after a refresh retry */
  retried?: boolean;
  /** skip the automatic refresh (e.g. for the refresh endpoint itself) */
  noAuth?: boolean;
}

function buildUrl(path: string, query?: RequestOptions["query"]): string {
  const url = new URL(`${API_URL}${path}`);
  if (query) {
    for (const [k, v] of Object.entries(query)) {
      if (v !== undefined && v !== null && v !== "") url.searchParams.set(k, String(v));
    }
  }
  return url.toString();
}

export async function api<T>(path: string, init: RequestOptions = {}): Promise<T> {
  const headers: Record<string, string> = { Accept: "application/json" };
  if (init.body !== undefined) headers["Content-Type"] = "application/json";
  if (accessToken && !init.noAuth) headers.Authorization = `Bearer ${accessToken}`;
  let res: Response;
  try {
    res = await fetch(buildUrl(path, init.query), {
      method: init.method ?? "GET",
      headers,
      body: init.body !== undefined ? JSON.stringify(init.body) : undefined,
      credentials: "include",
      signal: init.signal,
    });
  } catch (e) {
    if (e instanceof DOMException && e.name === "AbortError") throw e;
    throw new AppError("network_error", "Network error", 0);
  }
  if (res.status === 401 && !init.retried && !init.noAuth) {
    const token = await refreshAccessToken();
    if (token) return api<T>(path, { ...init, retried: true });
  }
  if (!res.ok) {
    let body: unknown = null;
    try {
      body = await res.json();
    } catch {
      body = null;
    }
    throw toAppError(res.status, body);
  }
  if (res.status === 204) return undefined as T;
  const text = await res.text();
  return (text ? JSON.parse(text) : undefined) as T;
}

export const get = <T>(path: string, query?: RequestOptions["query"], signal?: AbortSignal) =>
  api<T>(path, { query, signal });
export const post = <T>(path: string, body?: unknown, query?: RequestOptions["query"]) =>
  api<T>(path, { method: "POST", body, query });
export const put = <T>(path: string, body?: unknown) => api<T>(path, { method: "PUT", body });
export const patch = <T>(path: string, body?: unknown) => api<T>(path, { method: "PATCH", body });
export const del = <T>(path: string) => api<T>(path, { method: "DELETE" });

/**
 * Multipart upload with progress events (XMLHttpRequest, because fetch has no upload progress).
 * Retries once after a token refresh on 401.
 */
export function upload<T>(
  path: string,
  file: File,
  onProgress?: (pct: number) => void,
  fieldName = "file",
  retried = false,
): Promise<T> {
  return new Promise<T>((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", buildUrl(path));
    xhr.withCredentials = true;
    xhr.responseType = "json";
    if (accessToken) xhr.setRequestHeader("Authorization", `Bearer ${accessToken}`);
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable && onProgress) onProgress(Math.round((e.loaded / e.total) * 100));
    };
    xhr.onerror = () => reject(new AppError("network_error", "Network error", 0));
    xhr.onload = async () => {
      if (xhr.status === 401 && !retried) {
        const token = await refreshAccessToken();
        if (token) {
          upload<T>(path, file, onProgress, fieldName, true).then(resolve, reject);
          return;
        }
      }
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve(xhr.response as T);
      } else {
        reject(toAppError(xhr.status, xhr.response));
      }
    };
    const form = new FormData();
    form.append(fieldName, file, file.name);
    xhr.send(form);
  });
}
