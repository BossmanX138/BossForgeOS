@echo off
setlocal

REM Force workspace-rooted bus/state so profile + model settings are local to this package.
set "BOSSFORGE_ROOT=%CD%"

REM Optional distro selection (set BOSSFORGE_WSL_DISTRO before running this script).
set "WSL_DISTRO_ARG="
if defined BOSSFORGE_WSL_DISTRO set "WSL_DISTRO_ARG=--internal-vllm-wsl-distro %BOSSFORGE_WSL_DISTRO%"

REM Stop stale launcher instances that can hold port 5005 and serve stale state.
taskkill /IM BossForgeLauncher.exe /F >nul 2>nul

if exist ".venv\Scripts\python.exe" (
    .venv\Scripts\python.exe -m launcher.bossforge_launcher --internal-vllm-wsl --internal-vllm-wsl-python python3 %WSL_DISTRO_ARG%
) else (
    python -m launcher.bossforge_launcher --internal-vllm-wsl --internal-vllm-wsl-python python3 %WSL_DISTRO_ARG%
)
