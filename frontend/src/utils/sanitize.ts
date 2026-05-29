const SENSITIVE_KEYS = ["key", "apikey", "apiKey", "token", "secret", "password", "authorization"];

function isSensitiveKey(key: string): boolean {
  const normalized = key.toLowerCase();
  return SENSITIVE_KEYS.some((item) => normalized.includes(item.toLowerCase()));
}

export function sanitizeText(value: unknown, fallback = "数据暂缺"): string {
  if (value === null || value === undefined) return fallback;
  if (typeof value === "number" && !Number.isFinite(value)) return fallback;
  const text = String(value);
  if (!text.trim() || ["nan", "none", "null", "undefined"].includes(text.trim().toLowerCase())) return fallback;
  return text;
}

export function maskSensitive(value: unknown): string {
  const text = sanitizeText(value, "");
  if (!text) return "已脱敏";
  if (text.length <= 8) return "已脱敏";
  return `${text.slice(0, 3)}***${text.slice(-3)}`;
}

export function sanitizeRecord<T = unknown>(input: T): T {
  if (Array.isArray(input)) {
    return input.map((item) => sanitizeRecord(item)) as T;
  }
  if (input && typeof input === "object") {
    const output: Record<string, unknown> = {};
    for (const [key, value] of Object.entries(input as Record<string, unknown>)) {
      output[key] = isSensitiveKey(key) ? maskSensitive(value) : sanitizeRecord(value);
    }
    return output as T;
  }
  if (typeof input === "number" && !Number.isFinite(input)) {
    return null as T;
  }
  return input;
}

export function removeSensitiveKeys<T = unknown>(input: T): T {
  if (Array.isArray(input)) return input.map((item) => removeSensitiveKeys(item)) as T;
  if (input && typeof input === "object") {
    const output: Record<string, unknown> = {};
    for (const [key, value] of Object.entries(input as Record<string, unknown>)) {
      if (!isSensitiveKey(key)) output[key] = removeSensitiveKeys(value);
    }
    return output as T;
  }
  return input;
}
