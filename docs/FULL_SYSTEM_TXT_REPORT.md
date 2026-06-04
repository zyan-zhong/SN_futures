# Full System TXT Report

`full_system_report_service` writes a plain-text operational report for handoff and follow-up diagnosis.

Outputs:

- `outputs/reports/full_system_report_YYYYMMDD_HHMMSS.txt`
- `outputs/reports/full_system_report_latest.txt`
- `outputs/reports/full_system_report_latest.json`

The report covers process lifecycle, API health, data sources, data watermarks, sample/real data boundary, feature coverage, training datasets, candidate/active status, OOF validation, research backtests, task queue, frontend status, security, known issues, and recommendations.

The report is diagnostic only. It does not train models, publish active models, generate customer predictions, lower promotion gates, or fabricate baseline/fake predictions.

Run:

```powershell
.\scripts\generate_full_system_report.ps1
```
