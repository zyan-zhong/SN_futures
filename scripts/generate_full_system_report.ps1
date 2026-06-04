$ErrorActionPreference = "Stop"

Push-Location (Split-Path -Parent $PSScriptRoot)
try {
  $script = @'
import json
import sys
sys.path.insert(0, "src")
from sn_futures.services.full_system_report_service import build_full_system_txt_report

result = build_full_system_txt_report()
print(json.dumps({
    "status": result.get("status"),
    "txt_path": result.get("txt_path"),
    "latest_txt_path": result.get("latest_txt_path"),
    "json_path": result.get("json_path"),
}, ensure_ascii=False, indent=2))
if result.get("status") != "success":
    raise SystemExit(1)
'@
  $script | python -
} finally {
  Pop-Location
}
