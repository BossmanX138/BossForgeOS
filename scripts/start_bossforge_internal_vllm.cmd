@echo off
setlocal

REM Force workspace-rooted bus/state so profile + model settings are local to this package.
set "BOSSFORGE_ROOT=%CD%"

REM Prefer dedicated internal vLLM runtime if present.
if exist ".runtime\vllm_runtime\Scripts\python.exe" (
    set "BOSSFORGE_INTERNAL_VLLM_PYTHON=%CD%\.runtime\vllm_runtime\Scripts\python.exe"
)

set "PYTHON_BIN="
if exist ".venv\Scripts\python.exe" set "PYTHON_BIN=.venv\Scripts\python.exe"
if not defined PYTHON_BIN if exist "C:\Users\%USERNAME%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" set "PYTHON_BIN=C:\Users\%USERNAME%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
if not defined PYTHON_BIN set "PYTHON_BIN=python"

"%PYTHON_BIN%" -m launcher.bossforge_launcher
