import type { PositionScenarioResult as Result } from "../../api/types";
import { formatNumber, formatPercent } from "../../utils/format";
import { EmptyState } from "../common/EmptyState";
import { MetricCard } from "../common/MetricCard";
import { SectionCard } from "../layout/SectionCard";

export function PositionScenarioResult({ result }: { result?: Result | null }) {
  if (!result) return <EmptyState label="请填写持仓信息后生成情景观察区" />;
  return (
    <SectionCard title="持仓情景结果" subtitle="仅输出观察区和风险提示，不提供确定性交易指令">
      <div className="metric-grid">
        <MetricCard label="名义敞口" value={formatNumber(result.notional_exposure, 2)} />
        <MetricCard label="保证金占用" value={formatNumber(result.margin_required, 2)} />
        <MetricCard label="VaR 95" value={formatNumber(result.var_95, 2)} />
        <MetricCard label="压力 VaR" value={formatNumber(result.stress_var, 2)} />
        <MetricCard label="最大亏损占比" value={formatPercent(result.max_loss_ratio)} />
      </div>
      <div className="mini-list-grid">
        <div>
          <h4>观察区</h4>
          <ul>{(result.observation_zone?.length ? result.observation_zone : [{ label: "暂无观察区" }]).map((item, index) => <li key={index}>{String(item.label || item.name || JSON.stringify(item))}</li>)}</ul>
        </div>
        <div>
          <h4>风险区</h4>
          <ul>{(result.risk_zone?.length ? result.risk_zone : [{ label: "暂无风险区" }]).map((item, index) => <li key={index}>{String(item.label || item.name || JSON.stringify(item))}</li>)}</ul>
        </div>
      </div>
      <p className="muted">周期共振：{result.horizon_resonance || "待验证"}</p>
      <div className="reason-list">
        {(result.uncertainty_notes?.length ? result.uncertainty_notes : ["仅供投研参考，需独立决策。"]).map((item) => (
          <span key={item}>{item}</span>
        ))}
      </div>
      <strong className="disclaimer-line">{result.disclaimer || "仅供投研参考，需独立决策，不构成投资建议。"}</strong>
    </SectionCard>
  );
}
