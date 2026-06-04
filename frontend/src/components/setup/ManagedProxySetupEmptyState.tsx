import { deriveGuidedEmptyState } from "../../utils/guidedSetup";
import { SafeConfigInstructions } from "./SafeConfigInstructions";

export function ManagedProxySetupEmptyState({ nextAllowedAction }: { nextAllowedAction?: string }) {
  const state = deriveGuidedEmptyState(nextAllowedAction);

  return (
    <section aria-label="Managed Proxy setup guidance" className="guided-empty-state managed-proxy-setup-empty-state">
      <header>
        <strong>Managed Proxy 还没有完成配置</strong>
        <span>当前不会请求真实 endpoint，也不会构建 Feature Store v12。</span>
      </header>
      <div className="guided-empty-state__grid">
        <div>
          <strong>第一步该做什么</strong>
          <p>{state.nextAction}</p>
          <p>只在本机私有配置或 shell 中设置 endpoint/token，然后回到这里刷新只读状态。</p>
        </div>
        <div>
          <strong>配置后点哪里验证</strong>
          <ul>
            <li>Operator Runbook / Setup Verification</li>
            <li>Endpoint Smoke Test</li>
            <li>Schema Mapping / Sample Fixture Contract</li>
            <li>PIT Replay / PIT Audit</li>
            <li>Data Quality</li>
          </ul>
        </div>
      </div>
      <SafeConfigInstructions />
    </section>
  );
}
