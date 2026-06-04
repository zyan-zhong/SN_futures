import type { ReactNode } from "react";
import { PageActionBar } from "./PageActionBar";

export function PageToolbar({
  title,
  subtitle,
  actions
}: {
  title: string;
  subtitle?: string;
  actions?: ReactNode;
}) {
  return <PageActionBar actions={actions} description={subtitle} title={title} />;
}
