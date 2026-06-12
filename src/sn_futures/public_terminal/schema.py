from __future__ import annotations

from copy import deepcopy
from typing import Any


PUBLIC_TERMINAL_SCHEMA_VERSION = "public-terminal-openapi-v1"

PUBLIC_TERMINAL_SIDE_EFFECTS = {
    "training": False,
    "prediction": False,
    "backtest": False,
    "feature_store": False,
    "real_api_default": False,
}

FORBIDDEN_PUBLIC_TERMINAL_SIDE_EFFECTS = {
    "training": True,
    "prediction": True,
    "backtest": True,
    "feature_store": True,
    "production_cache_write": True,
    "legacy_refresh_all": True,
}

PUBLIC_TERMINAL_ERROR_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["error_code", "message", "blocking_reasons", "details_sanitized"],
    "properties": {
        "error_code": {"type": "string"},
        "message": {"type": "string"},
        "blocking_reasons": {"type": "array", "items": {"type": "string"}},
        "details_sanitized": {"type": "object"},
    },
}

PUBLIC_TERMINAL_REQUEST_SCHEMAS: dict[str, dict[str, Any]] = {
    "PublicEmptyRequest": {
        "type": "object",
        "properties": {},
        "additionalProperties": False,
    },
    "PublicSettingsSaveRequest": {
        "type": "object",
        "properties": {
            "base_url": {"type": "string"},
            "token": {"type": "string"},
            "provider": {"type": "string"},
        },
        "additionalProperties": False,
    },
    "PublicProviderSmokeRequest": {
        "type": "object",
        "properties": {
            "allow_remote": {"type": "boolean", "default": False},
            "provider": {"type": "string"},
        },
        "additionalProperties": False,
    },
    "PublicTaskPathRequest": {
        "type": "object",
        "properties": {
            "task_id": {"type": "string"},
        },
        "required": ["task_id"],
        "additionalProperties": False,
    },
}

