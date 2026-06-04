import { useCallback, useState } from "react";
import { getInstitutionalValidationReport, runInstitutionalValidation } from "../../api/terminal";
import type { InstitutionalValidationReport } from "../../api/types";
import { usePolling } from "../../hooks/usePolling";
import { formatNullable, formatNumber } from "../../utils/format";
import { DataTable } from "../common/DataTable";
import { ErrorState } from "../common/ErrorState";
import { LoadingState } from "../common/LoadingState";
import { SectionCard } from "../layout/SectionCard";

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value) ? (value as Record<string, unknown>) : {};
}

function rowsFromRecord(record?: Record<string, Record<string, unknown>>) {
  return Object.entries(asRecord(record)).map(([scenario, payload]) => ({ scenario, ...asRecord(payload) }));
}

export function InstitutionalValidationPanel() {
  const loader = useCallback(() => getInstitutionalValidationReport(), []);
  const { data, error, loading, refresh } = usePolling<InstitutionalValidationReport>(loader, 60000);
  const [running, setRunning] = useState(false);
  const [runError, setRunError] = useState<string | null>(null);

  async function handleRun() {
    setRunning(true);
    setRunError(null);
    try {
      await runInstitutionalValidation();
      await refresh();
    } catch (err) {
      setRunError(err instanceof Error ? err.message : "机构级验证运行失败。");
    } finally {
      setRunning(false);
    }
  }

  const dsr = data?.deflated_sharpe_ratio;
  const pbo = data?.probability_of_backtest_overfitting;
  const reality = data?.reality_check;
  const promotion = data?.promotion_eligibility;

  return (
    <SectionCard
      title="机构级验证"
      subtitle="包含 DSR/PBO、Reality Check、成本压力、Regime 压力和上线资格；验证失败不会发布 active。"
      actions={
        <button className="primary-button" type="button" onClick={handleRun} disabled={running}>
          运行机构级验证
        </button>
      }
    >
      {loading || running ? <LoadingState label="正在加载机构级验证结果..." /> : null}
      {error ? <ErrorState message={error} onRetry={refresh} /> : null}
      {runError ? <ErrorState message={runError} onRetry={handleRun} /> : null}

      <div className="metric-grid">
        <div className="metric-card">
          <span>Deflated Sharpe Ratio</span>
          <strong>{formatNumber(dsr?.deflated_sharpe_ratio as number | null | undefined)}</strong>
        </div>
        <div className="metric-card">
          <span>PBO</span>
          <strong>{formatNumber(pbo?.pbo as number | null | undefined)}</strong>
        </div>
        <div className="metric-card">
          <span>Reality Check</span>
          <strong>{reality?.passed ? "通过" : "未通过"}</strong>
        </div>
        <div className="metric-card">
          <span>上线资格</span>
          <strong>{promotion?.eligible ? "满足机构级验证" : "不可上线"}</strong>
        </div>
      </div>

      <div className="two-column">
        <DataTable
          data={rowsFromRecord(data?.cost_stress)}
          emptyLabel="暂无成本压力测试结果"
          columns={[
            { key: "scenario", title: "成本场景" },
            { key: "expectancy", title: "成本后期望", format: "number" },
            { key: "sharpe", title: "Sharpe", format: "number" },
            { key: "max_drawdown", title: "最大回撤", format: "number" },
            { key: "hit_rate", title: "命中率", format: "number" },
            { key: "active_eligibility_under_cost_stress", title: "压力下资格", format: "status" }
          ]}
        />
        <DataTable
          data={rowsFromRecord(data?.regime_stress)}
          emptyLabel="暂无市场状态压力测试结果"
          columns={[
            { key: "scenario", title: "市场状态" },
            { key: "sample_count", title: "样本数", format: "number" },
            { key: "direction_accuracy", title: "方向命中", format: "number" },
            { key: "expectancy", title: "期望", format: "number" },
            { key: "max_drawdown", title: "最大回撤", format: "number" },
            { key: "calibration_error", title: "校准误差", format: "number" }
          ]}
        />
      </div>

      <SectionCard title="不可上线原因" subtitle="任一机构级验证项失败，都不会降低 gate，也不会发布 active。">
        {promotion?.failure_reasons?.length ? (
          <ul className="risk-list">
            {promotion.failure_reasons.map((reason) => (
              <li key={reason}>{reason}</li>
            ))}
          </ul>
        ) : (
          <p>{formatNullable(promotion?.message_zh || data?.message_zh)}</p>
        )}
      </SectionCard>
    </SectionCard>
  );
}
