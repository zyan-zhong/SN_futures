import clsx from "clsx";
import { formatStatusLabel, getStatusTone, type StatusTone } from "../../utils/statusTaxonomy";

export function StatusPill({
  label,
  tone,
  formatLabel = false
}: {
  label: string;
  tone?: StatusTone;
  formatLabel?: boolean;
}) {
  const displayLabel = formatLabel ? formatStatusLabel(label) : label;
  const displayTone = tone ?? getStatusTone(label);
  return (
    <span
      aria-label={`状态：${displayLabel}`}
      className={clsx("status-pill", `tone-${displayTone}`)}
      data-tone={displayTone}
      title={displayLabel}
    >
      {displayLabel}
    </span>
  );
}