PUBLIC_TERMINAL_RESPONSE_SCHEMAS: dict[str, dict[str, Any]] = {
    "PublicTerminalOpenApiPayload": {
        "type": "object",
        "properties": {
            "schema_version": {"type": "string"},
            "title": {"type": "string"},
            "endpoints": {"type": "array", "items": {"type": "object"}},
            "request_schemas": {"type": "object"},
            "response_schemas": {"type": "object"},
            "error_schema": {"type": "object"},
        },
    },
    "PublicReadinessPayload": {
        "type": "object",
        "properties": {
            "status": {"type": "string"},
            "summary": {"type": "string"},
            "next_action": {"type": "string"},
            "provider_smoke_passed": {"type": "boolean"},
            "ready_for_refresh": {"type": "boolean"},
            "blocking_reasons": {"type": "array", "items": {"type": "string"}},
            "data_watermark": {"type": "object"},
            "provider_status": {"type": "object"},
            "prediction_readiness": {"type": "object"},
            "prediction_core_readiness": {"type": "object"},
        },
    },
    "PublicSettingsStatus": {
        "type": "object",
        "properties": {
            "configured": {"type": "boolean"},
            "masked": {"type": "string"},
            "sources": {"type": "array", "items": {"type": "object"}},
            "local_api_provider_token_masked": {"type": "string"},
            "tushare_token_masked": {"type": "string"},
        },
    },
    "PublicSettingsSavePayload": {
        "type": "object",
        "properties": {
            "success": {"type": "boolean"},
            "configured": {"type": "boolean"},
            "masked": {"type": "string"},
            "message": {"type": "string"},
            "message_zh": {"type": "string"},
        },
    },
    "PublicSmokePayload": {
        "type": "object",
        "properties": {
            "status": {"type": "string"},
            "error_code": {"type": "string"},
            "row_count": {"type": "integer"},
            "source_statuses": {"type": "array", "items": {"type": "object"}},
            "manifest": {"type": "object"},
            "blocking_reasons": {"type": "array", "items": {"type": "string"}},
            "training_invoked": {"type": "boolean"},
            "prediction_generated": {"type": "boolean"},
            "backtest_invoked": {"type": "boolean"},
        },
    },
    "PublicTaskPayload": {
        "type": "object",
        "properties": {
            "task_id": {"type": "string"},
            "status": {"type": "string"},
            "progress": {"type": "number"},
            "reason": {"type": "string"},
            "result": {"type": "object"},
            "provider_coverage": {"type": "array", "items": {"type": "object"}},
            "missing_data": {"type": "array", "items": {"type": "string"}},
            "training_invoked": {"type": "boolean"},
            "prediction_generated": {"type": "boolean"},
            "backtest_invoked": {"type": "boolean"},
        },
    },
    "PublicTaskCancelPayload": {
        "type": "object",
        "properties": {
            "task_id": {"type": "string"},
            "status": {"type": "string"},
            "cancel_requested": {"type": "boolean"},
            "message": {"type": "string"},
            "reason": {"type": "string"},
        },
    },
    "PublicMarketPayload": {
        "type": "object",
        "properties": {
            "market": {"type": "object"},
        },
    },
    "PublicEventsPayload": {
        "type": "object",
        "properties": {
            "event_center": {"type": "object"},
        },
    },
    "PublicReportPayload": {
        "type": "object",
        "properties": {
            "report": {"type": "object"},
        },
    },
    "PublicPredictionStatusPayload": {
        "type": "object",
        "properties": {
            "schema_version": {"type": "string"},
            "prediction_status": {
                "type": "object",
                "properties": {
                    "schema_version": {"type": "string"},
                    "status": {"type": "string"},
                    "dry_run_status": {"type": "string"},
                    "dry_run": {"type": "boolean"},
                    "can_predict": {"type": "boolean"},
                    "ready_to_generate_prediction": {"type": "boolean"},
                    "reason": {"type": "string"},
                    "blocking_reasons": {"type": "array", "items": {"type": "string"}},
                    "missing_evidence": {"type": "array", "items": {"type": "string"}},
                    "active_release_safe": {"type": "boolean"},
                    "readiness_status": {"type": "string"},
                    "latest_quote": {"type": "object"},
                    "worker_pool": {"type": "object"},
                    "loop_state": {"type": "object"},
                },
            },
            "training_invoked": {"type": "boolean"},
            "prediction_generated": {"type": "boolean"},
            "backtest_invoked": {"type": "boolean"},
            "customer_prediction_generated": {"type": "boolean"},
        },
    },
}

