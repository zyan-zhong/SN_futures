from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"


def _read(path: str) -> str:
    return (FRONTEND / path).read_text(encoding="utf-8")


def test_first_run_wizard_files_exist_and_include_required_copy() -> None:
    wizard = _read("src/components/onboarding/FirstRunWizard.tsx")
    hook = _read("src/hooks/useFirstRun.ts")
    utility = _read("src/utils/onboarding.ts")
    assert "欢迎使用 SNInsightTerminal" in wizard
    assert "稍后配置" in wizard
    assert "不再自动弹出" in wizard
    assert "仅供沪锡期货量化投研参考" in wizard
    assert "不构成投资建议" in wizard
    assert "密钥仅保存在本机用户目录" in wizard
    assert "getSettingsStatus" in hook
    assert "getDataStatus" in hook
    assert "getSystemHealth" in hook
    assert "firstRunCompleted" in utility


def test_first_run_is_integrated_into_app_without_blocking_terminal_shell() -> None:
    app = _read("src/App.tsx")
    assert "FirstRunWizard" in app
    assert "useFirstRun" in app
    assert "firstRun.shouldShow" in app


def test_onboarding_local_storage_only_uses_allowed_first_run_key() -> None:
    onboarding = _read("src/utils/onboarding.ts")
    assert "window.localStorage" in onboarding
    assert "firstRunCompleted" in onboarding
    assert "SN_ALPHA_VANTAGE_KEY" not in onboarding
    assert "SN_NEWSAPI_KEY" not in onboarding

