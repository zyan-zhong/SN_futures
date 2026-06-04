import type { ReactNode } from "react";

export function TechnicalDetailsDrawer({
  title = "技术明细",
  children
}: {
  title?: string;
  children: ReactNode;
}) {
  return (
    <details className="technical-details-drawer">
      <summary>{title}</summary>
      <div className="technical-details-body">{children}</div>
    </details>
  );
}
