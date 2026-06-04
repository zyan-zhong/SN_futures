import { useEffect, useState } from "react";
import { getManagedProxyConfigHandoff, refreshManagedProxyConfigHandoff } from "../../api/terminal";
import type { ManagedProxyConfigHandoffPayload } from "../../api/types";
import { formatBooleanFlag } from "../../utils/copySystem";
import { formatNextAction, formatStatusLabel } from "../../utils/statusTaxonomy";

function list(values?: string[]) {
  return (values ?? []).filter((item) => String(item || "").trim());
}

function hasUnsafeCommand(commands: string[]) {
  return commands.some((command) => !command.includes("<paste-token-only-in-your-local-shell>") && command.includes("SN_MANAGED_PROXY_TOKEN"));
}

export function ManagedProxyConfigHandoffCard({ compact = false }: { compact?: boolean }) {
  const [payload, setPayload] = useState<ManagedProxyConfigHandoffPayload | null>(null);
  const [statusMessage, setStatusMessage] = useState("");
  const commands = list(payload?.copy_safe_setup_commands);
  const unsafeCommand = hasUnsafeCommand(commands);

  useEffect(() => {
    let cancelled = false;
    void getManagedProxyConfigHandoff()
      .then((value) => {
        if (!cancelled) setPayload(value);
      })
      .catch(() => {
        if (!cancelled) setPayload({ status: "missing_config", endpoint_configured: false, token_configured: false });
      });
    return () => {
      cancelled = true;
    };
  }, []);

  async function handleRefresh() {
    const next = await refreshManagedProxyConfigHandoff();
    setPayload(next);
    setStatusMessage("Configuration handoff refreshed");
    window.dispatchEvent(new CustomEvent("setup-action-completed"));
  }

  async function copyCommand(command: string) {
    if (unsafeCommand) return;
    await navigator.clipboard?.writeText(command);
    setStatusMessage("Placeholder command copied");
  }

  return (
    <section aria-label="Secure Configuration Handoff" className={compact ? "config-handoff-card compact" : "config-handoff-card"}>
      <header>
        <div>
          <strong>Secure Configuration Handoff</strong>
          <span>Use local shell or ignored local config only. This card never accepts raw tokens.</span>
        </div>
        <button type="button" onClick={() => void handleRefresh()} aria-label="Refresh secure configuration handoff">
          Refresh handoff
        </button>
      </header>

      <div className="metric-grid">
        <div className="metric-card">
          <span>status</span>
          <strong>{formatStatusLabel(payload?.status ?? "missing_config")}</strong>
        </div>
        <div className="metric-card">
          <span>endpoint_configured</span>
          <strong>{formatBooleanFlag(payload?.endpoint_configured ?? false)}</strong>
        </div>
        <div className="metric-card">
          <span>token_configured</span>
          <strong>{formatBooleanFlag(payload?.token_configured ?? false)}</strong>
        </div>
        <div className="metric-card">
          <span>token_masked</span>
          <strong>{payload?.token_masked || "not configured"}</strong>
        </div>
      </div>

      <div className="config-handoff-warning" role="note">
        Do not paste token into ChatGPT, Codex, commits, logs, or screenshots.
      </div>

      <div className="config-handoff-commands" aria-label="Safe local setup commands" tabIndex={0}>
        <strong>PowerShell placeholder commands</strong>
        <ul>
          {commands.map((command, index) => (
            <li key={command}>
              <code>{command}</code>
              <button type="button" onClick={() => void copyCommand(command)} aria-label={`Copy safe placeholder command ${index + 1}`}>
                Copy
              </button>
            </li>
          ))}
        </ul>
      </div>

      <div className="metric-grid">
        <div className="metric-card">
          <span>gitignore coverage</span>
          <strong>{formatStatusLabel(payload?.gitignore_secret_coverage?.status ?? "missing")}</strong>
        </div>
        <div className="metric-card">
          <span>alias consistency</span>
          <strong>{formatStatusLabel(payload?.env_alias_consistency?.status ?? "missing")}</strong>
        </div>
        <div className="metric-card">
          <span>next safe action</span>
          <strong>{formatNextAction(payload?.next_safe_actions_after_config?.[0] ?? "configure_managed_proxy_endpoint_or_token")}</strong>
        </div>
      </div>

      {!compact && (
        <div className="config-handoff-checklist">
          <strong>After local config</strong>
          <ul>
            {list(payload?.next_safe_actions_after_config).map((action) => (
              <li key={action}>{formatNextAction(action)}</li>
            ))}
          </ul>
        </div>
      )}
      {statusMessage && <p role="status">{statusMessage}</p>}
    </section>
  );
}
