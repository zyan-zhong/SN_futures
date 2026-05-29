param(
    [Parameter(Mandatory = $true)]
    [string]$ExePath,
    [Parameter(Mandatory = $true)]
    [string]$UninstallPath
)

$shell = New-Object -ComObject WScript.Shell
$desktop = [Environment]::GetFolderPath("Desktop")
$programs = [Environment]::GetFolderPath("Programs")
$folder = Join-Path $programs "SN Insight Terminal"

if (-not (Test-Path $folder)) {
    New-Item -ItemType Directory -Path $folder | Out-Null
}

$desktopShortcut = $shell.CreateShortcut((Join-Path $desktop "SN Insight Terminal.lnk"))
$desktopShortcut.TargetPath = $ExePath
$desktopShortcut.WorkingDirectory = Split-Path $ExePath
$desktopShortcut.Save()

$startShortcut = $shell.CreateShortcut((Join-Path $folder "SN Insight Terminal.lnk"))
$startShortcut.TargetPath = $ExePath
$startShortcut.WorkingDirectory = Split-Path $ExePath
$startShortcut.Save()

$uninstallShortcut = $shell.CreateShortcut((Join-Path $folder "Uninstall SN Insight Terminal.lnk"))
$uninstallShortcut.TargetPath = $UninstallPath
$uninstallShortcut.WorkingDirectory = Split-Path $ExePath
$uninstallShortcut.Save()
