@echo off
setlocal

set "TARGET=%~1"
if "%TARGET%"=="" goto usage

for /f "usebackq delims=" %%I in (`powershell -NoProfile -Command "[uri]::EscapeDataString($args[0])" -- "%TARGET%"`) do set "ENCODED=%%I"
if "%ENCODED%"=="" set "ENCODED=%TARGET%"

set "URL=http://127.0.0.1:5005/?view=view_iconforge^&open_icon=%ENCODED%"
start "" "%URL%"

endlocal
exit /b 0

:usage
echo Usage: open_in_iconforge_context.cmd ^<icon-file-path^>
exit /b 1
