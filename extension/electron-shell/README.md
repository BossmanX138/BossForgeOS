# BossForgeOS Electron Shell

This shell runs Electron over a Python backend in hybrid mode.

## Table of Contents

- [Features](#features)
- [Usage](#usage)
- [Launch-Target Configuration](#launch-target-configuration)
- [Notes](#notes)

## Features

- Electron is the wrapper UI and process orchestrator.
- Python backend remains the runtime underneath.
- Startup probes a health endpoint first and reuses an already-running backend when available.
- If no backend is running, Electron launches a managed backend process.
- Electron only stops the backend on quit when Electron started that backend instance.
- Startup target can be changed so A.S.S. (or any bootstrap entry) can become whatever backend/app you launch.

## Usage

1. Ensure Python and BossForgeOS dependencies are installed.
2. From this directory, run:

```sh
npm install
npm start
```

1. Electron opens the configured backend URL after health checks succeed.

## Launch-Target Configuration

Default behavior:

- Target script: `launcher/bossforge_launcher.py`
- Health endpoint: `/api/status`
- Host: `127.0.0.1`
- Port: `5005`

Environment variables:

- `BOSSFORGE_APP_NAME`: Window/tray label.
- `BOSSFORGE_PROJECT_ROOT`: Project root used for resolving scripts and cwd.
- `BOSSFORGE_PYTHON`: Explicit Python executable.
- `BOSSFORGE_HOST`: Backend host.
- `BOSSFORGE_PORT`: Backend port.
- `BOSSFORGE_START_SCRIPT`: Relative or absolute Python script to launch.
- `BOSSFORGE_START_ARGS`: Space-separated startup args for custom script.
- `BOSSFORGE_START_ARGS_JSON`: JSON array of startup args (preferred for complex args).
- `BOSSFORGE_HEALTH_PATH`: Health probe path.
- `BOSSFORGE_APPEND_DEFAULT_ARGS`: Set to `1` to force default `--no-browser --host --port` args for custom script.

Examples:

```powershell
$env:BOSSFORGE_APP_NAME='A.S.S. Hybrid Shell'; npm start
```

```powershell
$env:BOSSFORGE_START_SCRIPT='launcher/custom_launcher.py'
$env:BOSSFORGE_START_ARGS_JSON='["--mode","hybrid","--profile","default"]'
$env:BOSSFORGE_HEALTH_PATH='/healthz'
npm start
```

## Notes

- If your custom start script does not accept `--host`/`--port`, leave `BOSSFORGE_APPEND_DEFAULT_ARGS` unset.
- Tray icon path remains `assets/bossforgeos.png`.
- You can keep Python as the substrate while swapping launch targets above it.
