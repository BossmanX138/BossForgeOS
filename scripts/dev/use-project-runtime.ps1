param(
    [switch]$PersistUser
)

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "../..")).Path
$entries = @(
    "C:\Program Files\Git\cmd",
    (Join-Path $repoRoot ".runtime/devpy/Scripts"),
    (Join-Path $repoRoot "scripts")
)

$existing = @($env:Path -split ';' | Where-Object { $_ -and $_.Trim() })
$toAdd = @()
foreach ($entry in $entries) {
    if ((Test-Path $entry) -and -not ($existing -contains $entry)) {
        $toAdd += $entry
    }
}

if ($toAdd.Count -gt 0) {
    $env:Path = (($toAdd + $existing) -join ';')
}

if ($PersistUser) {
    $userPath = [Environment]::GetEnvironmentVariable('Path', 'User')
    $userParts = @($userPath -split ';' | Where-Object { $_ -and $_.Trim() })
    foreach ($entry in $toAdd) {
        if (-not ($userParts -contains $entry)) {
            $userParts = @($entry) + $userParts
        }
    }
    [Environment]::SetEnvironmentVariable('Path', ($userParts -join ';'), 'User')
}

$report = [ordered]@{
    repo_root = $repoRoot
    added_entries = $toAdd
    git = (Get-Command git -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source -ErrorAction SilentlyContinue)
    python = (Get-Command python -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source -ErrorAction SilentlyContinue)
    bforge = (Get-Command bforge -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source -ErrorAction SilentlyContinue)
}

$report | ConvertTo-Json -Depth 4
