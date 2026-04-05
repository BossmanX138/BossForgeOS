@echo off
setlocal

REM Stop stale launcher instances that can hold port 5005 and serve a broken UI state.
taskkill /IM BossForgeLauncher.exe /F >nul 2>nul

if exist ".venv\Scripts\python.exe" (
	.venv\Scripts\python.exe -m launcher.bossforge_launcher
) else (
	python -m launcher.bossforge_launcher
)
