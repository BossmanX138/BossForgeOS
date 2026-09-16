@echo off
setlocal

REM One-command Codemage worker launcher.
REM 1) Starts Codemage in background (hidden window)
REM 2) Queues first BossGate completion work item (BG-004) if requested

set "ROOT=%~dp0.."
pushd "%ROOT%" >nul

echo Starting Codemage background worker...
powershell -NoProfile -Command ^
  "$match = Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'python.exe' -and $_.CommandLine -like '*core.agents.codemage_agent*' }; if ($match) { Write-Host 'Codemage already running; skipping spawn.' } else { Start-Process python -ArgumentList '-m core.agents.codemage_agent --interval 8' -WindowStyle Hidden }"

if /I "%~1"=="--no-queue" goto done

echo Queueing BossGate work item BG-004...
python -c "from core.rune.rune_bus import RuneBus, resolve_root_from_env; b=RuneBus(resolve_root_from_env()); p={'packet_id':'bossgate-finish','title':'BG-004 real transfer transport','details':'Implement BG-004 from docs/bossgate_connector_todo.md: upgrade bossgate_transfer_agent from intent logging to real transfer transport with tests and TODO updates.','source':'bossgate_connector_todo','source_path':'docs/bossgate_connector_todo.md','source_line':22}; path=b.emit_command('codemage','work_item',p,issued_by='launcher'); print(f'command written: {path}')"

:done
echo Codemage worker launch sequence complete.
echo Use: python -m core.utils.bforge bossgate tail --limit 25
echo Use: python -m core.utils.bforge tail --limit 50

popd >nul
endlocal
