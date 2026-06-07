import type { TerminalSnapshot } from "../../api/types";
import { buildLocalFirstStatusModel } from "../../utils/localFirstStatus";
import { StatusPill } from "../common/StatusPill";
import { SectionCard } from "../layout/SectionCard";

export function LocalFirstStatusPanel({ snapshot, title = "System Readiness" }: { snapshot?: TerminalSnapshot | null; title?: string }) {
  const model = buildLocalFirstStatusModel(snapshot);
  return (
    <SectionCard title={title} subtitle="Local-first setup summary before prediction, training, backtest, or Feature Store workflows.">
      <div className="metric-grid">
        {model.providerSetupCards.map((provider) => (
          <div className="metric-card" key={provider.providerId}>
            <span>{provider.label}</span>
            <strong>{provider.configured ? "configured" : "数据源未配置"}</strong>
            <StatusPill label={provider.status} tone={provider.configured ? "good" : "warn"} />
            <small>{provider.nextAction}</small>
          </div>
        ))}
      </div>
      <div className="notice-card">
        <strong>预测已阻断</strong>
        <span>暂无真实预测。配置本地 provider、运行 smoke、刷新真实数据后再进入研究预测。研究参考，不构成投资建议。</span>
      </div>
      <ul className="reason-list">
        {model.nextActions.map((action) => (
          <li key={action}>{action}</li>
        ))}
      </ul>
    </SectionCard>
  );
}
