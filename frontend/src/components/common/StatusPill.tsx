import clsx from "clsx";

export function StatusPill({
  label,
  tone = "neutral"
}: {
  label: string;
  tone?: "good" | "warn" | "bad" | "neutral" | "info";
}) {
  return <span className={clsx("status-pill", `tone-${tone}`)}>{label}</span>;
}
