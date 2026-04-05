# BossForgeOS SoundStage Daemon

The SoundStage daemon is a deterministic sound engine for Windows, restoring true "Open Program" and "Close Program" sounds, with per-app overrides and a local HTTP API for integration and control. It is fully integrated with BossForgeOS, the Control Hall GUI, and the VS Code extension.

## Table of Contents

- [Features](#features)
- [Usage](#usage)
- [Extending](#extending)
- [Requirements](#requirements)
- [Cross-References](#cross-references)
- [License](#license)

## Features
- Monitors real, user-facing top-level windows and process IDs
- Ignores hidden/system/invisible windows and known system processes
- Detects true program open/close events (debounced, no false positives)
- Plays mapped WAVs for open/close, with per-app overrides
- Exposes a local HTTP API (Flask) with endpoints:
  - `/status`: Get current state and config
  - `/play`: Trigger a sound (open/close/custom)
  - `/set-mapping`: Update sound mappings
  - `/log`: Retrieve event log
- Integrated with Control Hall GUI and VS Code extension
- Ready for MCP agent integration

## Usage
1. Install requirements:
   ```sh
   pip install -r requirements.txt
   ```
2. Run the daemon:
   ```sh
   python soundstage_daemon.py
   ```
3. Use the HTTP API to control and extend the engine.

## Extending
- Add new sound mappings in the config or via `/set-mapping`
- Integrate with MCP agents, Control Hall GUI, or VS Code extension via HTTP API

## Requirements
- Windows 10/11
- Python 3.8+
- `pywin32`, `Flask`, `playsound` or `winsound`, `psutil`

## Cross-References
- [README.md](README.md): SoundStage overview
- [ARCHITECTURE.md](ARCHITECTURE.md): SoundStage architecture
- [INSTALL.md](INSTALL.md): Build and install
- [DEMO.md](DEMO.md): Feature demonstration

## License
MIT
