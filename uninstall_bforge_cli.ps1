$ErrorActionPreference = "Stop"

function Write-Step([string]$Message) {
    Write-Host "[bforge-cli] $Message"
}

$UserBin = Join-Path $HOME "BossCrafts\bin"
$CmdShim = Join-Path $UserBin "bforge.cmd"
$PsShim = Join-Path $UserBin "bforge.ps1"
$ShShim = Join-Path $UserBin "bforge"

foreach ($shim in @($CmdShim, $PsShim, $ShShim)) {
    if (Test-Path $shim) {
        Remove-Item -Path $shim -Force
        Write-Step "Removed $shim"
    }
}

$CurrentPath = [Environment]::GetEnvironmentVariable("Path", "User")
if ($CurrentPath) {
    $segments = $CurrentPath.Split(';') | Where-Object { -not [string]::IsNullOrWhiteSpace($_) }
    $filtered = @()
    foreach ($segment in $segments) {
        if ($segment.TrimEnd('\\') -ine $UserBin.TrimEnd('\\')) {
            $filtered += $segment
        }
    }
    $NewPath = ($filtered -join ';')
    [Environment]::SetEnvironmentVariable("Path", $NewPath, "User")
    Write-Step "Removed $UserBin from user PATH if it was present"
}

Write-Step "Open a new terminal session to refresh PATH changes"
