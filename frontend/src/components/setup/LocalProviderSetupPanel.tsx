import type { TerminalSnapshot } from "../../api/types";
import { buildLocalFirstStatusModel } from "../../utils/localFirstStatus";
import { StatusPill } from "../common/StatusPill";
import { SectionCard } from "../layout/SectionCard";

export function LocalProviderSetupPanel({ snapshot }: { snapshot?: TerminalSnapshot | null }) {
  const model = buildLocalFirstStatusModel(snapshot);
  return (
    <SectionCard title="Provider Setup Matrix" subtitle="Local API Provider Hub status: configure keys locally, smoke providers, then refresh real data.">
      <div className="provider-card-grid">
        {model.providerSetupCards.map((provider) => (
          <article className="provider-card compact-provider-card" key={provider.providerId}>
            <header>
              <strong>{provider.label}</strong>
              <StatusPill label={provider.configured ? "configured" : "not configured"} tone={provider.configured ? "good" : "warn"} />
            </header>
            <p>{provider.configured ? "Ready for provider smoke before downstream use." : "未配置 / not configured"}</p>
            <small>{provider.nextAction}</small>
          </article>
        ))}
      </div>
      <div className="notice-card">
        <strong>Local API Provider</strong>
        <span>Provider smoke is read-only. It must not train, build Feature Store, run backtest, or generate customer prediction.</span>
      </div>
    </SectionCard>
  );
}
