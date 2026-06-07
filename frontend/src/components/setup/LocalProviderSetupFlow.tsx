import { useEffect, useState } from "react";
import {
  getDataStatusPayload,
  getKeyDiagnostics,
  getLocalApiProviderHub,
  getProviderCredentials,
  getSettingsStatus,
  refreshProviderCredentials,
  runProviderSmokeTest,
  saveSettingsSecrets
} from "../../api/terminal";
import type { KeyDiagnosticsPayload, LocalApiProviderHubPayload, ProviderCredentialsPayload, ProviderSmokePayload, TerminalSettingsStatus } from "../../api/types";
import { StatusPill } from "../common/StatusPill";
import { SectionCard } from "../layout/SectionCard";

function statusText(value: unknown, fallback = "not_run") {
  const text = String(value ?? "").trim();
  return text || fallback;
}

function maskedProviderToken(status: TerminalSettingsStatus | null) {
  return status?.local_api_provider_token_masked || "not configured";
}

export function LocalProviderSetupFlow({ compact = false }: { compact?: boolean }) {
  const [providerId, setProviderId] = useState("local_api_provider");
  const [baseUrl, setBaseUrl] = useState("");
  const [token, setToken] = useState("");
  const [settings, setSettings] = useState<TerminalSettingsStatus | null>(null);
  const [credentials, setCredentials] = useState<ProviderCredentialsPayload | null>(null);
  const [hub, setHub] = useState<LocalApiProviderHubPayload | null>(null);
  const [smoke, setSmoke] = useState<ProviderSmokePayload | null>(null);
  const [keyDiagnostics, setKeyDiagnostics] = useState<KeyDiagnosticsPayload | null>(null);
  const [dataStatusMessage, setDataStatusMessage] = useState("data-status not refreshed");
  const [busyAction, setBusyAction] = useState("");
  const [message, setMessage] = useState("");

  async function reloadStatus() {
    const [nextSettings, nextCredentials, nextHub] = await Promise.all([getSettingsStatus(), getProviderCredentials(), getLocalApiProviderHub()]);
    setSettings(nextSettings);
    setCredentials(nextCredentials);
    setHub(nextHub);
  }

  useEffect(() => {
    let cancelled = false;
    reloadStatus()
      .catch((error) => {
        if (!cancelled) setMessage(error instanceof Error ? error.message : "Local API Provider status unavailable");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  async function handleSave() {
    setBusyAction("save");
    setMessage("");
    try {
      const result = await saveSettingsSecrets({
        SN_LOCAL_API_PROVIDER_ENABLED: token.trim() || baseUrl.trim() ? "true" : "",
        SN_LOCAL_API_PROVIDER_ID: providerId.trim() || "local_api_provider",
        SN_LOCAL_API_PROVIDER_BASE_URL: baseUrl.trim(),
        SN_LOCAL_API_PROVIDER_TOKEN: token.trim()
      });
      setSettings(result);
      setToken("");
      await reloadStatus();
      setMessage(`Saved local provider settings. Masked token: ${maskedProviderToken(result)}`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Save local provider settings failed");
    } finally {
      setBusyAction("");
    }
  }

  async function handleDiagnostics() {
    setBusyAction("diagnostics");
    setMessage("");
    try {
      const [diagnostics, nextCredentials, nextHub] = await Promise.all([getKeyDiagnostics(), refreshProviderCredentials(), getLocalApiProviderHub()]);
      setKeyDiagnostics(diagnostics);
      setCredentials(nextCredentials);
      setHub(nextHub);
      setMessage("Provider key diagnostics refreshed");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Provider key diagnostics failed");
    } finally {
      setBusyAction("");
    }
  }

  async function handleSmoke() {
    setBusyAction("smoke");
    setMessage("");
    try {
      const result = await runProviderSmokeTest({ provider_id: providerId || "local_api_provider" });
      setSmoke(result);
      const nextHub = await getLocalApiProviderHub();
      setHub(nextHub);
      setMessage(`Run provider smoke finished: ${statusText(result.status)}`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Run provider smoke failed");
    } finally {
      setBusyAction("");
    }
  }

  async function handleRefreshDataStatus() {
    setBusyAction("data-status");
    setMessage("");
    try {
      const payload = await getDataStatusPayload();
      const sources = Array.isArray(payload?.sources) ? payload.sources.length : 0;
      setDataStatusMessage(`data-status refreshed, sources=${sources}`);
      await reloadStatus();
    } catch (error) {
      setDataStatusMessage(error instanceof Error ? error.message : "data-status refresh failed");
    } finally {
      setBusyAction("");
    }
  }

  const localProvider = credentials?.providers?.local_api_provider || credentials?.providers?.custom_http_provider;
  const smokeStatus = smoke?.status || hub?.provider_smoke_status || "not_run";
  const smokeSourceStatuses = smoke?.source_statuses || hub?.provider_smoke?.source_statuses || [];
  const firstSmokeSource = smokeSourceStatuses[0];
  const smokeReady = hub?.safe_refresh_available || smokeStatus === "pass";
  const blockedReasons = smoke?.blocking_reasons || hub?.blocking_reasons || credentials?.blocking_reasons || [];

  return (
    <SectionCard
      title="Local API Provider Setup Flow"
      subtitle="Set local keys, save to user secrets, verify masked diagnostics, run provider smoke, then refresh status safely."
    >
      <div className="settings-grid secret-form">
        <label>
          Local provider id
          <input
            autoComplete="off"
            type="text"
            value={providerId}
            onChange={(event) => setProviderId(event.target.value)}
            aria-label="SN_LOCAL_API_PROVIDER_ID"
          />
        </label>
        <label>
          SN_LOCAL_API_PROVIDER_BASE_URL
          <input
            autoComplete="off"
            type="url"
            value={baseUrl}
            onChange={(event) => setBaseUrl(event.target.value)}
            placeholder={settings?.local_api_provider_base_url || "https://local-provider.example"}
            aria-label="SN_LOCAL_API_PROVIDER_BASE_URL"
          />
        </label>
        <label>
          SN_LOCAL_API_PROVIDER_TOKEN
          <input
            autoComplete="off"
            type="password"
            value={token}
            onChange={(event) => setToken(event.target.value)}
            placeholder="leave blank to keep existing token"
            aria-label="SN_LOCAL_API_PROVIDER_TOKEN"
          />
        </label>
      </div>
      <p className="warning-text">Do not paste raw Authorization headers, raw endpoint secrets, bearer strings, or token query parameters.</p>
      <div className="button-row">
        <button className="primary-button" type="button" disabled={busyAction === "save" || (!baseUrl.trim() && !token.trim())} onClick={() => void handleSave()}>
          {busyAction === "save" ? "Saving local provider settings..." : "Save local provider settings"}
        </button>
        <button className="secondary-button" type="button" disabled={busyAction === "diagnostics"} onClick={() => void handleDiagnostics()}>
          {busyAction === "diagnostics" ? "Refreshing diagnostics..." : "Provider key diagnostics"}
        </button>
        <button className="secondary-button" type="button" disabled={busyAction === "smoke"} onClick={() => void handleSmoke()}>
          {busyAction === "smoke" ? "Running provider smoke..." : "Run provider smoke"}
        </button>
        <button className="ghost-button" type="button" disabled={busyAction === "data-status"} onClick={() => void handleRefreshDataStatus()}>
          {busyAction === "data-status" ? "Refreshing data-status..." : "Refresh data-status"}
        </button>
        <button className="ghost-button" type="button" disabled={!smokeReady || busyAction === "data-status"} onClick={() => void handleRefreshDataStatus()}>
          Safe refresh
        </button>
      </div>
      <div className="metric-grid compact">
        <div className="metric-card">
          <span className="metric-label">settings source</span>
          <strong>{settings?.local_api_provider_source || "none"}</strong>
          <small>{maskedProviderToken(settings)}</small>
        </div>
        <div className="metric-card">
          <span className="metric-label">credential handoff</span>
          <strong>{statusText(credentials?.provider_credentials_status, "missing_config")}</strong>
          <small>{localProvider?.key_masked || "local_api_provider not configured"}</small>
        </div>
        <div className="metric-card">
          <span className="metric-label">provider smoke</span>
          <strong>{statusText(smokeStatus)}</strong>
          <small>{statusText(smoke?.manifest?.provider_id || hub?.provider_smoke?.manifest?.provider_id, providerId)}</small>
        </div>
        <div className="metric-card">
          <span className="metric-label">next safe action</span>
          <strong>{statusText(hub?.next_allowed_action, "configure_local_api_provider_credentials")}</strong>
          <small>{smokeReady ? "safe refresh entry is available" : "run provider smoke first"}</small>
        </div>
      </div>
      {!compact ? (
        <div className="notice-card">
          <strong>Smoke manifest</strong>
          <span>
            source_statuses={smokeSourceStatuses.length};
            row_count={smoke?.manifest?.row_count ?? hub?.provider_smoke?.manifest?.row_count ?? 0};
            error_code={smoke?.error_code || smoke?.manifest?.error_code || firstSmokeSource?.error_code || "none"};
            source path={firstSmokeSource?.path || "not available"};
            data-status={dataStatusMessage}
          </span>
        </div>
      ) : null}
      {keyDiagnostics?.local_api_provider ? (
        <p className="muted">
          Local provider key diagnostics: {statusText(keyDiagnostics.local_api_provider.source)} / {keyDiagnostics.local_api_provider.masked || "not configured"}
        </p>
      ) : null}
      {blockedReasons.length ? <p className="warning-text">blocking: {blockedReasons.join(", ")}</p> : null}
      {message ? <StatusPill label={message} tone={message.includes("failed") ? "bad" : "good"} /> : null}
    </SectionCard>
  );
}
