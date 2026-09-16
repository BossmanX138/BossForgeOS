# Getting Started

## Prerequisites

- Python 3.11+
- Optional: Docker Desktop for prune actions

## Install

1. Install dependencies:
   - `pip install -r docs/requirements.txt`

## Reproducible Dev Runtime (Windows)

Use this when global `python`/`pip` setup is inconsistent.

1. Create isolated runtime:
   - `C:\Users\%USERNAME%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m venv .runtime\devpy`
2. Upgrade packaging tools:
   - `.runtime\devpy\Scripts\python.exe -m pip install --upgrade pip setuptools wheel`
3. Install minimum runtime/test dependencies:
   - `.runtime\devpy\Scripts\python.exe -m pip install flask werkzeug psutil pyyaml pandas duckdb requests msal oauthlib`
4. Quick import verification:
   - `.runtime\devpy\Scripts\python.exe -c "import flask, werkzeug, psutil, yaml, pandas, duckdb, requests, msal, oauthlib; print('ok')"`

## Verification Commands

1. DataForge module smoke:
   - `.runtime\devpy\Scripts\python.exe -m modules.DataForge.main`
2. Launcher help smoke:
   - `.runtime\devpy\Scripts\python.exe -m launcher.bossforge_launcher --help`
3. Full tests:
   - `.runtime\devpy\Scripts\python.exe -m unittest discover -s tests -p "test_*.py" -q`
4. Strict warning-clean tests:
   - `.runtime\devpy\Scripts\python.exe -W error::ResourceWarning -W error::SyntaxWarning -m unittest discover -s tests -p "test_*.py" -q`

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

## Agent Maker: Core vs Prime

Agent Maker supports two classes of model profiles:

1. `core`: service-first agents that do not require an embedded LLM for their main behavior.
2. `prime`: model-backed agents intended for reasoning/generative workloads.

Both classes can persist relationship memory in the model gateway memory database.

### Agent Interaction Memory (SQLite)

- **Database path:** `bus/state/agent_memory.sqlite3`
- **Tracks:** interactions with users/employers/projects and collaborating agents.
- **Use cases:** continuity, relationship context, historical recall for future runs.

Example API recall:

- `GET /api/model/agents/memory?name=<agent_name>&limit=25`

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

## Launch BossForgeOS

1. Start Control Hall only:
   - .\scripts\start_control_hall.cmd
2. Start the full local orchestrator:
   - .\scripts\start_bossforge.cmd
3. For the intended user-facing flow, launch BossForgeOS from A.S.S. after CBCAA login.

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
