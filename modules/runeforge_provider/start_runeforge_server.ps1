param(
  [switch]$NoWindow,
  [string]$ModelPath = "",
  [string]$PythonPath = ""
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$workspaceRoot = (Resolve-Path (Join-Path $Root "..\..")).Path
Set-Location $Root

$env:RUNEFORGE_HOST = "0.0.0.0"
$env:RUNEFORGE_PORT = "8008"
$env:RUNEFORGE_FAST_MODE = "1"
$env:RUNEFORGE_FAST_MAX_NEW_TOKENS = "512"
$env:RUNEFORGE_WORKSPACE_ROOT = $workspaceRoot
$env:RUNEFORGE_UPLOAD_DIR = (Join-Path $Root "uploads")
$env:RUNEFORGE_AUDIT_LOG_PATH = (Join-Path $Root "logs\runeforge_audit.jsonl")
$env:RUNEFORGE_MEMORY_STORE_PATH = (Join-Path $Root "runeforge_memory_store.json")
$env:RUNEFORGE_AGENT_PROFILE_PATH = (Join-Path $Root "runeforge_agent.profile.json")
$env:RUNEFORGE_AGENT_SCHEMA_JSON_PATH = (Join-Path $Root "bosscrafts_agent.schema.json")
$env:RUNEFORGE_PROVIDER_MANIFEST_PATH = (Join-Path $Root "provider_manifest.json")
$env:RUNEFORGE_PEC_MODEL_PATH = ""
$env:RUNEFORGE_PEC_FALLBACK_MODEL_PATH = ""
$env:RUNEFORGE_PEC_ENABLED = "0"
$env:RUNEFORGE_PEC_RUNTIME_MODE = "auto"
$env:RUNEFORGE_TTS_ENABLED = "1"
$env:RUNEFORGE_TTS_DEFAULT_VOICE_HINT = "zira"
$env:RUNEFORGE_TTS_DEFAULT_RATE = "185"
$env:RUNEFORGE_TTS_DIR = (Join-Path $Root "audio")
$defaultCoderPath = Join-Path $workspaceRoot ".models\Qwen--Qwen2.5-Coder-7B-Instruct-AWQ"
$selectedModelPath = if ($ModelPath) { $ModelPath } else { $defaultCoderPath }
$selectedModelPath = [System.IO.Path]::GetFullPath($selectedModelPath)
$env:RUNEFORGE_BASE_MODEL_PATH = $selectedModelPath.Replace("\","/")

$cpuCount = [Environment]::ProcessorCount
$hfWorkers = [Math]::Min([Math]::Max([int]($cpuCount / 2), 4), 24)
$torchThreads = [Math]::Min([Math]::Max([int]($cpuCount - 2), 4), 16)
$interop = [Math]::Min([Math]::Max([int]($cpuCount / 8), 1), 4)
$env:RUNEFORGE_HF_PARALLEL_LOADING = "true"
$env:RUNEFORGE_HF_PARALLEL_WORKERS = "$hfWorkers"
$env:RUNEFORGE_TORCH_THREADS = "$torchThreads"
$env:RUNEFORGE_TORCH_INTEROP_THREADS = "$interop"
$env:RUNEFORGE_UVICORN_WORKERS = "1"
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"

$registry = @{
  default = @{ model_path = $selectedModelPath.Replace("\","/"); pec_mode = "off" }
  "Qwen2.5-Coder-7B-Instruct-AWQ" = @{ model_path = $selectedModelPath.Replace("\","/"); pec_mode = "off" }
}
$alphaPath = (Join-Path $Root "models/Runeforge_Alpha-7b")
if (Test-Path $alphaPath) {
  $registry["Runeforge_Alpha-7b"] = @{ model_path = $alphaPath.Replace("\","/"); pec_mode = "on" }
}
$env:RUNEFORGE_MODEL_REGISTRY = ($registry | ConvertTo-Json -Compress)
$env:RUNEFORGE_MODEL_PATH = $registry.default.model_path

$runtimePython = Join-Path $workspaceRoot ".runtime\runeforge_provider\Scripts\python.exe"
$py = if ($PythonPath) { $PythonPath } elseif (Test-Path $runtimePython) { $runtimePython } else { "python" }
if (Test-Path $runtimePython) {
  $env:PATH = ((Split-Path -Parent $runtimePython) + ";" + $env:PATH)
}

Write-Host "[Runeforge] Preflight self-heal check..." -ForegroundColor Cyan
Write-Host "[Runeforge] Model: $selectedModelPath" -ForegroundColor Cyan

$requiredModelFiles = @("config.json", "tokenizer.json")
$missingModelFiles = @($requiredModelFiles | Where-Object { -not (Test-Path (Join-Path $selectedModelPath $_)) })
$hasModelWeights = (Test-Path (Join-Path $selectedModelPath "model.safetensors")) -or
  (Test-Path (Join-Path $selectedModelPath "model.safetensors.index.json"))
if ($missingModelFiles.Count -gt 0 -or -not $hasModelWeights) {
  throw "Qwen Coder snapshot is incomplete at '$selectedModelPath'. Run scripts\setup_runeforge_qwen_coder.ps1 first."
}

$requiredDirs = @(
  (Join-Path $Root "logs"),
  (Join-Path $Root "uploads"),
  (Join-Path $Root "audio"),
  (Join-Path $Root "web"),
  (Join-Path $Root "models")
)
foreach ($d in $requiredDirs) {
  if (-not (Test-Path $d)) {
    Write-Host "[Runeforge] Creating missing directory: $d" -ForegroundColor Yellow
    New-Item -ItemType Directory -Force -Path $d | Out-Null
  }
}

$pkgCheckPath = Join-Path $Root "_rf_pkgcheck.py"
@'
import importlib.util
pkgs = ["torch", "fastapi", "uvicorn", "transformers", "python_multipart", "requests", "PIL", "pystray", "jsonschema", "peft"]
missing = [p for p in pkgs if importlib.util.find_spec(p) is None]
print(";".join(missing))
'@ | Set-Content -LiteralPath $pkgCheckPath -Encoding UTF8
$missingRaw = & $py $pkgCheckPath
Remove-Item -LiteralPath $pkgCheckPath -ErrorAction SilentlyContinue
$missingPkgs = @()
if ($LASTEXITCODE -eq 0 -and $missingRaw) {
  $missingPkgs = $missingRaw.Trim().Split(";", [System.StringSplitOptions]::RemoveEmptyEntries)
}
if ($missingPkgs.Count -gt 0) {
  Write-Host "[Runeforge] Missing Python deps: $($missingPkgs -join ', ')" -ForegroundColor Yellow
  $ans = Read-Host "Install missing deps now? (Y/N)"
  if ($ans -match '^(y|yes)$') {
    & $py -m pip install fastapi uvicorn transformers peft python-multipart requests pillow pystray jsonschema
  } else {
    Write-Host "[Runeforge] Skipping dependency install by user choice." -ForegroundColor Yellow
  }
}

if ($NoWindow) {
  Write-Host "[Runeforge] Preflight complete. Starting headless inference server..." -ForegroundColor Green
  & $py "$Root\runeforge_inference_server.py"
} else {
  Write-Host "[Runeforge] Preflight complete. Starting tray controller..." -ForegroundColor Green
  & $py "$Root\runeforge_tray.py"
}
