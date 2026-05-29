import { useState } from "react";
import { ErrorState } from "./components/common/ErrorState";
import { LoadingState } from "./components/common/LoadingState";
import { SampleModeBanner } from "./components/common/SampleModeBanner";
import { AppShell } from "./components/layout/AppShell";
import { FirstRunWizard } from "./components/onboarding/FirstRunWizard";
import { BacktestPage } from "./pages/BacktestPage";
import { DashboardPage } from "./pages/DashboardPage";
import { DataStatusPage } from "./pages/DataStatusPage";
import { EventPage } from "./pages/EventPage";
import { FactorPage } from "./pages/FactorPage";
import { ModelGovernancePage } from "./pages/ModelGovernancePage";
import { PositionPage } from "./pages/PositionPage";
import { PredictionPage } from "./pages/PredictionPage";
import { ReportsPage } from "./pages/ReportsPage";
import { ResearchLabPage } from "./pages/ResearchLabPage";
import { SettingsPage } from "./pages/SettingsPage";
import { useFirstRun } from "./hooks/useFirstRun";
import { useLocalSetting } from "./hooks/useLocalSetting";
import { useTerminalSnapshot } from "./hooks/useTerminalSnapshot";

export type PageKey =
  | "dashboard"
  | "predictions"
  | "factors"
  | "events"
  | "backtest"
  | "governance"
  | "research"
  | "position"
  | "reports"
  | "data"
  | "settings";

export default function App() {
  const [page, setPage] = useState<PageKey>("dashboard");
  const { data: snapshot, error, loading, refresh } = useTerminalSnapshot(30000);
  const firstRun = useFirstRun();
  const [showSampleData] = useLocalSetting("showSampleData", true);

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
    if (loading && !visibleSnapshot) return <LoadingState label="正在连接沪锡专业终端..." />;
    if (error && !visibleSnapshot) return <ErrorState message={error} onRetry={refresh} />;
    switch (page) {
      case "dashboard":
        return <DashboardPage snapshot={visibleSnapshot} onRefresh={refresh} showSampleData={showSampleData} />;
      case "predictions":
        return <PredictionPage snapshot={visibleSnapshot} onNavigate={setPage} onRefresh={refresh} showSampleData={showSampleData} />;
      case "factors":
        return <FactorPage showSampleData={showSampleData} />;
      case "events":
        return <EventPage onNavigate={setPage} showSampleData={showSampleData} />;
      case "backtest":
        return <BacktestPage />;
      case "governance":
        return <ModelGovernancePage snapshot={visibleSnapshot} />;
      case "research":
        return <ResearchLabPage />;
      case "position":
        return <PositionPage />;
      case "reports":
        return <ReportsPage showSampleData={showSampleData} />;
      case "data":
        return <DataStatusPage snapshot={visibleSnapshot} onNavigate={setPage} onRefresh={refresh} />;
      case "settings":
        return <SettingsPage />;
      default:
        return <DashboardPage snapshot={visibleSnapshot} showSampleData={showSampleData} />;
    }
  }

  return (
    <AppShell current={page} onNavigate={setPage} summary={visibleSnapshot?.summary}>
      <SampleModeBanner visible={Boolean(snapshot?.sample_mode && showSampleData)} message={snapshot?.sample_banner_zh} />
      {error && visibleSnapshot ? <div className="inline-warning">部分接口刷新失败，已保留上一版终端快照：{error}</div> : null}
      {renderPage()}
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
  );
}
