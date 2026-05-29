import { useCallback, useState } from "react";
import { getBacktestDiagnostics, getResearchBacktestReport, runResearchBacktest } from "../api/terminal";
import type { BacktestDiagnostics, ResearchBacktestPayload } from "../api/types";
import { BacktestPanel } from "../components/backtest/BacktestPanel";
import { CostSensitivityPanel } from "../components/backtest/CostSensitivityPanel";
import { InstitutionalValidationPanel } from "../components/backtest/InstitutionalValidationPanel";
import { RegimePerformancePanel } from "../components/backtest/RegimePerformancePanel";
import { ErrorBoundary } from "../components/common/ErrorBoundary";
import { ErrorState } from "../components/common/ErrorState";
import { LoadingState } from "../components/common/LoadingState";
import { SectionCard } from "../components/layout/SectionCard";
import { usePolling } from "../hooks/usePolling";

const horizons = [
  ["next_5m", "5分钟"],
  ["next_15m", "15分钟"],
  ["next_30m", "30分钟"],
  ["next_hour", "1小时"],
  ["tomorrow", "1日"],
  ["one_to_two_weeks", "1-2周"],
  ["one_to_three_months", "1-3个月"]
];

export function BacktestPage() {
  const [horizon, setHorizon] = useState("tomorrow");
  const [researchBacktest, setResearchBacktest] = useState<ResearchBacktestPayload | null>(null);
  const [researchLoading, setResearchLoading] = useState(false);
  const [researchError, setResearchError] = useState<string | null>(null);
  const loader = useCallback(() => getBacktestDiagnostics(horizon), [horizon]);
  const { data, error, loading, refresh } = usePolling<BacktestDiagnostics>(loader, 60000);

  async function handleRunResearchBacktest() {
    setResearchLoading(true);
    setResearchError(null);
    try {
      const result = await runResearchBacktest({ candidate_version: "v3", horizons: ["1d", "3d", "5d", "10d", "20d"] });
      const report = await getResearchBacktestReport(undefined, "v3");
      setResearchBacktest({ ...result, markdown: report.markdown });
    } catch (err) {
      setResearchError(err instanceof Error ? err.message : "研究型回测暂时无法运行。");
    } finally {
      setResearchLoading(false);
    }
  }

  return (
    <div className="page-stack">
      <SectionCard
        title="回测与 Walk-forward"
        subtitle="按周期查看成本后指标、walk-forward、成本敏感性、市场状态分组和机构级验证。"
        actions={
          <select aria-label="选择回测周期" value={horizon} onChange={(event) => setHorizon(event.target.value)}>
            {horizons.map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        }
      >
        <ErrorBoundary moduleName="Walk-forward 回测指标">
          {loading ? (
            <LoadingState />
          ) : error ? (
            <ErrorState message={error} onRetry={refresh} />
          ) : (
            <BacktestPanel diagnostics={data || undefined} />
          )}
        </ErrorBoundary>
      </SectionCard>

      <ErrorBoundary moduleName="回测分组图表">
        <div className="two-column">
          <CostSensitivityPanel data={data?.cost_sensitivity} />
          <RegimePerformancePanel data={data?.by_regime} />
        </div>
      </ErrorBoundary>

      <ErrorBoundary moduleName="机构级验证">
        <InstitutionalValidationPanel />
      </ErrorBoundary>

      <SectionCard
        title="研究型收益曲线"
        subtitle="研究回测，不代表 live active 预测，不构成投资建议。"
        actions={<button className="secondary-button" type="button" onClick={handleRunResearchBacktest} disabled={researchLoading}>运行 v3 研究回测</button>}
      >
        {researchLoading ? <LoadingState label="正在基于 OOF trace 生成研究回测..." /> : null}
        {researchError ? <ErrorState message={researchError} onRetry={handleRunResearchBacktest} /> : null}
        <div className="notice-card">
          <strong>研究边界</strong>
          <span>只使用样本外 OOF 信号；不使用 in-sample prediction，不发布 active，不生成客户预测。</span>
        </div>
        {researchBacktest?.horizons ? (
          <div className="data-table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Horizon</th>
                  <th>Status</th>
                  <th>Trade Count</th>
                  <th>Total Return</th>
                  <th>Max Drawdown</th>
                  <th>Equity Path</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(researchBacktest.horizons).map(([key, value]) => (
                  <tr key={key}>
                    <td>{key}</td>
                    <td>{value.status ?? "-"}</td>
                    <td>{String(value.metrics?.trade_count ?? "-")}</td>
                    <td>{String(value.metrics?.total_return ?? "-")}</td>
                    <td>{String(value.metrics?.max_drawdown ?? "-")}</td>
                    <td>{value.equity_curve_path ?? "-"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="empty-state">暂无 v3 研究回测结果，请先生成 candidate_v3 OOF trace。</div>
        )}
        {researchBacktest?.report_path ? (
          <div className="notice-card">
            <strong>报告路径</strong>
            <span>{researchBacktest.report_path}</span>
          </div>
        ) : null}
      </SectionCard>
    </div>
  );
}
