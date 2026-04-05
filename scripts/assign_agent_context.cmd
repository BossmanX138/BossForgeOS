@echo off
setlocal

set "ROOT=%~dp0"
set "AGENT=%~1"
set "TARGET=%~2"

if "%AGENT%"=="" goto usage
if "%TARGET%"=="" set "TARGET=%CD%"

if exist "%ROOT%\.venv\Scripts\python.exe" (
  "%ROOT%\.venv\Scripts\python.exe" -m core.bforge assign set "%TARGET%" --agent "%AGENT%"
) else (
  python -m core.bforge assign set "%TARGET%" --agent "%AGENT%"
)

goto :eof

:usage
echo Usage: assign_agent_context.cmd ^<agent^> [path]
exit /b 1
