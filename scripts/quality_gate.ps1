param(
  [string]$PythonPath = "python",
  [string]$NpmPath = "",
  [switch]$SkipE2E,
  [switch]$SkipFrontend,
  [switch]$SkipFrontendBuild,
  [switch]$SkipPytest,
  [switch]$OnlyScans,
  [switch]$ContinueOnError,
  [switch]$List
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $ProjectRoot

# Cross-platform implementation lives in scripts\quality_gate.py.
# It runs repo cleanliness through scripts\check_repo_cleanliness.py,
# plus compileall, pytest, frontend typecheck/build/check:ui, secret scan,
# real-result sample/baseline scan, historical OHLCV scaling scan,
# API endpoint contract tests, and data watermark schema tests.

$args = @("scripts\quality_gate.py")
if ($NpmPath) { $args += @("--npm", $NpmPath) }
if ($SkipE2E) { $args += "--skip-e2e" }
if ($SkipFrontend) { $args += "--skip-frontend" }
if ($SkipFrontendBuild) { $args += "--skip-frontend-build" }
if ($SkipPytest) { $args += "--skip-pytest" }
if ($OnlyScans) { $args += "--only-scans" }
if ($ContinueOnError) { $args += "--continue-on-error" }
if ($List) { $args += "--list" }

& $PythonPath @args
exit $LASTEXITCODE
