param(
    [string]$BaseUrl = "http://127.0.0.1:8765"
)

$ErrorActionPreference = "Stop"

function Zh([string]$Base64) {
    return [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($Base64))
}

$T = @{
    Prefix = "6L+Q6KGM5pyf6K+K5pat"
    UserDir = "55So5oi35pWw5o2u55uu5b2V"
    OutputDir = "6aKE5rWL6L6T5Ye655uu5b2V"
    ReportDir = "5oql5ZGK55uu5b2V"
    ConfigDir = "6YWN572u55uu5b2V"
    Exists = "5a2Y5Zyo"
    Missing = "5LiN5a2Y5Zyo"
    RequestApi = "6K+35rGC6K+K5pat5o6l5Y+j"
    ApiOk = "6K+K5pat5o6l5Y+j5Y+v6K6/6Zeu"
    ApiFail = "6K+K5pat5o6l5Y+j5pqC5LiN5Y+v6K6/6Zeu77yM5bCG5LuF5L+d5a2Y5pys5Zyw5paH5Lu25qOA5p+l57uT5p6c"
    RestartBackend = "5ZCv5Yqo5ZCO56uv5ZCO6YeN5paw6L+Q6KGM5pys6ISa5pys"
    ConfigureKey = "6YWN572uIEFQSSBrZXk="
    RefreshData = "6L+Q6KGM5pWw5o2u5Yi35paw"
    GeneratePrediction = "55Sf5oiQ6aKE5rWL"
    GenerateReport = "55Sf5oiQ5oql5ZGK"
    Saved = "6K+K5pat57uT5p6c5bey5L+d5a2Y"
    NoCache = "57uT6K6677ya5pyq5om+5Yiw6aKE5rWL57yT5a2Y"
    NoPrediction = "57uT6K6677ya5pyq5om+5Yiw5Y+v5bGV56S66aKE5rWL5Y2h54mH"
    NoReport = "57uT6K6677ya5pyq5om+5Yiw5oql5ZGKIE1hcmtkb3du"
    NoNews = "57uT6K6677ya5pyq5om+5Yiw5paw6Ze7L+S6i+S7tuW6k+iusOW9lQ=="
    NoProviderValidation = "57uT6K6677ya5b2T5YmN5LuF6IO956Gu6K6k6YWN572u54q25oCB77yM5bCa5pyq5a6M5oiQIHByb3ZpZGVyIOWunumZheivt+axgumqjOivgQ=="
    NextStep = "5bu66K6u5LiL5LiA5q2l"
}

function Write-Info([string]$Message) {
    Write-Host ("[{0}] {1}" -f (Zh $T.Prefix), $Message)
}

$userRoot = Join-Path $env:LOCALAPPDATA "SNInsightTerminal"
$outputDir = Join-Path $userRoot "outputs"
$reportDir = Join-Path $userRoot "reports"
$configDir = Join-Path $userRoot "config"
$logsDir = Join-Path $userRoot "logs"
$secretsPath = Join-Path $configDir "secrets.json"

New-Item -ItemType Directory -Force -Path $logsDir | Out-Null

Write-Info ("{0}: {1}" -f (Zh $T.UserDir), $userRoot)
Write-Info ("{0}: {1}" -f (Zh $T.OutputDir), $outputDir)
Write-Info ("{0}: {1}" -f (Zh $T.ReportDir), $reportDir)
Write-Info ("{0}: {1}" -f (Zh $T.ConfigDir), $configDir)
Write-Info ("secrets.json: {0}" -f ($(if (Test-Path $secretsPath) { Zh $T.Exists } else { Zh $T.Missing })))

$endpoint = "$BaseUrl/api/terminal/runtime-diagnostics"
$localSummary = [ordered]@{
    user_data_dir = $userRoot
    output_dir = $outputDir
    report_dir = $reportDir
    config_dir = $configDir
    secrets_path_exists = (Test-Path $secretsPath)
    forecast_files = @(
        "sn_unified_forecast.json",
        "sn_live_predictions.json",
        "sn_live_snapshot.json"
    ) | ForEach-Object {
        $path = Join-Path $outputDir $_
        [ordered]@{ name = $_; exists = (Test-Path $path); path = $path }
    }
    report_files = @(
        "sn_daily_report.md",
        "sn_weekly_report.md",
        "sn_monthly_report.md",
        "sn_event_report.md"
    ) | ForEach-Object {
        $path = Join-Path $reportDir $_
        [ordered]@{ name = $_; exists = (Test-Path $path); path = $path }
    }
}

try {
    Write-Info ("{0}: {1}" -f (Zh $T.RequestApi), $endpoint)
    $apiResult = Invoke-RestMethod -Method Get -Uri $endpoint -TimeoutSec 10
    $result = $apiResult
    Write-Info (Zh $T.ApiOk)
} catch {
    Write-Info (Zh $T.ApiFail)
    $result = [ordered]@{
        api_error = $_.Exception.Message
        local_summary = $localSummary
        data_gap_conclusion = [ordered]@{
            no_cache_files = -not ($localSummary.forecast_files | Where-Object { $_.exists })
            no_reports = -not ($localSummary.report_files | Where-Object { $_.exists })
            no_predictions = $true
            no_news_events = $true
            no_provider_validation = $true
            frontend_only_shell = $true
        }
        next_actions_zh = @(
            (Zh $T.RestartBackend),
            (Zh $T.ConfigureKey),
            (Zh $T.RefreshData),
            (Zh $T.GeneratePrediction),
            (Zh $T.GenerateReport)
        )
    }
}

$outPath = Join-Path $logsDir "runtime_diagnostics.json"
$json = $result | ConvertTo-Json -Depth 20
$json | Set-Content -Path $outPath -Encoding UTF8

Write-Info ("{0}: {1}" -f (Zh $T.Saved), $outPath)

$conclusion = $result.data_gap_conclusion
if ($null -ne $conclusion) {
    if ($conclusion.no_cache_files) { Write-Info (Zh $T.NoCache) }
    if ($conclusion.no_predictions) { Write-Info (Zh $T.NoPrediction) }
    if ($conclusion.no_reports) { Write-Info (Zh $T.NoReport) }
    if ($conclusion.no_news_events) { Write-Info (Zh $T.NoNews) }
    if ($conclusion.no_provider_validation) { Write-Info (Zh $T.NoProviderValidation) }
}

if ($result.next_actions_zh) {
    Write-Info (Zh $T.NextStep)
    foreach ($action in $result.next_actions_zh) {
        Write-Host "  - $action"
    }
}
