const API_BASE = (
  process.env.NEXT_PUBLIC_API_BASE_URL ||
  (process.env.NEXT_PUBLIC_GITHUB_PAGES === "true" ? "" : "http://127.0.0.1:8000")
).replace(/\/$/, "");

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

export async function apiGet<T>(path: string): Promise<T> {
  const response = await fetch(apiUrl(path), {
    cache: "no-store",
  });

  return parseResponse<T>(response);
}

export async function apiPost<T>(
  path: string,
  body?: unknown,
): Promise<T> {
  const response = await fetch(apiUrl(path), {
    method: "POST",
    headers: {
      Accept: "application/json",
      ...(body !== undefined
        ? { "Content-Type": "application/json" }
        : {}),
    },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });

  return parseResponse<T>(response);
}

export async function apiPut<T>(
  path: string,
  body: unknown,
): Promise<T> {
  const response = await fetch(apiUrl(path), {
    method: "PUT",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body),
  });

  return parseResponse<T>(response);
}

export async function apiDelete<T>(path: string): Promise<T> {
  const response = await fetch(apiUrl(path), {
    method: "DELETE",
    headers: {
      Accept: "application/json",
    },
  });

  return parseResponse<T>(response);
}
