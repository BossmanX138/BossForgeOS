@echo off
setlocal

set "PYTHON_BIN="
if exist ".venv\Scripts\python.exe" set "PYTHON_BIN=.venv\Scripts\python.exe"
if not defined PYTHON_BIN if exist "C:\Users\%USERNAME%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" set "PYTHON_BIN=C:\Users\%USERNAME%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
if not defined PYTHON_BIN set "PYTHON_BIN=python"

"%PYTHON_BIN%" -m launcher.bossforge_launcher
