param(
    [string]$BackupPath = "$env:LOCALAPPDATA\BossForgeSoundSystem\system-sound-backup.reg"
)

$targetDir = Split-Path -Parent $BackupPath
if (-not (Test-Path $targetDir)) {
    New-Item -Path $targetDir -ItemType Directory | Out-Null
}

reg export "HKCU\AppEvents\Schemes\Apps\.Default" "$BackupPath" /y
Write-Host "Backup saved to $BackupPath"
