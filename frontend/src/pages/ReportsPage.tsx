import { useCallback, useEffect, useState } from "react";
import { getFullReport, getReports, refreshReports } from "../api/terminal";
import type { FullReportPayload, ReportItem } from "../api/types";
import { ArtifactCenter } from "../components/artifacts/ArtifactCenter";
import { EmptyState } from "../components/common/EmptyState";
import { ErrorBoundary } from "../components/common/ErrorBoundary";
import { ErrorState } from "../components/common/ErrorState";
import { LoadingState } from "../components/common/LoadingState";
import { StatusPill } from "../components/common/StatusPill";
import { ReportCenter } from "../components/reports/ReportCenter";
import { usePolling } from "../hooks/usePolling";

function mergeFullReport(reports: ReportItem[], full?: FullReportPayload | null): ReportItem[] {
  if (!full?.type) return reports;
  return reports.map((report) =>
    report.type === full.type
      ? {
          ...report,
          title: full.title || report.title,
          generated_at: full.generated_at || report.generated_at,
          data_cutoff: full.data_cutoff || report.data_cutoff,
          markdown: full.markdown || report.markdown,
          disclaimer: full.disclaimer || report.disclaimer
        }
      : report
  );
}

export function ReportsPage({ showSampleData = true }: { showSampleData?: boolean }) {
  const loader = useCallback(() => getReports(), []);
  const { data, error, loading, refresh } = usePolling<ReportItem[]>(loader, 60000);
  const [fullReport, setFullReport] = useState<FullReportPayload | null>(null);
  const [fullError, setFullError] = useState("");
  const [taskMessage, setTaskMessage] = useState("");

  const reports = (data || []).filter((report) => showSampleData || !report.sample_mode);
  const selectedType = fullReport?.type || reports[0]?.type || "daily";

  const loadFullReport = useCallback(async (type = selectedType) => {
    setFullError("");
    try {
      setFullReport(await getFullReport(type));
    } catch (exc) {
      setFullError(exc instanceof Error ? exc.message : "报告全文暂时无法加载。");
    }
  }, [selectedType]);

  useEffect(() => {
    if (reports.length) void loadFullReport(reports[0].type || "daily");
  }, [reports.length]); // eslint-disable-line react-hooks/exhaustive-deps

  async function generateReports() {
    setTaskMessage("正在生成报告...");
    const result = await refreshReports();
    setTaskMessage(result.message_zh || "报告刷新完成。");
    await refresh();
    await loadFullReport(selectedType);
  }

  if (loading) return <LoadingState />;
  if (error) return <ErrorState message={error} onRetry={refresh} />;

  return (
    <ErrorBoundary moduleName="报告中心">
      <div className="page-stack">
        {reports.length ? (
          <>
            <div className="button-row">
              <button className="primary-button" type="button" onClick={() => void generateReports()}>
                生成报告
              </button>
              {fullError ? <StatusPill label={fullError} tone="warn" /> : null}
              {taskMessage ? <StatusPill label={taskMessage} tone="info" /> : null}
            </div>
            <ReportCenter
              reports={mergeFullReport(reports, fullReport)}
              onReportSelect={(report) => void loadFullReport(report.type || "daily")}
            />
          </>
        ) : (
          <div className="empty-action-panel">
            <EmptyState label="暂无报告，请先运行报告生成任务。" />
            <button className="primary-button" type="button" onClick={() => void generateReports()}>
              点击生成报告
            </button>
            {taskMessage ? <StatusPill label={taskMessage} tone="info" /> : null}
          </div>
        )}
        <ArtifactCenter />
      </div>
    </ErrorBoundary>
  );
}
