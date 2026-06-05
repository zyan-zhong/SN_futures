from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_quality_gate_module():
    module_path = Path("scripts/quality_gate.py")
    spec = importlib.util.spec_from_file_location("quality_gate", module_path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_quality_gate_declares_release_blocking_steps() -> None:
    gate = _load_quality_gate_module()
    step_names = [step.name for step in gate.build_gate_steps(gate.GateOptions(skip_e2e=True))]

    assert "python compileall" in step_names
    assert "pytest full suite" in step_names
    assert "frontend typecheck" in step_names
    assert "frontend build" in step_names
    assert "frontend UI contract check" in step_names
    assert "repo cleanliness check" in step_names
    assert "secret scan" in step_names
    assert "real-result sample/baseline scan" in step_names
    assert "historical OHLCV scaling scan" in step_names
    assert "API endpoint contract tests" in step_names
    assert "data watermark schema tests" in step_names


def test_real_result_scan_blocks_sample_or_baseline_payloads_marked_allowed(tmp_path: Path) -> None:
    gate = _load_quality_gate_module()
    payload = tmp_path / "sn_unified_forecast.json"
    payload.write_text(
        '{"sample_data_used": true, "allowed_for_prediction": true, "is_real_data_only": true}',
        encoding="utf-8",
    )

    findings = gate.find_real_result_policy_violations([payload])

    assert findings
    assert "sample_data_used" in findings[0].reason


def test_historical_scaling_scan_blocks_live_ratio_ohlcv_mutation(tmp_path: Path) -> None:
    gate = _load_quality_gate_module()
    source = tmp_path / "bad_overlay.py"
    source.write_text(
        """
def apply_live_snapshot_overlay(frame, latest, last_close):
    live_scale_ratio = latest / last_close
    frame["open"] = frame["open"] * live_scale_ratio
    frame["close"] = frame["close"] * live_scale_ratio
    return frame
""",
        encoding="utf-8",
    )

    findings = gate.find_historical_scaling_violations([source])

    assert findings
    assert "OHLCV" in findings[0].reason


def test_release_package_scan_blocks_env_and_secret_files(tmp_path: Path) -> None:
    gate = _load_quality_gate_module()
    release = tmp_path / "release"
    release.mkdir()
    (release / ".env").write_text("SN_NEWSAPI_KEY=SECRET", encoding="utf-8")
    (release / "secrets.json").write_text("{}", encoding="utf-8")

    findings = gate.find_release_package_violations(release)

    assert {finding.path.name for finding in findings} == {".env", "secrets.json"}
    assert all("Fix:" in finding.reason for finding in findings)


def test_release_package_scan_blocks_private_seed_in_pyinstaller_onedir(tmp_path: Path) -> None:
    gate = _load_quality_gate_module()
    seed = tmp_path / "dist" / "SNInsightTerminal" / "_internal" / "private" / "private_bundle_seed.json"
    seed.parent.mkdir(parents=True)
    seed.write_text('{"secrets": {"SN_NEWSAPI_KEY": "RAW_SECRET_VALUE"}}', encoding="utf-8")

    findings = gate.find_release_package_violations(tmp_path / "dist")

    assert len(findings) == 1
    assert findings[0].path == seed
    assert "private_bundle_seed.json" in findings[0].format(tmp_path)
    assert "Fix:" in findings[0].reason


def test_release_package_scan_allows_safe_pyinstaller_onedir(tmp_path: Path) -> None:
    gate = _load_quality_gate_module()
    internal = tmp_path / "dist" / "SNInsightTerminal" / "_internal"
    certifi = internal / "certifi"
    certifi.mkdir(parents=True)
    (certifi / "cacert.pem").write_text("public ca bundle", encoding="utf-8")
    (internal / ".env.example").write_text("SN_NEWSAPI_KEY=your_key_here", encoding="utf-8")
    (tmp_path / "dist" / "SNInsightTerminal" / "SNInsightTerminal.exe").write_text("", encoding="utf-8")

    findings = gate.find_release_package_violations(tmp_path / "dist")

    assert findings == []


def test_pyinstaller_spec_and_release_script_do_not_embed_private_or_runtime_datas() -> None:
    gate = _load_quality_gate_module()

    findings = gate.find_packaging_manifest_violations(Path("."))

    assert findings == []


def test_customer_acceptance_checklist_includes_final_quality_gate_items() -> None:
    checklist = Path("docs/CUSTOMER_ACCEPTANCE_CHECKLIST.md").read_text(encoding="utf-8")

    for term in (
        "数据源配置",
        "一键刷新",
        "数据状态",
        "新闻/政策事件",
        "Feature Store gate",
        "预测原因",
        "回测原因",
        "报告免责声明",
        "发行包排除",
    ):
        assert term in checklist
