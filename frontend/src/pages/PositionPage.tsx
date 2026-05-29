import { useState } from "react";
import { postPositionScenario } from "../api/terminal";
import type { PositionScenarioInput, PositionScenarioResult as Result } from "../api/types";
import { ErrorBoundary } from "../components/common/ErrorBoundary";
import { ErrorState } from "../components/common/ErrorState";
import { SectionCard } from "../components/layout/SectionCard";
import { PositionScenarioForm } from "../components/position/PositionScenarioForm";
import { PositionScenarioResult } from "../components/position/PositionScenarioResult";

export function PositionPage() {
  const [result, setResult] = useState<Result | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function submit(input: PositionScenarioInput) {
    setLoading(true);
    setError(null);
    try {
      setResult(await postPositionScenario(input));
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "持仓情景计算失败");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="page-stack">
      <ErrorBoundary moduleName="持仓情景表单">
        <SectionCard title="持仓情景" subtitle="只输出观察区、风险区和不确定性提示">
          <PositionScenarioForm loading={loading} onSubmit={submit} />
        </SectionCard>
      </ErrorBoundary>
      {error ? <ErrorState message={error} /> : null}
      <ErrorBoundary moduleName="持仓情景结果">
        <PositionScenarioResult result={result} />
      </ErrorBoundary>
    </div>
  );
}
