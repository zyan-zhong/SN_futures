from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "frontend" / "src"


REQUIRED_STATUSES = [
    "blocked",
    "missing",
    "not_run",
    "skipped",
    "research_only",
    "planning_only",
    "dry_run_only",
    "ready",
    "pass",
    "fail",
    "warning",
    "guarded",
    "locked_down",
    "incomplete",
    "ready_with_missing_config",
]


def _read(relative: str) -> str:
    return (SRC / relative).read_text(encoding="utf-8")


def test_status_taxonomy_exports_required_formatters_and_statuses() -> None:
    source = _read("utils/statusTaxonomy.ts")

    for name in [
        "STATUS_TAXONOMY",
        "formatStatusLabel",
        "formatGateStatus",
        "formatCandidateStatus",
        "formatNextAction",
        "formatEvidenceState",
        "getStatusTone",
        "getStatusDescription",
        "getDisabledReason",
        "assertNoRawStatusLeak",
    ]:
        assert f"export function {name}" in source or f"export const {name}" in source

    for status in REQUIRED_STATUSES:
        assert f'"{status}"' in source


def test_status_entries_are_user_facing_not_raw_keys() -> None:
    source = _read("utils/statusTaxonomy.ts")

    for status in ["not_run", "ready_with_missing_config", "research_only", "dry_run_only"]:
        match = re.search(rf'"{status}"\s*:\s*\{{(?P<body>.*?)\n\s*\}}', source, re.S)
        assert match, f"missing taxonomy entry for {status}"
        body = match.group("body")
        assert f'label: "{status}"' not in body
        assert f"label: '{status}'" not in body
        assert "description:" in body
        assert "tone:" in body
        assert "allowedNextActionStyle:" in body
        assert "canUnlockDownstreamGates:" in body


def test_status_taxonomy_contains_readable_chinese_copy() -> None:
    source = _read("utils/statusTaxonomy.ts")
    copy = _read("utils/copySystem.ts")

    for phrase in [
        "已阻断",
        "尚未运行",
        "仅研究观察",
        "仅规划",
        "仅 dry-run",
        "可继续审核",
        "检查通过",
        "检查失败",
        "受保护",
        "已锁定",
        "配置 Managed Proxy endpoint 或 token",
        "下一步",
    ]:
        assert phrase in source

    for phrase in [
        "当前状态",
        "下一步允许动作",
        "预测生成权限",
        "Active 发布权限",
        "是",
        "否",
    ]:
        assert phrase in copy


def test_pages_use_status_formatters_for_primary_status_values() -> None:
    expectations = {
        "pages/PredictionWorkspacePage.tsx": ["formatStatusLabel", "formatNextAction"],
        "pages/DataOnboardingPage.tsx": ["formatStatusLabel", "formatNextAction"],
        "pages/CandidateResearchPage.tsx": ["formatCandidateStatus"],
        "pages/GovernanceConsolePage.tsx": ["formatStatusLabel", "formatNextAction"],
    }

    for relative, required_imports in expectations.items():
        source = _read(relative)
        for required in required_imports:
            assert required in source, f"{relative} must use {required}"


def test_primary_ui_contract_does_not_render_known_bad_concatenated_statuses() -> None:
    combined = "\n".join(
        _read(relative)
        for relative in [
            "pages/CandidateResearchPage.tsx",
            "pages/ResearchArchivePage.tsx",
            "pages/GovernanceConsolePage.tsx",
            "pages/PredictionWorkspacePage.tsx",
            "pages/DataOnboardingPage.tsx",
            "utils/workspaceGuards.ts",
            "components/common/WorkspaceGuardBanner.tsx",
        ]
    )

    for forbidden in ["candidate_v7not_run", "promotion dry-runnot_run"]:
        assert forbidden not in combined
