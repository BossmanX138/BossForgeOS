# Runeforge OS Edition - WindowsWorld Agent Scripts

This workspace contains modular Python scripts for automating and controlling major Windows functions. Each script is self-contained and focused on a specific automation category.

## Table of Contents

- [Script Categories](#script-categories)
- [Safety](#safety)
- [Usage](#usage)

## Script Categories

- **app_control.py**: Open, close, and list running applications.
- **file_management.py**: Create, delete, move, copy, rename files, and list directories.
- **window_management.py**: Move, resize, minimize, maximize, and close windows.
- **network_tools.py**: Get IP, check connectivity, and list Wi-Fi networks.
- **user_session.py**: Lock, log off, shutdown, restart, and sleep.
- **clipboard_tools.py**: Get and set clipboard text.
- **screenshot_tools.py**: Capture and save screenshots.
- **system_info.py**: Display OS, CPU, RAM, and disk info.
- **process_management.py**: List, kill, and start processes.
- **registry_tools.py**: Read and set Windows registry values.
- **powershell_tools.py**: Run arbitrary PowerShell commands.
- **command_execution.py**: Run arbitrary shell commands.
- **high_risk_action.py**: Utility for requiring command-code confirmation for dangerous actions.
- **command_code.txt**: Stores your system-wide command code for high-risk actions.

## Safety

High-risk actions (file deletion, move/copy, volume, dictation, and more) require command-code confirmation. Store your code in `command_code.txt` and use `high_risk_action.py` to enforce confirmation in new scripts.

## Usage

Each script can be run directly or imported as a module. Use `python scriptname.py --help` for usage instructions where applicable.

This suite is designed for modular, safe, and comprehensive Windows automation.
