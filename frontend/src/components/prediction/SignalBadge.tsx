import clsx from "clsx";
import { formatSignal } from "../../utils/format";

export function SignalBadge({ signal }: { signal?: string }) {
  const label = formatSignal(signal);
  const tone = label.includes("多头") ? "long" : label.includes("空头") ? "short" : label.includes("降级") ? "warn" : "neutral";
  return <span className={clsx("signal-badge", tone)}>{label}</span>;
}
