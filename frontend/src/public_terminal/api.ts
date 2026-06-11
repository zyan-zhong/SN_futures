import { getJson, postJson } from "../api/client";
import type {
  PublicEventsPayload,
  PublicMarketPayload,
  PublicPredictionStatusPayload,
  PublicTerminalOpenApiPayload,
  PublicProviderSmokeInput,
  PublicReadinessPayload,
  PublicReportPayload,
  PublicSettingsSavePayload,
  PublicSettingsSaveInput,
  PublicSettingsStatus,
  PublicSmokePayload,
  PublicTaskCancelPayload,
  PublicTaskPayload
} from "./types";

export function getPublicTerminalOpenApi() {
  return getJson<PublicTerminalOpenApiPayload>("/api/public-terminal/openapi.json", { timeoutMs: 8000, dedupe: false });
}

export function getPublicReadiness() {
  return getJson<PublicReadinessPayload>("/api/public-terminal/readiness", { timeoutMs: 8000, dedupe: false });
}

export function getPublicPredictionStatus() {
  return getJson<PublicPredictionStatusPayload>("/api/public-terminal/prediction-status", { timeoutMs: 8000, dedupe: false });
}

export function getPublicSettingsStatus() {
  return getJson<PublicSettingsStatus>("/api/public-terminal/settings/status", { timeoutMs: 8000, dedupe: false });
}

export function savePublicSettings(input: PublicSettingsSaveInput) {
  return postJson<PublicSettingsSavePayload>("/api/public-terminal/settings/save", input, { timeoutMs: 10000 });
}

export function resetPublicSettings() {
  return postJson<PublicSettingsSavePayload>("/api/public-terminal/settings/reset", {}, { timeoutMs: 10000 });
}

export function runPublicProviderSmoke(input: PublicProviderSmokeInput = {}) {
  return postJson<PublicSmokePayload>("/api/public-terminal/provider-smoke", { allow_remote: false, ...input }, { timeoutMs: 15000 });
}

export function runPublicProviderSmokeReal(input: PublicProviderSmokeInput = {}) {
  return postJson<PublicSmokePayload>("/api/public-terminal/provider-smoke-real", { allow_remote: false, ...input }, { timeoutMs: 15000 });
}

export function startPublicDataRefresh() {
  return postJson<PublicTaskPayload>("/api/public-terminal/refresh-data-status", {}, { timeoutMs: 10000 });
}

export function getPublicTask(taskId: string) {
  return getJson<PublicTaskPayload>(`/api/public-terminal/tasks/${encodeURIComponent(taskId)}`, { timeoutMs: 8000, dedupe: false });
}

export function cancelPublicTask(taskId: string) {
  return postJson<PublicTaskCancelPayload>(`/api/public-terminal/tasks/${encodeURIComponent(taskId)}/cancel`, {}, { timeoutMs: 8000 });
}

export function getPublicMarket() {
  return getJson<PublicMarketPayload>("/api/public-terminal/market", { timeoutMs: 8000, dedupe: false });
}

export function getPublicEvents() {
  return getJson<PublicEventsPayload>("/api/public-terminal/events", { timeoutMs: 8000, dedupe: false });
}

export function getPublicReport() {
  return getJson<PublicReportPayload>("/api/public-terminal/report", { timeoutMs: 8000, dedupe: false });
}
