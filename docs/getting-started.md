# Getting Started

## Prerequisites

- Python 3.11+
- Optional: Docker Desktop for prune actions

## Install

1. Install dependencies:
   - pip install -r requirements.txt

## Launch Services

1. Start daemon loop:
   - python -m core.hearth_tender_daemon --interval 30 --warn-threshold 80
2. Start Control Hall API:
   - python -m ui.control_hall
3. Open Control Hall in browser:
   - <http://127.0.0.1:5005>

## Unified Launcher

1. Start everything (daemon + Control Hall):
   - start_bossforge.cmd
2. Or launch directly in Python:
   - python -m launcher.bossforge_launcher
3. Optional modes:
   - python -m launcher.bossforge_launcher --daemon-only
   - python -m launcher.bossforge_launcher --hall-only

Archivist starts with the unified launcher and listens for archivist-targeted commands.

## Onboarding: Connectors & Voice Profiles

### GitHub Connector
- **Location:** `core/github_connector.py`
- **Purpose:** Secure integration with GitHub API for agent workflows (issue creation, PR listing, repo status).
- **Setup:**
   - Store your GitHub token securely using the Security Sentinel vault:
      - `python -m core.bforge security secret-set github_token <YOUR_TOKEN>`
   - Use bus commands (`github_create_issue`, `github_list_prs`, `github_repo_status`) or import the connector in your agent code.

### Hugging Face Connector
- **Location:** `core/huggingface_connector.py`
- **Purpose:** Secure integration with Hugging Face API for agent workflows (model search, listing, download).
- **Setup:**
   - Store your Hugging Face token securely using the Security Sentinel vault:
      - `python -m core.bforge security secret-set hf_token <YOUR_TOKEN>`
   - Use bus commands (`hf_search_models`, `hf_list_models`, `hf_download_model`) or import the connector in your agent code.

### Voice-Layer Profile Contract
- **Location:** `voices/voice_profile.schema.json`
- **Purpose:** Canonical JSON schema for onboarding and validating agent voice profiles.
- **Usage:**
   - Reference this schema when creating new voice profiles for agents.
   - Validate profiles using standard JSON schema tools.
   - Example profiles: `voices/codemage/profile.json`, `voices/runeforge/profile.json`

## Build a Windows EXE

1. Build executable launcher:
   - powershell -ExecutionPolicy Bypass -File .\build_launcher_exe.ps1
2. Run executable:
   - .\dist\BossForgeLauncher.exe

## Package a Versioned Release

1. Build and package a release bundle:
   - powershell -ExecutionPolicy Bypass -File .\package_release.ps1 -Version 0.1.0
2. Find release artifact:
   - .\releases\v0.1.0\BossForgeLauncher-v0.1.0.exe
3. Desktop shortcut created:
   - BossForge Launcher.lnk

## Use CLI

- python -m core.bforge status
- python -m core.bforge tail --limit 20
- python -m core.bforge os snapshot
- python -m core.bforge os daemon status-ping
- python -m core.bforge agent hearth full_prune
- python -m core.bforge shell
- python -m core.bforge ritual record morning_clean
- python -m core.bforge ritual play morning_clean
- python -m core.bforge ritual list
- python -m core.bforge agent archivist archive_logs
- python -m core.bforge agent archivist summarize_events --args "{\"limit\":100}"
- python -m core.bforge agent archivist snapshot_state
- python -m core.bforge summon archivist
- python -m core.bforge summon archivist --path "D:/Some/Project"
- python -m core.bforge summon archivist --path "D:/Some/Project" --open-ledger
- python -m core.bforge seal preview
- python -m core.bforge seal approve
- python -m core.bforge seal reject --reason "needs review"

### Archivist Database Index

- SQLite index (recommended):
  - python -m core.bforge agent archivist Archive_index_db --args "{\"project_path\":\"D:/Some/Project\",\"db_path\":\"D:/Some/Project/docs/archivist_index.sqlite3\",\"include_patterns\":[\"*.md\",\"*.txt\",\"*.py\"],\"db_type\":\"sqlite\"}"
- Access index (optional):
  - python -m core.bforge agent archivist Archive_index_db --args "{\"project_path\":\"D:/Some/Project\",\"db_path\":\"D:/Some/Project/docs/archivist_index.accdb\",\"include_patterns\":[\"*.md\",\"*.txt\"],\"db_type\":\"access\"}"

## Right-Click Summon (Windows)

1. Install Explorer context menu entry:
   - powershell -ExecutionPolicy Bypass -File .\install_archivist_context_menu.ps1
2. Right-click a file/folder or folder background and choose Summon Archivist.
3. Remove entry if needed:
   - powershell -ExecutionPolicy Bypass -File .\uninstall_archivist_context_menu.ps1

## Control Hall API

- GET /api/status
- GET /api/events?limit=40
- POST /api/command

## Verify Bus Activity

Inspect the local bus folder:

- %USERPROFILE%\\BossCrafts\\bus\\events
- %USERPROFILE%\\BossCrafts\\bus\\commands
- %USERPROFILE%\\BossCrafts\\bus\\state

## Common Flow

1. Run daemon.
2. Issue a command from CLI or POST /api/command.
3. Observe emitted event result in events folder or bforge tail.
