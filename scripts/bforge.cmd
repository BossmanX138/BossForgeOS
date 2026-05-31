@echo off
setlocal
set "REPO_ROOT=%~dp0.."
set "CONDA_PY=%USERPROFILE%\miniconda3\envs\bossforge\python.exe"
set "RUNTIME_PY=%REPO_ROOT%\.runtime\devpy\Scripts\python.exe"
set "BOSSFORGE_ROOT=%REPO_ROOT%"
set "PYTHONPATH=%REPO_ROOT%;%PYTHONPATH%"

if exist "%CONDA_PY%" (
  "%CONDA_PY%" -m core.utils.bforge %*
  exit /b %ERRORLEVEL%
)

if exist "%RUNTIME_PY%" (
  "%RUNTIME_PY%" -m core.utils.bforge %*
  exit /b %ERRORLEVEL%
)

python -m core.utils.bforge %*
