param(
    [string]$Root = $env:LOCALAPPDATA,
    [switch]$IncludeRelease,
    [switch]$IncludeSourceTree,
    [switch]$AllowPrivateBundleSeed
)

$ErrorActionPreference = "Stop"

function Test-SecretLikeLine {
    param([string]$Text)
    # High-risk literal assignment/header forms only, including X-Api-Key.
    # Field names such as
    # apiKey/source/token in frontend bundles are not enough to mark leakage.
    $placeholder = '(\[?masked\]?|\[?redacted\]?|\*{3,}|%2A%2A%2A|<[^>]+>|YOUR_|TEST_|example)'
    if ($Text -match '(?i)(?<![A-Za-z0-9_])(apikey|api_key)\s*=\s*(?!' + $placeholder + ')[^&\s,;''"]{8,}') { return $true }
    if ($Text -match '(?i)(?<![A-Za-z0-9_])(x-api-key|authorization)\s*[:=]\s*["'']?(?!' + $placeholder + ')[A-Za-z0-9._\-]{12,}') { return $true }
    if ($Text -match '(?i)Bearer\s+(?!' + $placeholder + ')[A-Za-z0-9._-]{12,}') { return $true }
    if ($Text -match '(?i)(SN_ALPHA_VANTAGE_KEY|SN_NEWSAPI_KEY|SN_MANAGED_PROXY_TOKEN|SN_MANAGED_DATA_PROXY_TOKEN|SN_TUSHARE_TOKEN)\s*=\s*(?!' + $placeholder + ')([A-Za-z0-9._\-]{8,})') { return $true }
    return $false
}

function Get-ResolvedSecretValues {
    $projectRoot = Get-Location
    $python = @"
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(r"$projectRoot") / "src"))
try:
    from sn_futures.services.api_key_resolver import resolved_secret_value
    import os
    names = ["SN_ALPHA_VANTAGE_KEY", "SN_NEWSAPI_KEY", "SN_MANAGED_PROXY_TOKEN", "SN_MANAGED_DATA_PROXY_TOKEN", "SN_TUSHARE_TOKEN"]
    values = [resolved_secret_value(name) for name in names]
    values.extend(str(os.environ.get(name, "")) for name in names)
    print(json.dumps([value for value in values if value and len(value) >= 8]))
except Exception:
    print("[]")
"@
    try {
        $values = $python | python - | ConvertFrom-Json
        return @($values)
    } catch {
        return @()
    }
}

$userRoot = Join-Path $Root "SNInsightTerminal"
$targets = @(
    (Join-Path $userRoot "logs"),
    (Join-Path $userRoot "outputs"),
    (Join-Path $userRoot "cache"),
    (Join-Path (Get-Location) "release_build_log.txt"),
    (Join-Path (Get-Location) "frontend\dist")
)

if ($IncludeSourceTree) {
    $targets += Join-Path (Get-Location) "src"
    $targets += Join-Path (Get-Location) "packaging"
    $targets += Join-Path (Get-Location) "docs"
    $targets += Join-Path (Get-Location) "tests"
}

if ($IncludeRelease) {
    $targets += Join-Path (Get-Location) "dist"
    $targets += Join-Path (Get-Location) "release"
}

$findings = @()
$resolvedSecrets = Get-ResolvedSecretValues
$projectRoot = (Get-Location).Path
$sourceRoots = @(
    (Join-Path $projectRoot "src"),
    (Join-Path $projectRoot "packaging"),
    (Join-Path $projectRoot "docs"),
    (Join-Path $projectRoot "tests")
)
foreach ($target in $targets) {
    if (-not (Test-Path $target)) { continue }
    $item = Get-Item $target
    $files = if ($item.PSIsContainer) {
        Get-ChildItem -LiteralPath $target -Recurse -File -ErrorAction SilentlyContinue
    } else {
        @($item)
    }
    foreach ($file in $files) {
        if ($file.FullName -match '\\private\\private_bundle_seed\.json$|\\build\\private_bundle_seed\.json$') {
            $findings += [pscustomobject]@{
                Path = $file.FullName
                Status = "private_bundle_seed_present"
                Message = "Private bundle seed exists; content was not read."
            }
            if ($AllowPrivateBundleSeed) {
                continue
            }
        }
        if ($file.FullName -match '\\packaging\\private_release_keys\.json$') {
            $findings += [pscustomobject]@{
                Path = $file.FullName
                Status = "private_release_keys_present"
                Message = "Private release key file exists; content was not read."
            }
            continue
        }
        if ($file.FullName -match '\\config\\secrets\.json$') {
            $findings += [pscustomobject]@{
                Path = $file.FullName
                Status = "config_file_present"
                Message = "Config file exists; content was not read."
            }
            continue
        }
        try {
            $content = Get-Content -LiteralPath $file.FullName -Raw -ErrorAction Stop
        } catch {
            continue
        }
        if ($null -eq $content) {
            continue
        }
        $exactSecretHit = $false
        foreach ($secret in $resolvedSecrets) {
            if ($content.Contains([string]$secret)) {
                $exactSecretHit = $true
                break
            }
        }
        $sourceTreeFile = $false
        foreach ($sourceRoot in $sourceRoots) {
            if ($file.FullName.StartsWith($sourceRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
                $sourceTreeFile = $true
                break
            }
        }
        if ($exactSecretHit) {
            $findings += [pscustomobject]@{
                Path = $file.FullName
                Status = "exact_secret_leak"
                Message = "Exact configured secret value found outside allowed config."
            }
        } elseif (Test-SecretLikeLine $content) {
            $findings += [pscustomobject]@{
                Path = $file.FullName
                Status = if ($sourceTreeFile) { "source_pattern_review" } else { "possible_secret" }
                Message = if ($sourceTreeFile) { "Sensitive field pattern in source; review only." } else { "Possible unsanitized sensitive field found; manual review required." }
            }
        }
    }
}

$summary = [pscustomobject]@{
    scanned_at = (Get-Date).ToString("s")
    user_data_root = $userRoot
    finding_count = @($findings | Where-Object { $_.Status -in @("exact_secret_leak", "possible_secret") }).Count
    findings = $findings
}

$outDir = Join-Path $userRoot "logs"
New-Item -ItemType Directory -Force -Path $outDir | Out-Null
$outPath = Join-Path $outDir "runtime_secret_scan.json"
$summary | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $outPath -Encoding UTF8

Write-Host "Runtime secret scan complete: $outPath"
if ($summary.finding_count -gt 0) {
    Write-Host "Possible secret findings detected; inspect the JSON report." -ForegroundColor Yellow
    exit 1
}
Write-Host "No complete key leakage detected." -ForegroundColor Green
