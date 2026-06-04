import { useCallback, useEffect, useMemo, useState } from "react";
import { getBacktestDiagnostics, getResearchBacktestReport, runResearchBacktest } from "../api/terminal";
import type { BacktestDiagnostics, ResearchBacktestHorizon, ResearchBacktestPayload } from "../api/types";
import { BacktestPanel } from "../components/backtest/BacktestPanel";
import { CostSensitivityPanel } from "../components/backtest/CostSensitivityPanel";
import { InstitutionalValidationPanel } from "../components/backtest/InstitutionalValidationPanel";
import { RegimePerformancePanel } from "../components/backtest/RegimePerformancePanel";
import { DrawdownChart } from "../components/charts/DrawdownChart";
import { EquityCurveChart } from "../components/charts/EquityCurveChart";
import { DataTable } from "../components/common/DataTable";
import { EmptyState } from "../components/common/EmptyState";
import { ErrorBoundary } from "../components/common/ErrorBoundary";
import { ErrorState } from "../components/common/ErrorState";
import { LoadingState } from "../components/common/LoadingState";
import { TechnicalDetailsDrawer } from "../components/common/TechnicalDetailsDrawer";
import { SectionCard } from "../components/layout/SectionCard";
import { usePolling } from "../hooks/usePolling";
import { formatNullable, formatNumber, toFiniteNumber } from "../utils/format";

const horizons = [
  ["next_5m", "5分钟"],
  ["next_15m", "15分钟"],
  ["next_30m", "30分钟"],
  ["next_hour", "1小时"],
  ["tomorrow", "1日"],
  ["one_to_two_weeks", "1-2周"],
  ["one_to_three_months", "1-3个月"]
];

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value) ? (value as Record<string, unknown>) : {};
}

function asArray<T = unknown>(value: unknown): T[] {
  return Array.isArray(value) ? (value as T[]) : [];
}

function normalizeResearchBacktest(payload?: ResearchBacktestPayload | null): ResearchBacktestPayload | null {
  const record = asRecord(payload);
  if (!Object.keys(record).length) return null;

  const normalizedHorizons = Object.fromEntries(
    Object.entries(asRecord(record.horizons)).map(([horizon, value]) => {
      const row = asRecord(value);
      return [
        horizon,
        {
          ...row,
          metrics: asRecord(row.metrics)
        } as ResearchBacktestHorizon
      ];
    })
  );

  return {
    ...record,
    horizons: normalizedHorizons
  } as ResearchBacktestPayload;
}

function backtestRows(payload?: ResearchBacktestPayload | null) {
  return Object.entries(asRecord(payload?.horizons)).map(([horizon, value]) => {
    const row = asRecord(value) as ResearchBacktestHorizon;
    const metrics = asRecord(row.metrics);
    return {
      horizon,
      status: formatNullable(row.status, "待验证"),
      trade_count: metrics.trade_count,
      total_return: metrics.total_return,
      max_drawdown: metrics.max_drawdown,
      sharpe: metrics.sharpe,
      dsr: metrics.deflated_sharpe_ratio ?? metrics.DSR,
      pbo: metrics.probability_of_backtest_overfitting ?? metrics.PBO,
      reality_check: metrics.reality_check_p_value ?? metrics.reality_check,
      equity_curve_path: row.equity_curve_path,
      drawdown_curve_path: row.drawdown_curve_path,
      trades_path: row.trades_path,
      metrics_path: row.metrics_path,
    };
  });
}

function curveRows(payload: ResearchBacktestPayload | null, key: "equity_curve" | "drawdown_curve") {
  for (const value of Object.values(asRecord(payload?.horizons))) {
    const rows = asArray<Record<string, unknown>>(asRecord(value)[key])
      .map((item) => {
        const point = asRecord(item);
        const valueField = key === "equity_curve" ? point.value ?? point.equity : point.value ?? point.drawdown;
        const number = toFiniteNumber(valueField);
        if (number === null) return null;
        return {
          ts: formatNullable(point.ts ?? point.time, ""),
          value: number
        };
      })
      .filter((item): item is { ts: string; value: number } => item !== null);
    if (rows.length) return rows;
  }
  return [];
}

