import type { ReactNode } from "react";
import type { TerminalSummary } from "../../api/types";
import type { PageKey } from "../../App";
import { COPY } from "../../utils/copy";
import { ErrorBoundary } from "../common/ErrorBoundary";
import type { UIMode } from "../../context/UIModeContext";
import { GlobalTaskBar } from "../task/GlobalTaskBar";
import { SimpleSidebar } from "./SimpleSidebar";
import { TopStatusBar } from "./TopStatusBar";

export function AppShell({
  current,
  onNavigate,
  onModeChange,
  summary,
  uiMode,
  children
}: {
  current: PageKey;
  onNavigate: (page: PageKey) => void;
  onModeChange: (mode: UIMode) => void;
  summary?: TerminalSummary;
  uiMode: UIMode;
  children: ReactNode;
}) {
  return (
    <div className={`app-shell ${uiMode === "simple" ? "simple-mode" : "professional-mode"}`}>
      <SimpleSidebar current={current} mode={uiMode} onModeChange={onModeChange} onNavigate={onNavigate} />
      <div className="workspace">
        <TopStatusBar summary={summary} />
        <main>
          <ErrorBoundary moduleName="主内容区域" onHome={() => onNavigate("dashboard")}>
            {children}
          </ErrorBoundary>
        </main>
        <footer className="compliance-footer">{COPY.disclaimer}</footer>
      </div>
      <GlobalTaskBar />
    </div>
  );
}
