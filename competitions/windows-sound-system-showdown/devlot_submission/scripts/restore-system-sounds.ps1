param(
    [string]$BackupPath = "$env:LOCALAPPDATA\BossForgeSoundSystem\system-sound-backup.reg"
)

if (-not (Test-Path $BackupPath)) {
    throw "Backup file not found: $BackupPath"
}

reg import "$BackupPath"
Write-Host "System sounds restored from $BackupPath"
