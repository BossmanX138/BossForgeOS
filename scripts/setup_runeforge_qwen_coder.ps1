param(
  [string]$PythonVersion = "3.12",
  [string]$ModelRepo = "Qwen/Qwen2.5-Coder-7B-Instruct-AWQ",
  [string]$TorchIndexUrl = "https://download.pytorch.org/whl/cu128"
)

$ErrorActionPreference = "Stop"
$WorkspaceRoot = Split-Path -Parent $PSScriptRoot
$RuntimeDir = Join-Path $WorkspaceRoot ".runtime\runeforge_provider"
$RuntimePython = Join-Path $RuntimeDir "Scripts\python.exe"
$ModelDir = Join-Path $WorkspaceRoot (".models\" + $ModelRepo.Replace("/", "--"))

$uv = Get-Command uv -ErrorAction SilentlyContinue
if (-not $uv) {
  throw "uv is required. Install uv or place it on PATH before running this setup."
}

if (-not (Test-Path $RuntimePython)) {
  Write-Host "[Runeforge] Creating Python $PythonVersion inference runtime..." -ForegroundColor Cyan
  & $uv.Source venv --python $PythonVersion $RuntimeDir
}

Write-Host "[Runeforge] Installing inference dependencies..." -ForegroundColor Cyan
& $uv.Source pip install --python $RuntimePython --reinstall `
  --index-url $TorchIndexUrl `
  torch `
  torchvision
if ($LASTEXITCODE -ne 0) {
  throw "CUDA PyTorch installation failed."
}

& $uv.Source pip install --python $RuntimePython `
  fastapi `
  uvicorn `
  transformers `
  accelerate `
  gptqmodel `
  peft `
  triton-windows `
  huggingface_hub `
  python-multipart `
  requests `
  pillow `
  pystray `
  jsonschema
if ($LASTEXITCODE -ne 0) {
  throw "Runeforge dependency installation failed."
}

Write-Host "[Runeforge] Resuming Qwen Coder snapshot download..." -ForegroundColor Cyan
$env:RUNEFORGE_SETUP_MODEL_REPO = $ModelRepo
$env:RUNEFORGE_SETUP_MODEL_DIR = $ModelDir
& $RuntimePython (Join-Path $PSScriptRoot "download_runeforge_qwen_coder.py")
if ($LASTEXITCODE -ne 0) {
  throw "Qwen Coder snapshot download failed."
}

Write-Host "[Runeforge] Qwen Coder runtime is ready." -ForegroundColor Green
Write-Host "Launch with: modules\runeforge_provider\Start-Runeforge-Server.cmd" -ForegroundColor Green
