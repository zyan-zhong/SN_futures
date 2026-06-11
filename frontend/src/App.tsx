import { lazy, Suspense, useEffect, useState } from "react";
import { ErrorState } from "./components/common/ErrorState";
import { LoadingState } from "./components/common/LoadingState";
import { SampleModeBanner } from "./components/common/SampleModeBanner";
import { AppShell } from "./components/layout/AppShell";
import { FirstRunWizard } from "./components/onboarding/FirstRunWizard";
import { UIModeProvider } from "./context/UIModeContext";
import { useFirstRun } from "./hooks/useFirstRun";
import { useLocalSetting } from "./hooks/useLocalSetting";
import { useTerminalSnapshot } from "./hooks/useTerminalSnapshot";
import { DashboardPage } from "./pages/DashboardPage";
import { isDevConsoleEnabled } from "./utils/devMode";

const BacktestPage = lazy(() => import("./pages/BacktestPage").then((module) => ({ default: module.BacktestPage })));
const DataStatusPage = lazy(() => import("./pages/DataStatusPage").then((module) => ({ default: module.DataStatusPage })));
const EventPage = lazy(() => import("./pages/EventPage").then((module) => ({ default: module.EventPage })));
const FactorPage = lazy(() => import("./pages/FactorPage").then((module) => ({ default: module.FactorPage })));
const GovernanceConsolePage = lazy(() => import("./pages/GovernanceConsolePage").then((module) => ({ default: module.GovernanceConsolePage })));
const MarketMonitorPage = lazy(() => import("./pages/MarketMonitorPage").then((module) => ({ default: module.MarketMonitorPage })));
const ModelGovernancePage = lazy(() => import("./pages/ModelGovernancePage").then((module) => ({ default: module.ModelGovernancePage })));
const PositionPage = lazy(() => import("./pages/PositionPage").then((module) => ({ default: module.PositionPage })));
const PredictionPage = lazy(() => import("./pages/PredictionPage").then((module) => ({ default: module.PredictionPage })));
const ReportsPage = lazy(() => import("./pages/ReportsPage").then((module) => ({ default: module.ReportsPage })));
const ResearchLabPage = lazy(() => import("./pages/ResearchLabPage").then((module) => ({ default: module.ResearchLabPage })));
const SettingsPage = lazy(() => import("./pages/SettingsPage").then((module) => ({ default: module.SettingsPage })));
const TrainingDataPage = lazy(() => import("./pages/TrainingDataPage").then((module) => ({ default: module.TrainingDataPage })));
const TerminalOverviewPage = lazy(() => import("./pages/TerminalOverviewPage").then((module) => ({ default: module.TerminalOverviewPage })));
const PredictionWorkspacePage = lazy(() => import("./pages/PredictionWorkspacePage").then((module) => ({ default: module.PredictionWorkspacePage })));
const DataOnboardingPage = lazy(() => import("./pages/DataOnboardingPage").then((module) => ({ default: module.DataOnboardingPage })));
const CandidateResearchPage = lazy(() => import("./pages/CandidateResearchPage").then((module) => ({ default: module.CandidateResearchPage })));
const ResearchArchivePage = lazy(() => import("./pages/ResearchArchivePage").then((module) => ({ default: module.ResearchArchivePage })));
const PublicTerminalPage = lazy(() => import("./public_terminal/PublicTerminalPage").then((module) => ({ default: module.PublicTerminalPage })));
const PublicSetupPage = lazy(() => import("./public_terminal/PublicSetupPage").then((module) => ({ default: module.PublicSetupPage })));
const PublicDataStatusPage = lazy(() => import("./public_terminal/PublicDataStatusPage").then((module) => ({ default: module.PublicDataStatusPage })));
const PublicMarketPage = lazy(() => import("./public_terminal/PublicMarketPage").then((module) => ({ default: module.PublicMarketPage })));
const PublicEventCenterPage = lazy(() => import("./public_terminal/PublicEventCenterPage").then((module) => ({ default: module.PublicEventCenterPage })));
const PublicReportsPage = lazy(() => import("./public_terminal/PublicReportsPage").then((module) => ({ default: module.PublicReportsPage })));
const PublicDiagnosticsPage = lazy(() => import("./public_terminal/PublicDiagnosticsPage").then((module) => ({ default: module.PublicDiagnosticsPage })));

export type PageKey =
  | "public-home"
  | "public-setup"
  | "public-data-status"
  | "public-market"
  | "public-events"
  | "public-reports"
  | "public-diagnostics"
  | "dashboard"
  | "market"
  | "predictions"
  | "factors"
  | "events"
  | "training"
  | "backtest"
  | "governance"
  | "research-governance"
  | "research"
  | "position"
  | "reports"
  | "data"
  | "settings"
  | "terminal-overview"
  | "prediction-workspace"
  | "data-onboarding"
  | "candidate-research"
  | "research-archive";

