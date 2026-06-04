import type { ReactNode } from "react";

export function PageActionBar({
  title,
  description,
  actions
}: {
  title: string;
  description?: string;
  actions?: ReactNode;
}) {
  return (
    <div className="page-action-bar">
      <div>
        <h2 className="page-toolbar-title">{title}</h2>
        {description ? <p className="page-toolbar-description">{description}</p> : null}
      </div>
      {actions ? <div className="page-toolbar-actions">{actions}</div> : null}
    </div>
  );
}
