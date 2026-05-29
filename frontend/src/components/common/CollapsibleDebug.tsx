import { sanitizeRecord } from "../../utils/sanitize";
import { COPY } from "../../utils/copy";

export function CollapsibleDebug({ data }: { data: unknown }) {
  const debugTitle = COPY.debugTitle || "技术明细 / 开发调试信息";
  return (
    <details className="debug-panel">
      <summary>{debugTitle}</summary>
      <pre>{JSON.stringify(sanitizeRecord(data), null, 2)}</pre>
    </details>
  );
}
