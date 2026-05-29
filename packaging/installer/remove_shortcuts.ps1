$desktop = [Environment]::GetFolderPath("Desktop")
$programs = [Environment]::GetFolderPath("Programs")
$folder = Join-Path $programs "SN Insight Terminal"

$desktopShortcut = Join-Path $desktop "SN Insight Terminal.lnk"
if (Test-Path $desktopShortcut) {
    Remove-Item -LiteralPath $desktopShortcut -Force
}

if (Test-Path $folder) {
    Remove-Item -LiteralPath $folder -Recurse -Force
}
