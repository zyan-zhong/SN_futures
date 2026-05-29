import type { TerminalSnapshot } from "../api/types";
import { ErrorBoundary } from "../components/common/ErrorBoundary";
import { CandidateDiagnosticsPanel } from "../components/model/CandidateDiagnosticsPanel";
import { CandidateTrainingPanel } from "../components/model/CandidateTrainingPanel";
import { HighConfidenceValidationPanel } from "../components/model/HighConfidenceValidationPanel";
import { LearningStatusPanel } from "../components/model/LearningStatusPanel";
import { ModelHealthPanel } from "../components/model/ModelHealthPanel";
import { OOFTracePanel } from "../components/model/OOFTracePanel";
import { PromotionGatePanel } from "../components/model/PromotionGatePanel";
import { SectionCard } from "../components/layout/SectionCard";

export function ModelGovernancePage({ snapshot }: { snapshot?: TerminalSnapshot | null }) {
  return (
    <div className="page-stack">
      <ErrorBoundary moduleName="模型健康">
        <ModelHealthPanel health={snapshot?.model_health} />
      </ErrorBoundary>

      <ErrorBoundary moduleName="晋级与降级守门">
        <PromotionGatePanel health={snapshot?.model_health} />
      </ErrorBoundary>

      <ErrorBoundary moduleName="Candidate 训练与 Walk-forward">
        <CandidateTrainingPanel />
      </ErrorBoundary>

      <ErrorBoundary moduleName="candidate_v2 研究对比">
        <SectionCard
          title="candidate_v1 vs candidate_v2"
          subtitle="v2 仅用于研究验证；不发布 active、不生成客户预测、不降低 promotion gate。"
        >
          <div className="metric-grid">
            <div className="metric-card">
              <span>新增字段贡献</span>
              <strong>usd_cny / us10y / copper_global_proxy / event_shock_score</strong>
              <small>只有真实覆盖率达标时才进入 feature_cols；缺失时不伪造。</small>
            </div>
            <div className="metric-card">
              <span>高置信 v2</span>
              <strong>OOF top10 / top20 / top30</strong>
              <small>高置信 OOF 命中率不是客户预测，不代表未来收益。</small>
            </div>
            <div className="metric-card">
              <span>Promotion dry-run</span>
              <strong>dry_run=true 不写 active_model.json</strong>
              <small>若通过，仅显示等待人工审批发布 active。</small>
            </div>
          </div>
        </SectionCard>
      </ErrorBoundary>

      <ErrorBoundary moduleName="OOF 样本外验证轨迹">
        <OOFTracePanel />
      </ErrorBoundary>

      <ErrorBoundary moduleName="高置信子集验证">
        <HighConfidenceValidationPanel />
      </ErrorBoundary>

      <ErrorBoundary moduleName="Candidate 失败归因">
        <CandidateDiagnosticsPanel />
      </ErrorBoundary>

      <ErrorBoundary moduleName="学习状态">
        <LearningStatusPanel status={snapshot?.learning_status} />
      </ErrorBoundary>
    </div>
  );
}
