import { getJson, postJson } from "./client";
import type { KeyDiagnosticsPayload, TerminalSettingsStatus } from "./types/settings";

export interface SettingsSecretsInput {
  SN_ALPHA_VANTAGE_KEY?: string;
  SN_NEWSAPI_KEY?: string;
  SN_TUSHARE_TOKEN?: string;
  SN_LOCAL_API_PROVIDER_ENABLED?: string;
  SN_LOCAL_API_PROVIDER_ID?: string;
  SN_LOCAL_API_PROVIDER_BASE_URL?: string;
  SN_LOCAL_API_PROVIDER_TOKEN?: string;
  SN_MANAGED_DATA_PROXY_TOKEN?: string;
  SN_MANAGED_DATA_PROXY_URL?: string;
}

export function getSettingsStatus() {
  return getJson<TerminalSettingsStatus>("/api/terminal/settings/status");
}

export function getKeyDiagnostics() {
  return getJson<KeyDiagnosticsPayload>("/api/terminal/settings/key-diagnostics");
}

export function saveSettingsSecrets(input: SettingsSecretsInput) {
  return postJson<TerminalSettingsStatus>("/api/terminal/settings/secrets", input);
}

export function resetSettingsSecrets() {
  return postJson<TerminalSettingsStatus>("/api/terminal/settings/reset", {});
}
