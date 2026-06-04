import { sanitizeRecord } from "../../utils/sanitize";
import { COPY } from "../../utils/copy";

function summarizeDebugData(data: unknown): string {
  const sanitized = sanitizeRecord(data);
  if (!sanitized || typeof sanitized !== "object") return String(sanitized ?? "empty");
  if (Array.isArray(sanitized)) {
    const first = sanitized[0];
    const keys = first && typeof first === "object" ? Object.keys(first as Record<string, unknown>).slice(0, 8).join(", ") : "items";
    return `array(${sanitized.length}) ${keys}`;
  }
  const keys = Object.keys(sanitized as Record<string, unknown>).slice(0, 12);
  return keys.length ? `keys: ${keys.join(", ")}` : "empty object";
}

export function CollapsibleDebug({ data }: { data: unknown }) {
  const debugTitle = COPY.debugTitle || "技术明细 / 开发调试信息";
  return (
    <details className="debug-panel">
      <summary>{debugTitle}</summary>
      <code className="debug-summary">{summarizeDebugData(data)}</code>
    </details>
  );
}
