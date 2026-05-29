param(
    [string]$PythonExe = "python",
    [ValidateSet("cpu", "gpu")]
    [string]$BuildFlavor = "cpu",
    [string]$Version = "V3.5",
    [switch]$SkipAppBuild
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$releaseDir = Join-Path $root "release"
$releaseArchiveRoot = Join-Path $root "release_archive"
$buildDir = Join-Path $root "build"
$distDir = Join-Path $root "dist"
$iconScript = Join-Path $root "scripts\generate_app_icon.py"
$appSpec = if ($BuildFlavor -eq "gpu") {
    Join-Path $root "packaging\SNInsightTerminalAppGpu.spec"
} else {
    Join-Path $root "packaging\SNInsightTerminalApp.spec"
}
$appDist = Join-Path $distDir "app"
$appWork = Join-Path $buildDir "app"
$appBundleZip = Join-Path $buildDir ($(if ($BuildFlavor -eq "gpu") { "app_bundle_gpu.zip" } else { "app_bundle_cpu.zip" }))
$releaseBundleZip = Join-Path $releaseDir ($(if ($BuildFlavor -eq "gpu") { "SNInsightTerminal_GPU_AppBundle.zip" } else { "SNInsightTerminal_AppBundle.zip" }))
$portableDir = Join-Path $releaseDir ($(if ($BuildFlavor -eq "gpu") { "SNInsightTerminal_GPU_Portable" } else { "SNInsightTerminal_Portable" }))
$setupExe = Join-Path $releaseDir ($(if ($BuildFlavor -eq "gpu") { "SNInsightTerminal_GPU_Setup.exe" } else { "SNInsightTerminal_Setup.exe" }))
$versionedSetupExe = Join-Path $releaseDir ($(if ($BuildFlavor -eq "gpu") { "SNInsightTerminal_${Version}_GPU_Full_Setup.exe" } else { "SNInsightTerminal_${Version}_CPU_Lite_Setup.exe" }))
$latestSetupExe = Join-Path $releaseDir ($(if ($BuildFlavor -eq "gpu") { "SNInsightTerminal_Latest_GPU_Full_Setup.exe" } else { "SNInsightTerminal_Latest_Setup.exe" }))
$legacyOnefileExe = Join-Path $releaseDir "SNInsightTerminal.exe"
$setupSource = Join-Path $root "packaging\installer\NativeSetup.cs"
$setupDist = Join-Path $distDir "setup"
$setupWork = Join-Path $buildDir "setup"

New-Item -ItemType Directory -Force -Path $releaseDir | Out-Null
New-Item -ItemType Directory -Force -Path $releaseArchiveRoot | Out-Null
New-Item -ItemType Directory -Force -Path $buildDir | Out-Null

$archiveDir = Join-Path $releaseArchiveRoot ("archive_" + (Get-Date -Format "yyyyMMdd_HHmmss"))
$oldReleaseArtifacts = @()
$oldReleaseArtifacts += Get-ChildItem -LiteralPath $releaseDir -Filter "SNInsightTerminal*Setup.exe" -ErrorAction SilentlyContinue
$oldReleaseArtifacts += Get-ChildItem -LiteralPath $releaseDir -Filter "SNInsightTerminal_GPU_AppBundle.zip" -ErrorAction SilentlyContinue
$oldReleaseArtifacts += Get-ChildItem -LiteralPath $releaseDir -Filter "SNInsightTerminal*Portable" -ErrorAction SilentlyContinue
$oldReleaseArtifacts += Get-ChildItem -LiteralPath $releaseDir -Filter "*说明*.txt" -ErrorAction SilentlyContinue
if ($oldReleaseArtifacts.Count -gt 0) {
    New-Item -ItemType Directory -Force -Path $archiveDir | Out-Null
    foreach ($artifact in $oldReleaseArtifacts) {
        Move-Item -LiteralPath $artifact.FullName -Destination (Join-Path $archiveDir $artifact.Name) -Force
    }
    Write-Host "Archived old installers to: $archiveDir"
}

& $PythonExe $iconScript

foreach ($path in @($setupDist, $setupWork)) {
    if (Test-Path $path) {
        Remove-Item -LiteralPath $path -Recurse -Force
    }
}

foreach ($path in @($setupExe, $versionedSetupExe, $latestSetupExe, $legacyOnefileExe)) {
    if (Test-Path $path) {
        Remove-Item -LiteralPath $path -Force
    }
}

if (-not $SkipAppBuild) {
    foreach ($path in @($appDist, $appWork, $portableDir, $appBundleZip, $releaseBundleZip)) {
        if (Test-Path $path) {
            Remove-Item -LiteralPath $path -Recurse -Force
        }
    }

    Push-Location $root
    & $PythonExe -m PyInstaller --clean --noconfirm --distpath $appDist --workpath $appWork $appSpec
    $appExit = $LASTEXITCODE
    Pop-Location
    if ($appExit -ne 0) {
        throw "App build failed with exit code $appExit"
    }

    $appSource = Join-Path $appDist "SNInsightTerminal"
    Copy-Item -LiteralPath $appSource -Destination $portableDir -Recurse -Force

    Push-Location $portableDir
    Compress-Archive -Path * -DestinationPath $appBundleZip -Force
    Pop-Location
} else {
    if (-not (Test-Path $portableDir)) {
        throw "SkipAppBuild was requested, but portable app folder was not found: $portableDir"
    }
    if (-not (Test-Path $appBundleZip)) {
        Push-Location $portableDir
        Compress-Archive -Path * -DestinationPath $appBundleZip -Force
        Pop-Location
    }
}

$cscCandidates = @(
    (Join-Path $env:WINDIR "Microsoft.NET\Framework64\v4.0.30319\csc.exe"),
    (Join-Path $env:WINDIR "Microsoft.NET\Framework\v4.0.30319\csc.exe")
)
$cscExe = $cscCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $cscExe) {
    throw "csc.exe not found. Cannot build native setup launcher."
}

$compilerArgs = @(
    "/nologo",
    "/target:winexe",
    "/platform:anycpu",
    "/optimize+",
    "/out:$setupExe",
    "/win32icon:$($root)\assets\sn_insight_terminal.ico",
    "/r:System.dll",
    "/r:System.Core.dll",
    "/r:System.Drawing.dll",
    "/r:System.Windows.Forms.dll",
    "/r:System.IO.Compression.dll",
    "/r:System.IO.Compression.FileSystem.dll",
    "/r:Microsoft.CSharp.dll",
    $setupSource
)

if ($BuildFlavor -eq "cpu") {
    $compilerArgs = $compilerArgs[0..4] + @("/resource:$appBundleZip,AppBundleZip") + $compilerArgs[5..($compilerArgs.Count - 1)]
} else {
    Copy-Item -LiteralPath $appBundleZip -Destination $releaseBundleZip -Force
}

& $cscExe $compilerArgs
$setupExit = $LASTEXITCODE
if ($setupExit -ne 0 -or -not (Test-Path $setupExe)) {
    throw "Native setup build failed with exit code $setupExit"
}

Write-Host "Portable app folder: $portableDir"
Write-Host "Setup exe: $setupExe"
if ($BuildFlavor -eq "gpu") {
    Write-Host "GPU setup sidecar bundle: $releaseBundleZip"
    Write-Host "Keep the GPU setup exe and sidecar zip in the same folder before running the installer."
}

if (Test-Path $portableDir) {
    Remove-Item -LiteralPath $portableDir -Recurse -Force
    Write-Host "Removed portable staging folder from release directory; official distribution is the setup exe only."
}