PUBLIC_TERMINAL_ENDPOINT_DEFINITIONS: list[dict[str, Any]] = [
    {
        "method": "GET",
        "path": "/api/public-terminal/openapi.json",
        "summary": "Return the Public Terminal API schema, endpoint manifest, and sanitized error contract.",
        "request_schema_name": "PublicEmptyRequest",
        "response_schema_name": "PublicTerminalOpenApiPayload",
        "side_effect_classification": "read_only",
        "client_function": "getPublicTerminalOpenApi",
        "used_by": ["PublicDiagnosticsPage"],
    },
    {
        "method": "GET",
        "path": "/api/public-terminal/readiness",
        "summary": "Return Public Terminal readiness, next action, provider smoke status, and data watermark metadata.",
        "request_schema_name": "PublicEmptyRequest",
        "response_schema_name": "PublicReadinessPayload",
        "side_effect_classification": "read_only",
        "client_function": "getPublicReadiness",
        "used_by": ["PublicTerminalPage", "PublicDataStatusPage", "PublicDiagnosticsPage"],
    },
    {
        "method": "GET",
        "path": "/api/public-terminal/prediction-status",
        "summary": "Return dry-run realtime prediction loop status without prediction values or model execution.",
        "request_schema_name": "PublicEmptyRequest",
        "response_schema_name": "PublicPredictionStatusPayload",
        "side_effect_classification": "read_only",
        "client_function": "getPublicPredictionStatus",
        "used_by": ["PredictionStatusPanel", "PublicTerminalPage"],
    },
    {
        "method": "GET",
        "path": "/api/public-terminal/settings/status",
        "summary": "Return masked Public Terminal provider settings status.",
        "request_schema_name": "PublicEmptyRequest",
        "response_schema_name": "PublicSettingsStatus",
        "side_effect_classification": "read_only",
        "client_function": "getPublicSettingsStatus",
        "used_by": ["PublicSetupPage"],
    },
    {
        "method": "POST",
        "path": "/api/public-terminal/settings/save",
        "summary": "Save Public Terminal provider settings and return masked status only.",
        "request_schema_name": "PublicSettingsSaveRequest",
        "response_schema_name": "PublicSettingsSavePayload",
        "side_effect_classification": "writes_settings",
        "client_function": "savePublicSettings",
        "used_by": ["PublicSetupPage"],
    },
    {
        "method": "POST",
        "path": "/api/public-terminal/settings/reset",
        "summary": "Reset Public Terminal provider settings without deleting unrelated user data.",
        "request_schema_name": "PublicEmptyRequest",
        "response_schema_name": "PublicSettingsSavePayload",
        "side_effect_classification": "writes_settings",
        "client_function": "resetPublicSettings",
        "used_by": ["PublicSetupPage"],
    },
    {
        "method": "POST",
        "path": "/api/public-terminal/provider-smoke",
        "summary": "Run no-remote provider-only smoke and write a Public Terminal smoke report.",
        "request_schema_name": "PublicProviderSmokeRequest",
        "response_schema_name": "PublicSmokePayload",
        "side_effect_classification": "diagnostic_only",
        "client_function": "runPublicProviderSmoke",
        "used_by": ["PublicSetupPage"],
        "provider_only": True,
    },
    {
        "method": "POST",
        "path": "/api/public-terminal/provider-smoke-real",
        "summary": "Run explicit advanced provider-only real smoke with timeout and sanitized errors.",
        "request_schema_name": "PublicProviderSmokeRequest",
        "response_schema_name": "PublicSmokePayload",
        "side_effect_classification": "diagnostic_only",
        "client_function": "runPublicProviderSmokeReal",
        "used_by": ["PublicSetupPage"],
        "provider_only": True,
    },
    {
        "method": "POST",
        "path": "/api/public-terminal/refresh-data-status",
        "summary": "Start the Public Terminal data-status refresh task without legacy refresh/all.",
        "request_schema_name": "PublicEmptyRequest",
        "response_schema_name": "PublicTaskPayload",
        "side_effect_classification": "starts_task",
        "client_function": "startPublicDataRefresh",
        "used_by": ["PublicDataStatusPage"],
    },
    {
        "method": "GET",
        "path": "/api/public-terminal/tasks/{task_id}",
        "summary": "Read a Public Terminal task status for frontend polling.",
        "request_schema_name": "PublicTaskPathRequest",
        "response_schema_name": "PublicTaskPayload",
        "side_effect_classification": "read_only",
        "client_function": "getPublicTask",
        "used_by": ["PublicDataStatusPage"],
    },
    {
        "method": "POST",
        "path": "/api/public-terminal/tasks/{task_id}/cancel",
        "summary": "Persist cancel_requested for a Public Terminal task.",
        "request_schema_name": "PublicTaskPathRequest",
        "response_schema_name": "PublicTaskCancelPayload",
        "side_effect_classification": "starts_task",
        "client_function": "cancelPublicTask",
        "used_by": ["PublicDataStatusPage"],
    },
    {
        "method": "GET",
        "path": "/api/public-terminal/market",
        "summary": "Return customer market data state and chart data only when real or cached bars exist.",
        "request_schema_name": "PublicEmptyRequest",
        "response_schema_name": "PublicMarketPayload",
        "side_effect_classification": "read_only",
        "client_function": "getPublicMarket",
        "used_by": ["PublicMarketPage"],
    },
    {
        "method": "GET",
        "path": "/api/public-terminal/events",
        "summary": "Return Public Terminal event center rows with source time provenance, SHFE SN relevance, and model-use blockers.",
        "request_schema_name": "PublicEmptyRequest",
        "response_schema_name": "PublicEventsPayload",
        "side_effect_classification": "read_only",
        "client_function": "getPublicEvents",
        "used_by": ["PublicEventCenterPage", "PublicReportsPage"],
    },
    {
        "method": "GET",
        "path": "/api/public-terminal/report",
        "summary": "Return research-only Public Terminal report coverage without investment advice.",
        "request_schema_name": "PublicEmptyRequest",
        "response_schema_name": "PublicReportPayload",
        "side_effect_classification": "read_only",
        "client_function": "getPublicReport",
        "used_by": ["PublicReportsPage"],
    },
]


