@echo off
setlocal

set "TARGET=%~1"
if "%TARGET%"=="" goto usage

set "ROOT=%~dp0.."
set "PYTHON_EXE=%ROOT%\.venv\Scripts\python.exe"
set "LAUNCHER=%ROOT%\launcher\bossforge_launcher.py"
set "BASE_URL=http://127.0.0.1:5005"
set "HEALTH_URL=%BASE_URL%/"

for /f "usebackq delims=" %%I in (`powershell -NoProfile -Command "[uri]::EscapeDataString($args[0])" -- "%TARGET%"`) do set "ENCODED=%%I"
if "%ENCODED%"=="" set "ENCODED=%TARGET%"

call :ensure_hall_running

set "URL=%BASE_URL%/?view=iconforge^&open_icon=%ENCODED%"
start "" "%URL%"

endlocal
exit /b 0

:ensure_hall_running
call :is_hall_running
if not errorlevel 1 goto :eof

if not exist "%PYTHON_EXE%" goto :eof
if not exist "%LAUNCHER%" goto :eof

start "BossForgeOS Control Hall" /min "%PYTHON_EXE%" "%LAUNCHER%" --hall-only --no-browser --no-tray-icon --host 127.0.0.1 --port 5005 >nul 2>&1

for /l %%N in (1,1,6) do (
	call :is_hall_running
	if not errorlevel 1 goto :eof
	>nul ping 127.0.0.1 -n 2
)
goto :eof

:is_hall_running
curl.exe --silent --max-time 1 "%HEALTH_URL%" >nul 2>&1
if %errorlevel%==0 exit /b 0
exit /b 1

:usage
echo Usage: open_in_iconforge_context.cmd ^<icon-file-path^>
exit /b 1
