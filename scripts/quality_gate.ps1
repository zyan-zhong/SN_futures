param(
  [string]$NodePath = "C:\Program Files\nodejs\node.exe",
  [string]$NpmPath = "C:\Program Files\nodejs\npm.cmd",
  [switch]$SkipE2E
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$FrontendDir = Join-Path $ProjectRoot "frontend"
$ReleaseDir = Join-Path $ProjectRoot "release"

function Invoke-GateStep {
  param(
    [string]$Name,
    [scriptblock]$Action
  )
  Write-Host "==> $Name"
  & $Action
  if ($LASTEXITCODE -ne 0) {
    throw "$Name failed with exit code $LASTEXITCODE"
  }
  Write-Host "PASS: $Name"
}

function Assert-PathExists {
  param([string]$Path, [string]$Message)
  if (-not (Test-Path -LiteralPath (Join-Path $ProjectRoot $Path))) {
    throw $Message
  }
}

function Assert-NoCustomerBaselineText {
  $forbidden = @("baseline forecast", "baseline backtest", "fake prediction", "基线预测", "基线回测")
  $targets = @((Join-Path $ProjectRoot "frontend\src"), (Join-Path $ProjectRoot "src\sn_futures"))
  $hits = @()
  foreach ($target in $targets) {
    if (-not (Test-Path $target)) { continue }
    foreach ($file in Get-ChildItem -LiteralPath $target -Recurse -File -ErrorAction SilentlyContinue) {
      try {
        $text = Get-Content -LiteralPath $file.FullName -Raw -ErrorAction Stop
      } catch {
        continue
      }
      foreach ($term in $forbidden) {
        if ($text.IndexOf($term, [System.StringComparison]::OrdinalIgnoreCase) -ge 0) {
          $hits += "$($file.FullName): $term"
        }
      }
    }
  }
  if ($hits.Count -gt 0) {
    throw "Customer-facing baseline/fake prediction text found:`n$($hits -join "`n")"
  }
  Write-Host "PASS: no customer-facing baseline/fake prediction text"
}

function Assert-NoActiveUnlessPromotionPass {
  $activeFiles = @()
  foreach ($root in @("outputs", "app_data\outputs")) {
    $path = Join-Path $ProjectRoot $root
    if (Test-Path $path) {
      $activeFiles += Get-ChildItem -LiteralPath $path -Recurse -Filter "active_model.json" -File -ErrorAction SilentlyContinue
    }
  }
  if ($activeFiles.Count -eq 0) {
    Write-Host "PASS: no active_model.json present"
    return
  }
  foreach ($file in $activeFiles) {
    $dir = Split-Path -Parent $file.FullName
    $promotionReport = Join-Path $dir "promotion_report.json"
    if (-not (Test-Path $promotionReport)) {
      throw "active_model.json exists without promotion_report.json: $($file.FullName)"
    }
    $report = Get-Content -LiteralPath $promotionReport -Raw | ConvertFrom-Json
    $passed = [bool]($report.gate_pass -or $report.passed -or $report.promotion_pass)
    if (-not $passed) {
      throw "active_model.json exists but promotion report does not pass gate: $($file.FullName)"
    }
  }
  Write-Host "PASS: active model files, if any, have promotion pass evidence"
}

function Assert-PrivateSeedNotStatic {
  $blocked = @()
  foreach ($path in @("frontend\dist", "release", "ui_web")) {
    $full = Join-Path $ProjectRoot $path
    if (Test-Path $full) {
      $blocked += Get-ChildItem -LiteralPath $full -Recurse -Filter "private_bundle_seed.json" -File -ErrorAction SilentlyContinue
    }
  }
  if ($blocked.Count -gt 0) {
    throw "private_bundle_seed.json is exposed in a static/release path:`n$($blocked.FullName -join "`n")"
  }
  Write-Host "PASS: private seed is not present in static/release paths"
}

function Assert-ReleaseTreeClean {
  if (-not (Test-Path $ReleaseDir)) {
    Write-Host "PASS: release directory does not exist yet"
    return
  }
  $blocked = Get-ChildItem -LiteralPath $ReleaseDir -Recurse -Force -File -ErrorAction SilentlyContinue |
    Where-Object {
      $_.Name -eq ".env" -or
      $_.Extension -in @(".log", ".sqlite", ".sqlite3", ".db") -or
      $_.FullName -match "\\(logs|cache|db)\\"
    }
  if ($blocked.Count -gt 0) {
    throw "release contains blocked runtime/log/cache/db artifacts:`n$($blocked.FullName -join "`n")"
  }
  Write-Host "PASS: release tree has no .env/log/cache/db artifacts"
}

function Assert-RequiredDocs {
  $required = @(
    "docs\NO_BASELINE_PREDICTION_POLICY.md",
    "docs\REAL_DATA_ONLY_POLICY.md",
    "docs\RUNTIME_SECRET_SANITIZATION.md",
    "docs\PRIVATE_BUNDLE_KEYS.md",
    "docs\PROFESSIONAL_TERMINAL_WORKBENCH.md",
    "docs\ARTIFACT_CENTER.md",
    "docs\CODEBASE_CLEANUP_AUDIT.md",
    "docs\CUSTOMER_RELEASE_REPORT_0.3.8_PRIVATE.md",
    "docs\PRIVATE_RELEASE_NOTES.md",
    "docs\PRODUCTION_RELEASE_GOVERNANCE.md",
    "docs\RELEASE_GUIDE.md"
  )
  foreach ($doc in $required) {
    Assert-PathExists -Path $doc -Message "required document missing: $doc"
  }
  Write-Host "PASS: required governance docs exist"
}

Set-Location $ProjectRoot

Invoke-GateStep "python compileall" { python -m compileall -q . }
Invoke-GateStep "pytest" { pytest -q }
Invoke-GateStep "unittest discover" { python -m unittest discover -s tests -p "test*.py" -v }

Push-Location $FrontendDir
try {
  Invoke-GateStep "frontend typecheck" { & $NpmPath run typecheck }
  Invoke-GateStep "frontend build" { & $NpmPath run build }
  Invoke-GateStep "frontend check:ui" { & $NpmPath run check:ui }
  if (-not $SkipE2E) {
    Invoke-GateStep "frontend test:e2e" { & $NpmPath run test:e2e }
  } else {
    Write-Host "SKIP: frontend test:e2e"
  }
} finally {
  Pop-Location
}

Invoke-GateStep "runtime secret scan" { & (Join-Path $ProjectRoot "scripts\scan_runtime_secrets.ps1") -IncludeSourceTree -AllowPrivateBundleSeed }
Assert-NoCustomerBaselineText
Assert-NoActiveUnlessPromotionPass
Assert-PrivateSeedNotStatic
Assert-ReleaseTreeClean
Assert-RequiredDocs

Write-Host "SNInsightTerminal quality gate passed."
