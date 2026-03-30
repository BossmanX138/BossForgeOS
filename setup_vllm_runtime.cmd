@echo off
setlocal

set "BASE_PY="
if exist "C:\Users\%USERNAME%\AppData\Local\Programs\Python\Python312\python.exe" set "BASE_PY=C:\Users\%USERNAME%\AppData\Local\Programs\Python\Python312\python.exe"
if not defined BASE_PY if exist "C:\Program Files\Python312\python.exe" set "BASE_PY=C:\Program Files\Python312\python.exe"
if not defined BASE_PY if exist "C:\Program Files (x86)\Python312\python.exe" set "BASE_PY=C:\Program Files (x86)\Python312\python.exe"
if not defined BASE_PY if exist ".venv\Scripts\python.exe" set "BASE_PY=.venv\Scripts\python.exe"

if defined BASE_PY (
  powershell -ExecutionPolicy Bypass -File .\setup_vllm_runtime.ps1 -BasePython "%BASE_PY%"
) else (
  echo No compatible Python found. Install Python 3.12 or create .venv first.
  exit /b 1
)
