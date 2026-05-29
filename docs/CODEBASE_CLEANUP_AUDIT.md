# Codebase Cleanup Audit

Date: 2026-05-29
Target release: `0.3.8-private-research-beta.1`

This audit records the cleanup boundary for the private research release. The cleanup intentionally avoids model logic changes, active model publication, customer prediction generation, and embedded key disclosure.

## Classification

| Category | Current handling |
| --- | --- |
| Production source | Kept under `src/sn_futures`, `frontend/src`, `packaging`, and `scripts`. |
| Tests | Kept. No test tree was deleted. |
| Documentation | Current release docs kept; superseded validation reports moved to `docs/archive`. |
| Release scripts | Kept and updated with `scripts/quality_gate.ps1`. |
| Sample data | Kept. `sample_data` was not removed. |
| Legacy UI | Kept. `ui_web` remains packaged for `/legacy`. |
| Outdated prompt/intermediate docs | Superseded validation reports archived, not deleted. |
| Temporary outputs | Removed from workspace where reproducible: root `tmp_*`, setup smoke scratch files, old e2e screenshots, `build`, `dist`, `.pytest_cache`, Python cache. |
| Old release | Removed `release_archive` because it contained obsolete historical bundles and is ignored by Git. |
| Dead code | No risky service deletion performed in this pass. Candidate duplicates require separate behavior-level refactor. |
| Duplicate service | Not merged in this pass to avoid changing research/model behavior. |
| Malformed/garbled text | Fixed packaging installer UI text, release guide, and PyInstaller missing-frontend error. Existing compatibility fallback strings in code/tests were left intact when behavior depends on them. |

## Cleaned Files And Directories

- `release_archive/`
- `build/`
- `dist/`
- `.pytest_cache/`
- `__pycache__/`
- `tmp_chrome_dump_v38/`
- `tmp_chrome_profile_v38/`
- `tmp_chrome_profile_v38b/`
- `tmp_api_err.log`
- `tmp_api_err.txt`
- `tmp_api_out.log`
- `tmp_api_out.txt`
- `tmp_v38_api_err.log`
- `tmp_v38_api_out.log`
- `tmp_v38_pkg_api_err.log`
- `tmp_v38_pkg_api_out.log`
- `setup_gpu_smoke.txt`
- `setup_smoke_new.txt`
- `setup_smoke_ok.txt`
- `release/installed_setup.log`
- `release/installed_uninstall.log`
- `e2e-artifacts/screenshots/market-refresh-validation.png`
- `e2e-artifacts/screenshots/data-status.png`

## Archived Documents

- `docs/archive/CUSTOMER_RELEASE_REPORT_0.3.3.md`
- `docs/archive/VALIDATION_REPORT.md`
- `docs/archive/RELEASE_VALIDATION_REPORT.md`

## Protected Content

The following were explicitly not deleted:

- `tests/`
- `docs/NO_BASELINE_PREDICTION_POLICY.md`
- `docs/REAL_DATA_ONLY_POLICY.md`
- `src/sn_futures/utils/secret_sanitizer.py`
- `docs/PRIVATE_BUNDLE_KEYS.md`
- `ui_web/`
- `sample_data/`
- current `release/SNInsightTerminal_Setup.exe` until rebuilt
- user runtime directory under `%LOCALAPPDATA%\SNInsightTerminal`

## Quality Gate

`scripts/quality_gate.ps1` now performs compile, unit, frontend, e2e, secret-scan, no-baseline text, active-model promotion, private-seed exposure, release cleanliness, and required-document checks.
