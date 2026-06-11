export type PublicTerminalHttpMethod = "GET" | "POST";
export type PublicTerminalSideEffect = "read_only" | "writes_settings" | "starts_task" | "diagnostic_only";

export const publicTerminalNoSideEffects = {
  training: false,
  prediction: false,
  backtest: false,
  feature_store: false,
  real_api_default: false
} as const;

export const publicTerminalForbiddenSideEffects = [
  "training",
  "prediction",
  "backtest",
  "feature_store",
  "production_cache_write",
  "legacy_refresh_all"
] as const;

export const publicTerminalEndpointManifest = [
  {
    method: "GET",
    path: "/api/public-terminal/openapi.json",
    summary: "Read the Public Terminal API schema and sanitized error contract.",
    requestSchemaName: "PublicEmptyRequest",
    responseSchemaName: "PublicTerminalOpenApiPayload",
    errorSchemaName: "PublicApiErrorPayload",
    clientFunction: "getPublicTerminalOpenApi",
    classification: "public",
    sideEffectClassification: "read_only",
    sideEffects: publicTerminalNoSideEffects,
    forbiddenSideEffects: publicTerminalForbiddenSideEffects,
    usedBy: ["PublicDiagnosticsPage"]
  },
  {
    method: "GET",
    path: "/api/public-terminal/readiness",
    summary: "Read customer readiness, next action, provider smoke state, and data watermark.",
    requestSchemaName: "PublicEmptyRequest",
    responseSchemaName: "PublicReadinessPayload",
    errorSchemaName: "PublicApiErrorPayload",
    clientFunction: "getPublicReadiness",
    classification: "public",
    sideEffectClassification: "read_only",
    sideEffects: publicTerminalNoSideEffects,
    forbiddenSideEffects: publicTerminalForbiddenSideEffects,
    usedBy: ["PublicTerminalPage", "PublicDataStatusPage", "PublicDiagnosticsPage"]
  },
  {
    method: "GET",
    path: "/api/public-terminal/prediction-status",
    summary: "Read realtime prediction readiness status without prediction values.",
    requestSchemaName: "PublicEmptyRequest",
    responseSchemaName: "PublicPredictionStatusPayload",
    errorSchemaName: "PublicApiErrorPayload",
    clientFunction: "getPublicPredictionStatus",
    classification: "public",
    sideEffectClassification: "read_only",
    sideEffects: publicTerminalNoSideEffects,
    forbiddenSideEffects: publicTerminalForbiddenSideEffects,
    usedBy: ["PredictionStatusPanel", "PublicTerminalPage"]
  },
  {
    method: "GET",
    path: "/api/public-terminal/settings/status",
    summary: "Read masked provider settings status.",
    requestSchemaName: "PublicEmptyRequest",
    responseSchemaName: "PublicSettingsStatus",
    errorSchemaName: "PublicApiErrorPayload",
    clientFunction: "getPublicSettingsStatus",
    classification: "public",
    sideEffectClassification: "read_only",
    sideEffects: publicTerminalNoSideEffects,
    forbiddenSideEffects: publicTerminalForbiddenSideEffects,
    usedBy: ["PublicSetupPage"]
  },
  {
    method: "POST",
    path: "/api/public-terminal/settings/save",
    summary: "Save provider settings and return masked status only.",
    requestSchemaName: "PublicSettingsSaveRequest",
    responseSchemaName: "PublicSettingsSavePayload",
    errorSchemaName: "PublicApiErrorPayload",
    clientFunction: "savePublicSettings",
    classification: "public",
    sideEffectClassification: "writes_settings",
    sideEffects: publicTerminalNoSideEffects,
    forbiddenSideEffects: publicTerminalForbiddenSideEffects,
    usedBy: ["PublicSetupPage"]
  },
  {
    method: "POST",
    path: "/api/public-terminal/settings/reset",
    summary: "Reset provider settings without deleting unrelated user data.",
    requestSchemaName: "PublicEmptyRequest",
    responseSchemaName: "PublicSettingsSavePayload",
    errorSchemaName: "PublicApiErrorPayload",
    clientFunction: "resetPublicSettings",
    classification: "public",
    sideEffectClassification: "writes_settings",
    sideEffects: publicTerminalNoSideEffects,
    forbiddenSideEffects: publicTerminalForbiddenSideEffects,
    usedBy: ["PublicSetupPage"]
  },
  {
    method: "POST",
    path: "/api/public-terminal/provider-smoke",
    summary: "Run no-remote provider-only data source check.",
    requestSchemaName: "PublicProviderSmokeRequest",
    responseSchemaName: "PublicSmokePayload",
    errorSchemaName: "PublicApiErrorPayload",
    clientFunction: "runPublicProviderSmoke",
    classification: "public",
    sideEffectClassification: "diagnostic_only",
    sideEffects: publicTerminalNoSideEffects,
    forbiddenSideEffects: publicTerminalForbiddenSideEffects,
    usedBy: ["PublicSetupPage"]
  },
  {
    method: "POST",
    path: "/api/public-terminal/provider-smoke-real",
    summary: "Run explicit advanced provider-only real source check.",
    requestSchemaName: "PublicProviderSmokeRequest",
    responseSchemaName: "PublicSmokePayload",
    errorSchemaName: "PublicApiErrorPayload",
    clientFunction: "runPublicProviderSmokeReal",
    classification: "public",
    sideEffectClassification: "diagnostic_only",
    sideEffects: publicTerminalNoSideEffects,
    forbiddenSideEffects: publicTerminalForbiddenSideEffects,
    usedBy: ["PublicSetupPage"]
  },
  {
    method: "POST",
    path: "/api/public-terminal/refresh-data-status",
    summary: "Start customer data-status refresh task.",
    requestSchemaName: "PublicEmptyRequest",
    responseSchemaName: "PublicTaskPayload",
    errorSchemaName: "PublicApiErrorPayload",
    clientFunction: "startPublicDataRefresh",
    classification: "public",
    sideEffectClassification: "starts_task",
    sideEffects: publicTerminalNoSideEffects,
    forbiddenSideEffects: publicTerminalForbiddenSideEffects,
    usedBy: ["PublicDataStatusPage"]
  },
  {
    method: "GET",
    path: "/api/public-terminal/tasks/{task_id}",
    summary: "Read customer task status for polling.",
    requestSchemaName: "PublicTaskPathRequest",
    responseSchemaName: "PublicTaskPayload",
    errorSchemaName: "PublicApiErrorPayload",
    clientFunction: "getPublicTask",
    classification: "public",
    sideEffectClassification: "read_only",
    sideEffects: publicTerminalNoSideEffects,
    forbiddenSideEffects: publicTerminalForbiddenSideEffects,
    usedBy: ["PublicDataStatusPage"]
  },
  {
    method: "POST",
    path: "/api/public-terminal/tasks/{task_id}/cancel",
    summary: "Request cancellation for a customer task.",
    requestSchemaName: "PublicTaskPathRequest",
    responseSchemaName: "PublicTaskCancelPayload",
    errorSchemaName: "PublicApiErrorPayload",
    clientFunction: "cancelPublicTask",
    classification: "public",
    sideEffectClassification: "starts_task",
    sideEffects: publicTerminalNoSideEffects,
    forbiddenSideEffects: publicTerminalForbiddenSideEffects,
    usedBy: ["PublicDataStatusPage"]
  },
  {
    method: "GET",
    path: "/api/public-terminal/market",
    summary: "Read market state and chart data only when real or cached bars exist.",
    requestSchemaName: "PublicEmptyRequest",
    responseSchemaName: "PublicMarketPayload",
    errorSchemaName: "PublicApiErrorPayload",
    clientFunction: "getPublicMarket",
    classification: "public",
    sideEffectClassification: "read_only",
    sideEffects: publicTerminalNoSideEffects,
    forbiddenSideEffects: publicTerminalForbiddenSideEffects,
    usedBy: ["PublicMarketPage"]
  },
  {
    method: "GET",
    path: "/api/public-terminal/events",
    summary: "Read policy, news, exchange, and supply-chain events with source time and SHFE SN relevance.",
    requestSchemaName: "PublicEmptyRequest",
    responseSchemaName: "PublicEventsPayload",
    errorSchemaName: "PublicApiErrorPayload",
    clientFunction: "getPublicEvents",
    classification: "public",
    sideEffectClassification: "read_only",
    sideEffects: publicTerminalNoSideEffects,
    forbiddenSideEffects: publicTerminalForbiddenSideEffects,
    usedBy: ["PublicEventCenterPage", "PublicReportsPage"]
  },
  {
    method: "GET",
    path: "/api/public-terminal/report",
    summary: "Read research-only report coverage without investment advice.",
    requestSchemaName: "PublicEmptyRequest",
    responseSchemaName: "PublicReportPayload",
    errorSchemaName: "PublicApiErrorPayload",
    clientFunction: "getPublicReport",
    classification: "public",
    sideEffectClassification: "read_only",
    sideEffects: publicTerminalNoSideEffects,
    forbiddenSideEffects: publicTerminalForbiddenSideEffects,
    usedBy: ["PublicReportsPage"]
  }
] as const;

export type PublicTerminalEndpoint = (typeof publicTerminalEndpointManifest)[number];
export type PublicTerminalEndpointPath = PublicTerminalEndpoint["path"];
