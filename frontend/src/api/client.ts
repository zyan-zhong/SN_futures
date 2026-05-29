import { sanitizeRecord } from "../utils/sanitize";

const API_BASE = (import.meta.env.VITE_API_BASE_URL || "").replace(/\/$/, "");

function endpoint(path: string): string {
  return `${API_BASE}${path.startsWith("/") ? path : `/${path}`}`;
}

async function parseResponse<T>(response: Response): Promise<T> {
  const text = await response.text();
  let payload: unknown = null;
  try {
    payload = text ? JSON.parse(text) : null;
  } catch {
    throw new Error(`服务返回了不可解析的数据，HTTP ${response.status}`);
  }
  if (!response.ok) {
    const record = sanitizeRecord(payload) as Record<string, unknown>;
    const message = typeof record.message === "string" ? record.message : `请求失败，HTTP ${response.status}`;
    throw new Error(message);
  }
  return sanitizeRecord(payload) as T;
}

export async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(endpoint(path), {
    method: "GET",
    headers: { Accept: "application/json" },
    credentials: "same-origin"
  });
  return parseResponse<T>(response);
}

export async function postJson<T>(path: string, body: unknown): Promise<T> {
  const response = await fetch(endpoint(path), {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json"
    },
    credentials: "same-origin",
    body: JSON.stringify(body)
  });
  return parseResponse<T>(response);
}
