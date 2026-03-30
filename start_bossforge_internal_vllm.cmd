@echo off
setlocal

REM Force workspace-rooted bus/state so profile + model settings are local to this package.
set "BOSSFORGE_ROOT=%CD%"

REM Prefer dedicated internal vLLM runtime if present.
if exist ".runtime\vllm_runtime\Scripts\python.exe" (
    set "BOSSFORGE_INTERNAL_VLLM_PYTHON=%CD%\.runtime\vllm_runtime\Scripts\python.exe"
)

REM Stop stale launcher instances that can hold port 5005 and serve stale state.
taskkill /IM BossForgeLauncher.exe /F >nul 2>nul

if exist ".venv\Scripts\python.exe" (
    .venv\Scripts\python.exe -m launcher.bossforge_launcher
) else (
    python -m launcher.bossforge_launcher
)
