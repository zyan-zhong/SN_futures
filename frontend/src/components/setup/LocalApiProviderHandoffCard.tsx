import { useEffect, useState } from "react";
import { getLocalApiProviderHub, getProviderCredentials, refreshProviderCredentials, runProviderSmokeTest } from "../../api/terminal";
import type { LocalApiProviderHubPayload, ProviderCredentialsPayload } from "../../api/types";
import { formatBooleanFlag } from "../../utils/copySystem";
import { formatNextAction, formatStatusLabel } from "../../utils/statusTaxonomy";

function list(values?: string[]) {
  return (values ?? []).filter((item) => String(item || "").trim());
}

function providerNames(payload: ProviderCredentialsPayload | null) {
  return Object.keys(payload?.providers ?? {});
}

function hasUnsafeCommand(commands: string[]) {
  return commands.some((command) => command.includes("SN_TWELVEDATA_API_KEY") && !command.includes("<paste-key-only-in-your-local-shell>"));
}

export function LocalApiProviderHandoffCard({ compact = false }: { compact?: boolean }) {
  const [credentials, setCredentials] = useState<ProviderCredentialsPayload | null>(null);
  const [hub, setHub] = useState<LocalApiProviderHubPayload | null>(null);
  const [statusMessage, setStatusMessage] = useState("");
  const commands = list(credentials?.copy_safe_setup_commands);
  const unsafeCommand = hasUnsafeCommand(commands);

  useEffect(() => {
    let cancelled = false;
    Promise.allSettled([getProviderCredentials(), getLocalApiProviderHub()]).then((results) => {
      if (cancelled) return;
      const credentialResult = results[0];
      const hubResult = results[1];
      if (credentialResult.status === "fulfilled") setCredentials(credentialResult.value);
      if (hubResult.status === "fulfilled") setHub(hubResult.value);
    });
    return () => {
      cancelled = true;
    };
  }, []);

  async function handleRefresh() {
    const next = await refreshProviderCredentials();
    setCredentials(next);
    setStatusMessage("Local API provider credential status refreshed");
    window.dispatchEvent(new CustomEvent("setup-action-completed"));
  }

  async function handleSmoke(provider = "twelvedata") {
    await runProviderSmokeTest({ provider });
    const next = await getLocalApiProviderHub();
    setHub(next);
    setStatusMessage("Provider smoke status refreshed");
    window.dispatchEvent(new CustomEvent("setup-action-completed"));
  }

  async function copyCommand(command: string) {
    if (unsafeCommand) return;
    await navigator.clipboard?.writeText(command);
    setStatusMessage("Placeholder command copied");
  }

  const yfinance = credentials?.providers?.yfinance_research_only;

  return (
    <section aria-label="Local API Provider Handoff" className={compact ? "config-handoff-card compact" : "config-handoff-card"}>
      <header>
        <div>
          <strong>Local API Provider Hub</strong>
          <span>local install / API provider mode: local_api_provider. This card never accepts raw API keys.</span>
        </div>
        <button type="button" onClick={() => void handleRefresh()} aria-label="Refresh local API provider credentials">
          Refresh provider status
        </button>
      </header>

      <div className="metric-grid">
        <div className="metric-card">
          <span>provider_mode</span>
          <strong>{hub?.provider_mode || credentials?.provider_mode || "local_api_provider"}</strong>
        </div>
        <div className="metric-card">
          <span>current step</span>
          <strong>{hub?.current_step || credentials?.current_step || "configure_local_api_provider_credentials"}</strong>
        </div>
        <div className="metric-card">
          <span>credential status</span>
          <strong>{formatStatusLabel(credentials?.provider_credentials_status ?? "missing_config")}</strong>
        </div>
        <div className="metric-card">
          <span>v12 allowed</span>
          <strong>{formatBooleanFlag(credentials?.feature_store_v12_allowed ?? false)}</strong>
        </div>
      </div>

      <div className="config-handoff-warning" role="note">
        Do not paste API keys into ChatGPT, Codex, commits, logs, issues, screenshots, or reports.
      </div>

      <div className="config-handoff-commands" aria-label="Safe local API provider setup commands" tabIndex={0}>
        <strong>PowerShell placeholder commands</strong>
        <ul>
          {commands.map((command, index) => (
            <li key={`${command}-${index}`}>
              <code>{command}</code>
              <button type="button" onClick={() => void copyCommand(command)} aria-label={`Copy local API provider placeholder command ${index + 1}`}>
                Copy
              </button>
            </li>
          ))}
        </ul>
      </div>

      <div className="metric-grid">
        {providerNames(credentials).map((providerId) => {
          const provider = credentials?.providers?.[providerId] ?? {};
          return (
            <div className="metric-card" key={providerId}>
              <span>{providerId}</span>
              <strong>{formatBooleanFlag(provider.key_configured ?? false)}</strong>
              <small>{provider.key_masked || (provider.research_only ? "research_only" : "missing")}</small>
            </div>
          );
        })}
      </div>

      <div className="metric-grid">
        <div className="metric-card">
          <span>yfinance_research_only</span>
          <strong>{formatBooleanFlag(yfinance?.research_only ?? true)}</strong>
          <small>production_eligible={formatBooleanFlag(yfinance?.production_eligible ?? false)}</small>
        </div>
        <div className="metric-card">
          <span>legacy managed proxy</span>
          <strong>{formatStatusLabel(String(credentials?.legacy_managed_proxy_status?.status ?? "not_configured"))}</strong>
        </div>
        <div className="metric-card">
          <span>next action</span>
          <strong>{formatNextAction(hub?.next_allowed_action ?? "configure_local_api_provider_credentials")}</strong>
        </div>
      </div>

      {!compact && (
        <div className="config-handoff-checklist">
          <strong>Safe checks</strong>
          <ul>
            <li>Refresh masked credential status.</li>
            <li>Run provider smoke only after local credentials are configured.</li>
            <li>Sample fixtures can validate contracts but cannot unlock v12.</li>
          </ul>
          <button type="button" onClick={() => void handleSmoke("twelvedata")} aria-label="Run local provider smoke test">
            Run provider smoke
          </button>
        </div>
      )}
      {statusMessage && <p role="status">{statusMessage}</p>}
    </section>
  );
}
