"""Service-layer adapters used by the existing V2/V3 API routes.

These modules intentionally sit between the legacy route aggregator and the
newer data/model/governance packages.  They keep endpoint compatibility while
making user-facing payloads Chinese, JSON-safe, and governance-aware.
"""

from .backtest_diagnostics_service import build_backtest_diagnostics
from .learning_status_service import build_api_learning_status
from .model_health_service import build_api_model_health
from .payload_utils import sanitize_for_json
from .position_scenario_service import build_position_scenario
from .prediction_service import integrate_live_prediction_payload
from .report_service import build_report_content

__all__ = [
    "build_api_learning_status",
    "build_api_model_health",
    "build_backtest_diagnostics",
    "build_position_scenario",
    "build_report_content",
    "integrate_live_prediction_payload",
    "sanitize_for_json",
]