export default function App() {
  const [page, setPage] = useState<PageKey>("public-home");
  const [uiMode, setUIMode] = useLocalSetting<"simple" | "professional">("uiMode", "simple");
  const [showSampleData] = useLocalSetting("showSampleData", false);
  const [autoStopBackendOnClose] = useLocalSetting("autoStopBackendOnClose", true);
  const devConsoleEnabled = isDevConsoleEnabled();
  const effectiveUIMode = devConsoleEnabled ? uiMode : "simple";
  const legacyTerminalAdaptersEnabled = devConsoleEnabled && effectiveUIMode === "professional";
  const firstRun = useFirstRun(legacyTerminalAdaptersEnabled);
  const { data: snapshot, error, loading, refresh } = useTerminalSnapshot(30000, legacyTerminalAdaptersEnabled);

  useEffect(() => {
    const isDesktopLaunch = new URLSearchParams(window.location.search).get("desktop") === "1";
    if (!autoStopBackendOnClose || !isDesktopLaunch) return undefined;
    const shutdownOnClose = () => {
      const payload = '{"reason":"frontend_unload"}';
      const blob = new Blob([payload], { type: "application/json" });
      if (navigator.sendBeacon) {
        navigator.sendBeacon("/api/terminal/system/shutdown", blob);
        return;
      }
      void fetch("/api/terminal/system/shutdown", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: payload,
        keepalive: true
      }).catch(() => undefined);
    };
    window.addEventListener("pagehide", shutdownOnClose);
    return () => window.removeEventListener("pagehide", shutdownOnClose);
  }, [autoStopBackendOnClose]);

  const visibleSnapshot = snapshot?.sample_mode && !showSampleData
    ? {
        ...snapshot,
        sample_mode: false,
        sample_banner_zh: undefined,
        predictions: [],
        summary: snapshot.summary
          ? {
              ...snapshot.summary,
              sample_mode: false,
              latest_price: null,
              current_signal: "观望",
              system_status: "暂无真实数据",
              data_quality_label: "数据暂缺"
            }
          : snapshot.summary
      }
    : snapshot;

  function renderPage() {
    if (loading && !visibleSnapshot && page === "dashboard") {
      return <LoadingState label="连接中..." />;
    }
    if (error && !visibleSnapshot && page === "dashboard") {
      return <ErrorState message={error} onRetry={refresh} />;
    }
    switch (page) {
      case "public-home":
        return <PublicTerminalPage />;
      case "public-setup":
        return <PublicSetupPage />;
      case "public-data-status":
        return <PublicDataStatusPage />;
      case "public-market":
        return <PublicMarketPage />;
      case "public-events":
        return <PublicEventCenterPage />;
      case "public-reports":
        return <PublicReportsPage />;
      case "public-diagnostics":
        return <PublicDiagnosticsPage />;
      case "dashboard":
        return <DashboardPage snapshot={visibleSnapshot} onRefresh={refresh} showSampleData={showSampleData} />;
      case "market":
        return <MarketMonitorPage />;
      case "events":
        return <EventPage onNavigate={setPage} showSampleData={showSampleData} />;
      case "factors":
        return <FactorPage showSampleData={showSampleData} />;
      case "training":
        return <TrainingDataPage />;
      case "research":
        return <ResearchLabPage />;
      case "backtest":
        return <BacktestPage />;
      case "predictions":
        return <PredictionPage snapshot={visibleSnapshot} onNavigate={setPage} onRefresh={refresh} showSampleData={showSampleData} />;
      case "reports":
        return <ReportsPage showSampleData={showSampleData} />;
      case "settings":
        return <SettingsPage />;
      case "data":
        return <DataStatusPage snapshot={visibleSnapshot} onNavigate={setPage} onRefresh={refresh} />;
      case "governance":
        return <ModelGovernancePage snapshot={visibleSnapshot} />;
      case "research-governance":
        return <GovernanceConsolePage />;
      case "position":
        return <PositionPage />;
      case "terminal-overview":
        return <TerminalOverviewPage />;
      case "prediction-workspace":
        return <PredictionWorkspacePage />;
      case "data-onboarding":
        return <DataOnboardingPage />;
      case "candidate-research":
        return <CandidateResearchPage onNavigate={setPage} />;
      case "research-archive":
        return <ResearchArchivePage />;
      default:
        return <PublicTerminalPage />;
    }
  }

  return (
    <UIModeProvider value={{ uiMode: effectiveUIMode, setUIMode }}>
      <AppShell
        current={page}
        onModeChange={setUIMode}
        onNavigate={setPage}
        showGlobalTaskBar={legacyTerminalAdaptersEnabled}
        summary={visibleSnapshot?.summary}
        uiMode={effectiveUIMode}
      >
        <SampleModeBanner visible={Boolean(snapshot?.sample_mode && showSampleData)} message={snapshot?.sample_banner_zh} />
        {error && visibleSnapshot ? <div className="inline-warning">接口刷新失败，保留上次数据：{error}</div> : null}
        <Suspense fallback={<LoadingState label="加载中..." />}>
          {renderPage()}
        </Suspense>
        {!firstRun.loading && firstRun.shouldShow ? (
          <FirstRunWizard
            settings={firstRun.settings}
            dataSources={firstRun.dataSources}
            systemHealth={firstRun.systemHealth}
            onRefresh={firstRun.refresh}
            onComplete={firstRun.complete}
          />
        ) : null}
      </AppShell>
    </UIModeProvider>
  );
}
