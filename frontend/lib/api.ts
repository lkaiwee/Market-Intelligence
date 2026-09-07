const API_BASE = (
  process.env.NEXT_PUBLIC_API_BASE_URL ||
  (process.env.NEXT_PUBLIC_GITHUB_PAGES === "true" ? "" : "http://127.0.0.1:8000")
).replace(/\/$/, "");

export const API_ACCESS_REQUIRED_EVENT = "market-intelligence:access-required";

let sessionToken: string | null | undefined;
let accessRevision = 0;

export function hasApiBaseUrl(): boolean {
  return Boolean(API_BASE);
}

function tokenStorageKey(): string {
  return `market-intelligence:owner-access:${new URL(API_BASE).origin}`;
}

export function getApiAccessToken(): string | null {
  if (typeof window === "undefined") return null;

  if (sessionToken === undefined) {
    try {
      sessionToken = window.sessionStorage.getItem(tokenStorageKey());
    } catch {
      // Access still works for this page if the browser disables session storage.
      sessionToken = null;
    }
  }

  return sessionToken;
}

export function setApiAccessToken(token: string | null): void {
  accessRevision += 1;
  sessionToken = token;
  if (typeof window === "undefined") return;

  try {
    if (token) {
      window.sessionStorage.setItem(tokenStorageKey(), token);
    } else {
      window.sessionStorage.removeItem(tokenStorageKey());
    }
  } catch {
    // Keep the token in memory only when session storage is unavailable.
  }
}

function apiUrl(path: string): string {
  if (!API_BASE) {
    throw new Error(
      "Backend not connected. This GitHub Pages site hosts the frontend. Live market data and portfolio features need a separately hosted API.",
    );
  }
  return `${API_BASE}${path}`;
}

async function parseResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    let message = await response.text();

    try {
      const parsed = JSON.parse(message);
      message = parsed.detail || message;
    } catch {
      // Keep raw response text.
    }

    throw new Error(`${response.status} ${message}`);
  }

  return response.json();
}

export async function getApiAccess(
  signal: AbortSignal,
): Promise<{ authentication_required: boolean }> {
  const response = await fetch(apiUrl("/api/access"), {
    cache: "no-store",
    headers: { Accept: "application/json" },
    signal,
  });
  const access = await parseResponse<{ authentication_required: boolean }>(response);

  if (typeof access.authentication_required !== "boolean") {
    throw new Error("The API returned an invalid access configuration.");
  }

  return access;
}

export async function checkApiAccess(
  token: string,
  signal: AbortSignal,
): Promise<boolean> {
  const response = await fetch(apiUrl("/api/access/check"), {
    cache: "no-store",
    headers: {
      Accept: "application/json",
      Authorization: `Bearer ${token}`,
    },
    signal,
  });

  if (response.status === 401) return false;
  if (!response.ok) throw new Error("Could not verify access with the API.");
  return true;
}

async function apiRequest<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = getApiAccessToken();
  const requestRevision = accessRevision;
  const headers = new Headers(init.headers);
  headers.set("Accept", "application/json");
  if (token) headers.set("Authorization", `Bearer ${token}`);

  const response = await fetch(apiUrl(path), {
    ...init,
    cache: "no-store",
    headers,
  });

  // A request from an earlier session must not lock a newly authenticated one.
  if (response.status === 401 && requestRevision === accessRevision) {
    setApiAccessToken(null);
    if (typeof window !== "undefined") {
      window.dispatchEvent(new Event(API_ACCESS_REQUIRED_EVENT));
    }
  }

  return parseResponse<T>(response);
}

export async function apiGet<T>(path: string): Promise<T> {
  return apiRequest<T>(path);
}

export async function apiPost<T>(
  path: string,
  body?: unknown,
): Promise<T> {
  return apiRequest<T>(path, {
    method: "POST",
    headers: {
      ...(body !== undefined
        ? { "Content-Type": "application/json" }
        : {}),
    },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
}

export async function apiPut<T>(
  path: string,
  body: unknown,
): Promise<T> {
  return apiRequest<T>(path, {
    method: "PUT",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body),
  });
}

export async function apiDelete<T>(path: string): Promise<T> {
  return apiRequest<T>(path, {
    method: "DELETE",
  });
}
