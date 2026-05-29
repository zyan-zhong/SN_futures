import type { ReactNode } from "react";
import type { TerminalSummary } from "../../api/types";
import type { PageKey } from "../../App";
import { COPY } from "../../utils/copy";
import { ErrorBoundary } from "../common/ErrorBoundary";
import { Sidebar } from "./Sidebar";
import { TopStatusBar } from "./TopStatusBar";

export function AppShell({
  current,
  onNavigate,
  summary,
  children
}: {
  current: PageKey;
  onNavigate: (page: PageKey) => void;
  summary?: TerminalSummary;
  children: ReactNode;
}) {
  return (
    <div className="app-shell">
      <Sidebar current={current} onNavigate={onNavigate} />
      <div className="workspace">
        <TopStatusBar summary={summary} />
        <main>
          <ErrorBoundary moduleName="主内容区域" onHome={() => onNavigate("dashboard")}>
            {children}
          </ErrorBoundary>
        </main>
        <footer className="compliance-footer">{COPY.disclaimer}</footer>
      </div>
    </div>
  );
}
