@echo off
setlocal

REM Stop stale launcher instances that can hold port 5005 and serve a broken UI state.
taskkill /IM BossForgeLauncher.exe /F >nul 2>nul

set "PYTHON_BIN="
if exist ".venv\Scripts\python.exe" set "PYTHON_BIN=.venv\Scripts\python.exe"
if not defined PYTHON_BIN if exist "C:\Users\%USERNAME%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" set "PYTHON_BIN=C:\Users\%USERNAME%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
if not defined PYTHON_BIN set "PYTHON_BIN=python"

"%PYTHON_BIN%" -m launcher.bossforge_launcher
