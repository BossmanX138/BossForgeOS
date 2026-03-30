@echo off
setlocal

set "ROOT=%~dp0"
set "TARGET=%~1"
set "INIT_FLAG="

if /I "%~2"=="--init-repo" (
  set "INIT_FLAG=--init-repo"
)

if "%TARGET%"=="" (
  set "TARGET=%CD%"
)

if exist "%ROOT%\.venv\Scripts\python.exe" (
  "%ROOT%\.venv\Scripts\python.exe" -m core.bforge summon archivist --path "%TARGET%" --open-ledger %INIT_FLAG%
) else (
  python -m core.bforge summon archivist --path "%TARGET%" --open-ledger %INIT_FLAG%
)

endlocal
