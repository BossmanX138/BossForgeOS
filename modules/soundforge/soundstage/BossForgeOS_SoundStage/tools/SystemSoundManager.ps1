param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("install", "status", "rollback")]
    [string]$Action,

    [string]$ManifestPath = "./tools/system-sounds-manifest.json",
    [string]$BackupPath
)

$ErrorActionPreference = "Stop"
$AppEventsRoot = "HKCU:\AppEvents\Schemes\Apps\.Default"
$BackupDir = "./tools/backups"

function Get-EventNodes {
    if (-not (Test-Path $AppEventsRoot)) {
        throw "AppEvents registry root not found: $AppEventsRoot"
    }

    return Get-ChildItem -Path $AppEventsRoot | Sort-Object Name
}

function Backup-SystemSounds {
    New-Item -ItemType Directory -Path $BackupDir -Force | Out-Null

    $stamp = (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssZ")
    $path = Join-Path $BackupDir "system-sounds-backup-$stamp.json"

    $items = @()
    foreach ($eventNode in Get-EventNodes) {
        $currentPath = Join-Path $eventNode.PSPath ".Current"
        $value = ""
        if (Test-Path $currentPath) {
            try {
                $value = (Get-ItemProperty -Path $currentPath -Name "(default)" -ErrorAction Stop)."(default)"
            } catch {
                $value = ""
            }
        }

        $items += [PSCustomObject]@{
            Event = $eventNode.PSChildName
            Current = $value
        }
    }

    $items | ConvertTo-Json -Depth 3 | Set-Content -Path $path -Encoding UTF8
    return $path
}

function Install-SystemSounds {
    if (-not (Test-Path $ManifestPath)) {
        throw "Manifest not found: $ManifestPath"
    }

    $manifest = Get-Content -Path $ManifestPath -Raw | ConvertFrom-Json

    if (-not $manifest.events) {
        throw "Manifest must contain an 'events' object."
    }

    $backup = Backup-SystemSounds
    Write-Host "Backup created: $backup"

    foreach ($property in $manifest.events.PSObject.Properties) {
        $eventName = $property.Name
        $wavPath = [string]$property.Value

        if (-not (Test-Path $wavPath)) {
            throw "WAV file missing for event '$eventName': $wavPath"
        }

        $eventKey = Join-Path $AppEventsRoot $eventName
        $currentKey = Join-Path $eventKey ".Current"

        New-Item -ItemType Directory -Path $currentKey -Force | Out-Null
        Set-ItemProperty -Path $currentKey -Name "(default)" -Value $wavPath

        Write-Host "Mapped $eventName -> $wavPath"
    }

    Write-Host "Install complete."
}

function Show-Status {
    Get-EventNodes |
        ForEach-Object {
            $eventNode = $_
            $currentPath = Join-Path $eventNode.PSPath ".Current"
            $value = ""
            if (Test-Path $currentPath) {
                try {
                    $value = (Get-ItemProperty -Path $currentPath -Name "(default)" -ErrorAction Stop)."(default)"
                } catch {
                    $value = ""
                }
            }

            [PSCustomObject]@{
                Event = $eventNode.PSChildName
                Current = $value
            }
        } |
        Format-Table -AutoSize
}

function Rollback-SystemSounds {
    if (-not $BackupPath) {
        $latest = Get-ChildItem -Path $BackupDir -Filter "system-sounds-backup-*.json" -ErrorAction SilentlyContinue |
            Sort-Object LastWriteTime -Descending |
            Select-Object -First 1

        if (-not $latest) {
            throw "No backup file found in $BackupDir"
        }

        $BackupPath = $latest.FullName
    }

    if (-not (Test-Path $BackupPath)) {
        throw "Backup file not found: $BackupPath"
    }

    $entries = Get-Content -Path $BackupPath -Raw | ConvertFrom-Json

    foreach ($entry in $entries) {
        $eventKey = Join-Path $AppEventsRoot $entry.Event
        $currentKey = Join-Path $eventKey ".Current"

        New-Item -ItemType Directory -Path $currentKey -Force | Out-Null
        Set-ItemProperty -Path $currentKey -Name "(default)" -Value ([string]$entry.Current)

        Write-Host "Restored $($entry.Event)"
    }

    Write-Host "Rollback complete from: $BackupPath"
}

switch ($Action) {
    "install" { Install-SystemSounds }
    "status" { Show-Status }
    "rollback" { Rollback-SystemSounds }
}
