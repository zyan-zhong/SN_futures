$ErrorActionPreference = "Stop"

Push-Location (Split-Path -Parent $PSScriptRoot)
try {
  $script = @'
import json
import sys
sys.path.insert(0, "src")
from sn_futures.services.all_api_smoke_service import run_all_terminal_api_smoke

report = run_all_terminal_api_smoke()
print(json.dumps({
    "status": report.get("status"),
    "checked_count": report.get("checked_count"),
    "failed_count": report.get("failed_count"),
    "secret_leak_detected": report.get("secret_leak_detected"),
    "output_path": report.get("output_path"),
}, ensure_ascii=False, indent=2))
if report.get("secret_leak_detected"):
    raise SystemExit(1)
'@
  $script | python -
} finally {
  Pop-Location
}