def _schema_by_name(schema_map: dict[str, dict[str, Any]], schema_name: str) -> dict[str, Any]:
    return deepcopy(schema_map[schema_name])


def public_terminal_endpoint_for_docs(endpoint: dict[str, Any]) -> dict[str, Any]:
    return {
        "method": endpoint["method"],
        "path": endpoint["path"],
        "summary": endpoint["summary"],
        "description": endpoint["summary"],
        "request_schema_name": endpoint["request_schema_name"],
        "response_schema_name": endpoint["response_schema_name"],
        "classification": "public",
        "side_effect_classification": endpoint["side_effect_classification"],
        "forbidden_side_effects": dict(FORBIDDEN_PUBLIC_TERMINAL_SIDE_EFFECTS),
        "side_effects": dict(PUBLIC_TERMINAL_SIDE_EFFECTS),
        "provider_only": bool(endpoint.get("provider_only", False)),
        "client_function": endpoint["client_function"],
        "used_by": list(endpoint["used_by"]),
    }


def public_terminal_endpoint_for_openapi(endpoint: dict[str, Any]) -> dict[str, Any]:
    request_schema_name = endpoint["request_schema_name"]
    response_schema_name = endpoint["response_schema_name"]
    return {
        **public_terminal_endpoint_for_docs(endpoint),
        "request_schema": _schema_by_name(PUBLIC_TERMINAL_REQUEST_SCHEMAS, request_schema_name),
        "response_schema": _schema_by_name(PUBLIC_TERMINAL_RESPONSE_SCHEMAS, response_schema_name),
        "error_schema_name": "PublicApiErrorPayload",
        "error_schema": deepcopy(PUBLIC_TERMINAL_ERROR_SCHEMA),
    }


def build_public_terminal_openapi() -> dict[str, Any]:
    return {
        "schema_version": PUBLIC_TERMINAL_SCHEMA_VERSION,
        "title": "SN Futures Public Terminal API",
        "classification": "public",
        "endpoints": [
            public_terminal_endpoint_for_openapi(endpoint)
            for endpoint in PUBLIC_TERMINAL_ENDPOINT_DEFINITIONS
        ],
        "request_schemas": deepcopy(PUBLIC_TERMINAL_REQUEST_SCHEMAS),
        "response_schemas": deepcopy(PUBLIC_TERMINAL_RESPONSE_SCHEMAS),
        "error_schema_name": "PublicApiErrorPayload",
        "error_schema": deepcopy(PUBLIC_TERMINAL_ERROR_SCHEMA),
        "side_effects": dict(PUBLIC_TERMINAL_SIDE_EFFECTS),
    }


PUBLIC_TERMINAL_API_ENDPOINTS = [
    public_terminal_endpoint_for_docs(endpoint)
    for endpoint in PUBLIC_TERMINAL_ENDPOINT_DEFINITIONS
]