export function BacktestPage() {
  const [horizon, setHorizon] = useState("tomorrow");
  const [researchVersion, setResearchVersion] = useState("v4");
  const [researchBacktest, setResearchBacktest] = useState<ResearchBacktestPayload | null>(null);
  const [researchReportLoading, setResearchReportLoading] = useState(false);
  const [researchLoading, setResearchLoading] = useState(false);
  const [researchError, setResearchError] = useState<string | null>(null);
  const loader = useCallback(() => getBacktestDiagnostics(horizon), [horizon]);
  const { data, error, loading, refresh } = usePolling<BacktestDiagnostics>(loader, 60000);
  const researchRows = useMemo(() => backtestRows(researchBacktest), [researchBacktest]);
  const equityCurve = useMemo(() => curveRows(researchBacktest, "equity_curve"), [researchBacktest]);
  const drawdownCurve = useMemo(() => curveRows(researchBacktest, "drawdown_curve"), [researchBacktest]);

  const loadResearchBacktestReport = useCallback(async () => {
    setResearchReportLoading(true);
    setResearchError(null);
    try {
      const report = await getResearchBacktestReport(undefined, researchVersion);
      setResearchBacktest(normalizeResearchBacktest(report));
    } catch (err) {
      setResearchBacktest(null);
      setResearchError(err instanceof Error ? err.message : "研究回测报告暂时无法读取。");
    } finally {
      setResearchReportLoading(false);
    }
  }, [researchVersion]);

  useEffect(() => {
    void loadResearchBacktestReport();
  }, [loadResearchBacktestReport]);

  async function handleRunResearchBacktest() {
    setResearchLoading(true);
    setResearchError(null);
    try {
      await runResearchBacktest({ candidate_version: researchVersion, horizons: ["1d", "3d", "5d", "10d", "20d"] });
      const report = await getResearchBacktestReport(undefined, researchVersion);
      setResearchBacktest(normalizeResearchBacktest(report));
    } catch (err) {
      setResearchError(err instanceof Error ? err.message : "研究型回测暂时无法运行。");
    } finally {
      setResearchLoading(false);
    }
  }

  return (
    <div className="page-stack">
      <SectionCard
        title="回测验证 Backtest Validation"
        subtitle="普通回测指标、Walk-forward、成本压力、Regime 压力、DSR/PBO、Reality Check 和不可上线原因。"
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
        subtitle="研究回测，不代表 live active 预测，不构成投资建议。只使用 OOF 样本外信号。"
        actions={
          <button className="secondary-button" type="button" onClick={handleRunResearchBacktest} disabled={researchLoading}>
            运行 {researchVersion} 研究回测
          </button>
        }
      >
        <div className="control-grid">
          <label>
            research backtest selector / version selector
            <select value={researchVersion} onChange={(event) => setResearchVersion(event.target.value)}>
              <option value="v10">candidate_v10</option>
              <option value="v9">candidate_v9</option>
              <option value="v8">candidate_v8</option>
              <option value="v7">candidate_v7</option>
              <option value="v6">candidate_v6</option>
              <option value="v4">candidate_v4</option>
              <option value="v3">candidate_v3</option>
            </select>
          </label>
        </div>
        <div className="notice-card">
          <strong>研究边界</strong>
          <span>只用 OOF 信号，不用 in-sample prediction，不发布 active，不生成客户预测，不接 baseline。</span>
        </div>
        {researchReportLoading ? <LoadingState label="正在读取研究回测报告..." /> : null}
        {researchLoading ? <LoadingState label="正在基于 OOF trace 生成研究回测..." /> : null}
        {researchError ? <ErrorState message={researchError} onRetry={handleRunResearchBacktest} /> : null}
        {!researchReportLoading && !researchLoading && !researchError && !researchRows.length ? (
          <>
            <EmptyState
              label="暂无研究回测数据"
              description="当前 candidate 还没有可读取的 research backtest 报告；页面保持空状态，不会发布 active 或生成客户预测。"
            />
            <div className="two-column">
              <EquityCurveChart data={[]} />
              <DrawdownChart data={[]} />
            </div>
          </>
        ) : null}
        {researchRows.length ? (
          <div className="two-column">
            <EquityCurveChart data={equityCurve} />
            <DrawdownChart data={drawdownCurve} />
          </div>
        ) : null}
        {researchRows.length ? (
          <DataTable
            data={researchRows}
            columns={[
              { key: "horizon", title: "Horizon" },
              { key: "status", title: "状态" },
              { key: "trade_count", title: "交易数", render: (row) => formatNumber(Number(row.trade_count), 0) },
              { key: "total_return", title: "总收益", render: (row) => formatNullable(row.total_return) },
              { key: "max_drawdown", title: "最大回撤", render: (row) => formatNullable(row.max_drawdown) },
              { key: "sharpe", title: "Sharpe", render: (row) => formatNullable(row.sharpe) },
              { key: "dsr", title: "DSR", render: (row) => formatNullable(row.dsr) },
              { key: "pbo", title: "PBO", render: (row) => formatNullable(row.pbo) },
              { key: "reality_check", title: "Reality Check", render: (row) => formatNullable(row.reality_check) },
            ]}
          />
        ) : null}
        {researchRows.length ? (
          <TechnicalDetailsDrawer title="技术明细">
            <DataTable
              data={researchRows}
              columns={[
                { key: "horizon", title: "Horizon" },
                { key: "equity_curve_path", title: "Equity curve CSV", render: (row) => formatNullable(row.equity_curve_path) },
                { key: "drawdown_curve_path", title: "Drawdown curve CSV", render: (row) => formatNullable(row.drawdown_curve_path) },
                { key: "trades_path", title: "Trades CSV", render: (row) => formatNullable(row.trades_path) },
                { key: "metrics_path", title: "Metrics JSON", render: (row) => formatNullable(row.metrics_path) },
              ]}
            />
          </TechnicalDetailsDrawer>
        ) : null}
        <div className="metric-grid compact">
          <div className="metric-card">
            <span className="metric-label">Cost stress</span>
            <strong>1x / 2x / 3x</strong>
            <small>metrics JSON 中归档</small>
          </div>
          <div className="metric-card">
            <span className="metric-label">Regime stress</span>
            <strong>high/low vol, trend, range</strong>
            <small>机构级验证面板展示</small>
          </div>
          <div className="metric-card">
            <span className="metric-label">导出</span>
            <strong>CSV / JSON / Markdown</strong>
            <small>{formatNullable(researchBacktest?.report_path, "等待生成报告")}</small>
          </div>
        </div>
      </SectionCard>
    </div>
  );
}
