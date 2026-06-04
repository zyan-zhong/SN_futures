import { sanitizeRecord } from "../utils/sanitize";

const API_BASE = (import.meta.env.VITE_API_BASE_URL || "").replace(/\/$/, "");
const DEFAULT_TIMEOUT_MS = 15000;
const REQUEST_DEDUPE = new Map<string, Promise<unknown>>();

type RequestOptions = {
  timeoutMs?: number;
  dedupe?: boolean;
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function endpoint(path: string): string {
  return `${API_BASE}${path.startsWith("/") ? path : `/${path}`}`;
}

async function parseResponse<T>(response: Response): Promise<T> {
  const text = await response.text();
  let payload: unknown = null;
  try {
    payload = text ? JSON.parse(text) : null;
  } catch {
    const suffix = response.ok ? "请稍后重试或查看运行日志。" : text.slice(0, 120).trim();
    throw new Error(`服务返回了不可解析的数据，HTTP ${response.status}${suffix ? `：${suffix}` : ""}`);
  }
  if (!response.ok) {
    const sanitized = sanitizeRecord(payload);
    const record = isRecord(sanitized) ? sanitized : {};
    const message = typeof record.message === "string" ? record.message : `请求失败，HTTP ${response.status}`;
    throw new Error(message);
  }
  return sanitizeRecord(payload) as T;
}

function normalizeRequestError(error: unknown, path: string, timeoutMs: number): Error {
  if (error instanceof DOMException && error.name === "AbortError") {
    return new Error(`请求超时：${path} 超过 ${timeoutMs}ms 未响应`);
  }
  if (error instanceof TypeError) {
    return new Error(`接口连接失败：${path} 暂时不可用，请确认后端服务已启动。`);
  }
  if (error instanceof Error) return error;
  return new Error(`接口请求失败：${path}`);
}

async function requestJson<T>(path: string, init: RequestInit, options: RequestOptions = {}): Promise<T> {
  const timeoutMs = options.timeoutMs ?? DEFAULT_TIMEOUT_MS;
  const controller = new AbortController();
  const timer = window.setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(endpoint(path), {
      ...init,
      signal: controller.signal
    });
    return await parseResponse<T>(response);
  } catch (error) {
    throw normalizeRequestError(error, path, timeoutMs);
  } finally {
    window.clearTimeout(timer);
  }
}

export async function getJson<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const dedupe = options.dedupe ?? true;
  const key = `GET:${path}`;
  if (dedupe && REQUEST_DEDUPE.has(key)) {
    return REQUEST_DEDUPE.get(key) as Promise<T>;
  }
  const promise = requestJson<T>(
    path,
    {
      method: "GET",
      headers: { Accept: "application/json" },
      credentials: "same-origin"
    },
    options
  );
  if (dedupe) {
    REQUEST_DEDUPE.set(key, promise);
    void promise.finally(() => REQUEST_DEDUPE.delete(key)).catch(() => undefined);
  }
  return promise;
}

export async function postJson<T>(path: string, body: unknown, options: RequestOptions = {}): Promise<T> {
  return requestJson<T>(
    path,
    {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json"
      },
      credentials: "same-origin",
      body: JSON.stringify(body)
    },
    { ...options, dedupe: false }
  );
}
