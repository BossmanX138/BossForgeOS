param(
    [string]$EnvName = "bossforge"
)

$ErrorActionPreference = "Stop"

function Write-Step([string]$Message) {
    Write-Host "[bootstrap-dev] $Message"
}

$CondaBat = Join-Path $HOME "miniconda3\condabin\conda.bat"
if (-not (Test-Path $CondaBat)) {
    throw "Miniconda not found at $CondaBat. Install Miniconda first."
}

Write-Step "Ensuring conda channel terms are accepted..."
& $CondaBat tos accept --override-channels --channel https://repo.anaconda.com/pkgs/main | Out-Null
& $CondaBat tos accept --override-channels --channel https://repo.anaconda.com/pkgs/r | Out-Null
& $CondaBat tos accept --override-channels --channel https://repo.anaconda.com/pkgs/msys2 | Out-Null

Write-Step "Creating/updating conda env: $EnvName"
& $CondaBat create -y -n $EnvName python=3.12

Write-Step "Installing dependencies into $EnvName"
& $CondaBat run -n $EnvName python -m pip install --upgrade pip
& $CondaBat run -n $EnvName pip install -r docs/requirements.txt
& $CondaBat run -n $EnvName pip install pandas duckdb requests msal oauthlib werkzeug psutil pyyaml

Write-Step "Installing bforge CLI shims"
powershell -ExecutionPolicy Bypass -File .\scripts\install_bforge_cli.ps1

Write-Step "Bootstrap complete. Open a new terminal, then run: bforge module doctor --include-external"
