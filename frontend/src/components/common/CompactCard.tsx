import type { ReactNode } from "react";

export function CompactCard({ title, value, note }: { title: string; value: ReactNode; note?: ReactNode }) {
  return (
    <div className="compact-card">
      <span>{title}</span>
      <strong>{value}</strong>
      {note ? <small>{note}</small> : null}
    </div>
  );
}

