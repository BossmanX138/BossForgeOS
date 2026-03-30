# BossForgeOS

BossForgeOS is a local command-and-control layer for orchestrating agents through a Rune Bus, daemon services, and a Control Hall interface.

## Table of Contents

- [Implemented v1 Foundation](#implemented-v1-foundation)
- [Project Layout](#project-layout)
- [Quick Start](#quick-start)
- [Unified Launcher](#unified-launcher)
- [Global bforge CLI](#global-bforge-cli)
- [Test Sentinel Agent](#test-sentinel-agent)
- [Internal vLLM (Runeforge Core)](#internal-vllm-runeforge-core)
- [Archivist Agent](#archivist-agent)
- [Windows Context Menus](#windows-context-menus)
- [Model Gateway Agent (Ollama, vLLM, LM Studio)](#model-gateway-agent-ollama-vllm-lm-studio)
- [CodeMage Model Backing (vLLM)](#codemage-model-backing-vllm)
- [Security Sentinel Agent](#security-sentinel-agent)
- [Runeforge Voice Commands](#runeforge-voice-commands)
- [Archivist File Index Database](#archivist-file-index-database)
- [CLI Plugin System](#cli-plugin-system)
- [Build Windows EXE](#build-windows-exe)
- [Package Release Bundle](#package-release-bundle)
- [Bus Root](#bus-root)
- [Next Steps](#next-steps)

## Implemented v1 Foundation

- File-based Rune Bus for commands, events, and state snapshots.
- Hearth-Tender daemon loop with command polling and health events.
- BossForge CLI (`bforge`) with status, tail, shell mode, ritual record/play/list, agent command dispatch, and OS daemon commands.
- Control Hall dashboard and API using Flask.
- OS snapshot module for disk, Docker, and WSL VHD checks.
- Integrated Archivist agent service for log archiving, event summaries, and state snapshots.
- Integrated Model Gateway service to bridge local LLM runtimes (Ollama, vLLM, LM Studio) through the Rune Bus.

## Project Layout

- `core/`: bus, daemon, CLI.
- `modules/`: system modules and snapshots.
- `ui/`: Control Hall server.
- `docs/`: architecture and runbook.
- `tests/`: unit tests.

## Quick Start

1. Install dependencies.
   - `pip install -r requirements.txt`
2. Run the daemon.
   - `python -m core.hearth_tender_daemon`
3. Run the Control Hall.
   - `python -m ui.control_hall`
4. Use the CLI.
   - `python -m core.bforge status`
   - `python -m core.bforge os snapshot`
   - `python -m core.bforge agent hearth light_prune`
   - `python -m core.bforge shell`
   - `python -m core.bforge ritual list`
5. Open Control Hall dashboard.
   - <http://127.0.0.1:5005>

## Unified Launcher

- Standard launch:
  - `start_bossforge.cmd`
- Internal vLLM launch (Windows runtime contract):
  - `start_bossforge_internal_vllm.cmd`
- Internal vLLM launch via WSL:
  - `start_bossforge_internal_vllm_wsl.cmd`
- Python entrypoint:
  - `python -m launcher.bossforge_launcher`
- Optional modes:
  - `python -m launcher.bossforge_launcher --daemon-only`
  - `python -m launcher.bossforge_launcher --hall-only`

## Global bforge CLI

- Install global shims:
  - `powershell -ExecutionPolicy Bypass -File .\install_bforge_cli.ps1`
  - `install_bforge_cli.cmd`
- Verify:
  - `bforge status`
  - `bforge os snapshot`
- Uninstall global shims:
  - `powershell -ExecutionPolicy Bypass -File .\uninstall_bforge_cli.ps1`
  - `uninstall_bforge_cli.cmd`

## Test Sentinel Agent

`test_sentinel` is a dedicated daemon for test hygiene and lightweight metrics. It does not replace full CI, but it keeps a local pulse on test debt and basic suite health.

- Polls on a slower cadence (default 45s) to avoid noisy overhead.
- Accepts direct bus commands for scanning debt and running suite metrics.
- Complements Archivist by owning test-focused analysis, while Archivist keeps project-wide backlog governance.

Common commands:

- `bforge agent test_sentinel status_ping`
- `bforge agent test_sentinel scan_test_debt`
- `bforge agent test_sentinel run_test_suite`
- `bforge agent test_sentinel collect_test_metrics`

## Internal vLLM (Runeforge Core)

- BossForge launcher can boot a closed internal vLLM endpoint for Runeforge routing.
- Default model path: `.models/runeforge_core-7b`
- Default served model name: `runeforge_Core-7b`
- Default endpoint: `http://127.0.0.1:8011/v1/chat/completions`
- This endpoint is auto-wired to `runeforge_profile.json` (`llm_router`) at startup when available.

Launcher flags:

- `--no-internal-vllm`
- `--internal-vllm-model`
- `--internal-vllm-model-name`
- `--internal-vllm-host`
- `--internal-vllm-port`
- `--internal-vllm-python`
- `--internal-vllm-wsl`
- `--internal-vllm-wsl-distro`
- `--internal-vllm-wsl-python`
- `--internal-vllm-wsl-model-path`

Packaging notes:

- If your main BossForge runtime does not have a compatible `vllm` install, bundle a dedicated runtime and pass its interpreter using `--internal-vllm-python`.
- Use Python `3.11` or `3.12` for the dedicated runtime bootstrap (`3.14` is not supported).
- On Windows, a successful `pip install vllm` can still fail at startup when native extension `vllm._C` is missing. In that case, run vLLM from Linux/WSL and point BossForge to that runtime/interpreter.
- WSL run command: `start_bossforge_internal_vllm_wsl.cmd`
- Dedicated runtime contract details: `docs/internal_vllm_runtime.md`
- Runtime bootstrap scripts:
  - `setup_vllm_runtime.cmd`
  - `setup_vllm_runtime.ps1`

## Archivist Agent

- Runs automatically under the unified launcher.
- Performs full documentation stewardship outside VS Code via `on_invoke`.
- Scans onboarded projects and initializes/updates markdown governance docs.
- Automatically stewards project-owned README files by refreshing a clickable Table of Contents (skips third-party/runtime/vendor trees).
- Writes daily ledger entries and delegation notes for unfinished TODOs.
- Emits `awaiting_seal` event instead of auto-committing.

Supported bus commands:

- `on_invoke`
- `run_daily`
- `add_project`
- `preview_seal`
- `approve_seal`
- `reject_seal`
- `archive_logs`
- `summarize_events`
- `snapshot_state`
- `status_ping`

Command examples:

- `python -m core.bforge summon archivist`
- `python -m core.bforge summon archivist --path "D:/Some/Repo"`
- `python -m core.bforge summon archivist --path "D:/Some/Repo" --open-ledger`
- `python -m core.bforge summon archivist --path "D:/Some/Repo" --no-notify`
- `python -m core.bforge agent archivist on_invoke`
- `python -m core.bforge agent archivist preview_seal`
- `python -m core.bforge agent archivist approve_seal`
- `python -m core.bforge agent archivist reject_seal --args "{\"reason\":\"needs review\"}"`
- `python -m core.bforge seal preview`
- `python -m core.bforge seal approve`
- `python -m core.bforge seal reject --reason "needs review"`
- `python -m core.bforge agent archivist add_project --args "{\"path\":\"D:/Path/Project\"}"`
- `python -m core.bforge agent archivist archive_logs`
- `python -m core.bforge agent archivist summarize_events --args "{\"limit\":100}"`
- `python -m core.bforge agent archivist snapshot_state`

Control Hall includes an Archivist Seal Queue panel with preview, approve, and reject actions.

## Windows Context Menus

### Summon Archivist

- Install right-click entry for files/folders/background:
  - `powershell -ExecutionPolicy Bypass -File .\install_archivist_context_menu.ps1`
- Uninstall right-click entry:
  - `powershell -ExecutionPolicy Bypass -File .\uninstall_archivist_context_menu.ps1`
- Runtime handler script:
  - `summon_archivist.cmd`
- Folder right-click behavior:
  - Attempts `git init` and `git add -A` before onboarding the folder to Archivist stewardship.
  - If Git is unavailable, Archivist still onboards and runs stewardship, and prints a bootstrap warning.

### Assign Agent To File/Folder

- Install right-click Assign Agent submenu:
  - `powershell -ExecutionPolicy Bypass -File .\install_agent_assign_context_menu.ps1`
- Uninstall right-click Assign Agent submenu:
  - `powershell -ExecutionPolicy Bypass -File .\uninstall_agent_assign_context_menu.ps1`
- Runtime handler script:
  - `assign_agent_context.cmd`
- Supported assignment targets:
  - Archivist
  - CodeMage
  - Runeforge
  - Devlot
  - Model Gateway
- CLI assignment commands:
  - `python -m core.bforge assign set "D:/Some/Path/file.py" --agent codemage`
  - `python -m core.bforge assign list`
  - `python -m core.bforge assign remove "D:/Some/Path/file.py"`

## Model Gateway Agent (Ollama, vLLM, LM Studio)

- Runs automatically under the unified launcher as `model_gateway`.
- Default endpoint config is written to bus state as `model_endpoints.json`.
- Agent profiles are JSON-based and stored in `model_agents.json`.
- MCP server registry is JSON-based and stored in `mcp_servers.json`.
- JSON is the runtime source of truth for reliability and easy programmatic updates.

Supported bus commands:

- `status_ping`
- `list_endpoints`
- `list_agents`
- `create_agent`
- `delete_agent`
- `run_agent`
- `list_servers`
- `serve_model`
- `stop_model_server`
- `stop_all_model_servers`
- `list_mcp_servers`
- `set_mcp_server`
- `remove_mcp_server`
- `export_config`
- `import_config`
- `set_endpoint`
- `remove_endpoint`
- `invoke`
- `refactor_code`

Queue commands from CLI:

- `python -m core.bforge model list`
- `python -m core.bforge model invoke "Summarize this repository architecture" --endpoint ollama`
- `python -m core.bforge model refactor --endpoint lmstudio --language python --code-file core/bforge.py --instructions "extract repeated logic"`
- `python -m core.bforge model set-endpoint mistral --provider openai_compatible --url %OPENAI_ENDPOINT_URL% --model mistral-7b-instruct`
- `python -m core.bforge model remove-endpoint mistral`
- `python -m core.bforge model agent-create refactorer --endpoint ollama --system "You are a senior refactor agent"`
- `python -m core.bforge model agent-create toolsmith --endpoint ollama --system "Use tools when useful" --tools filesystem,github`
- `python -m core.bforge model agent-run refactorer "Refactor this code for readability"`
- `python -m core.bforge model agent-run refactorer "Use this task" --endpoint lmstudio`
- `python -m core.bforge model agents`
- `python -m core.bforge model agent-delete refactorer`
- `python -m core.bforge model mcp-set filesystem --command npx --args-csv "-y,@modelcontextprotocol/server-filesystem,."`
- `python -m core.bforge model mcp-list`
- `python -m core.bforge model mcp-remove filesystem`
- `python -m core.bforge model export D:/BossCrafts/model_config.json`
- `python -m core.bforge model export D:/BossCrafts/model_config.yaml --format yaml`
- `python -m core.bforge model import D:/BossCrafts/model_config.json`
- `python -m core.bforge model import D:/BossCrafts/model_config.yaml --merge`
- `python -m core.bforge model serve ollama --host 127.0.0.1 --port 11434`
- `python -m core.bforge model serve vllm --model Qwen/Qwen2.5-7B-Instruct --host 127.0.0.1 --port 8000`
- `python -m core.bforge model servers`
- `python -m core.bforge model stop vllm`
- `python -m core.bforge model stop-all`

Additional notes:

- LM Studio endpoints are supported, but LM Studio server startup is managed by LM Studio itself.
- Control Hall includes a `Model Chat` panel that reads endpoints from `model_endpoints.json`.
- OS snapshot coverage includes disk pressure, CPU/RAM/swap, GPU VRAM (when `nvidia-smi` is available), and process load accounting.
- Direct generic dispatch example:
  - `python -m core.bforge agent model_gateway invoke --args "{\"endpoint\":\"ollama\",\"prompt\":\"Refactor this function...\"}"`

## CodeMage Model Backing (vLLM)

- CodeMage uses an OpenAI-compatible inference backend during `execute_work_packet`.
- Default backend: `http://127.0.0.1:8000/v1/chat/completions`

Commands:

- Configure backend:
  - `python -m core.bforge agent codemage set_model_backend --args "{\"endpoint\":\"vllm\",\"provider\":\"openai_compatible\",\"url\":\"http://127.0.0.1:8000/v1/chat/completions\",\"model\":\"Qwen/Qwen2.5-7B-Instruct\",\"timeout_seconds\":8}"`
- Start local vLLM server through model gateway:
  - `python -m core.bforge model serve vllm --model Qwen/Qwen2.5-7B-Instruct --host 127.0.0.1 --port 8000`
- Validate CodeMage binding:
  - `python -m core.bforge agent codemage status_ping`

## Security Sentinel Agent

- Runs automatically under the unified launcher as `security_sentinel`.
- Provides:
  - Workspace secret leak scanning.
  - Encrypted local secret vault storage (Windows DPAPI).
  - OAuth token payload storage/retrieval.
  - Policy allow/check controls for agent actions.

Security commands:

- `python -m core.bforge security scan --path "D:/Some/Repo"`
- `python -m core.bforge security secrets-list`
- `python -m core.bforge security secret-set openai_api_key sk-xxxx`
- `python -m core.bforge security secret-get openai_api_key`
- `python -m core.bforge security secret-get openai_api_key --reveal`
- `python -m core.bforge security secret-delete openai_api_key`
- `python -m core.bforge security oauth-set github ghp_xxx --refresh-token rfr_xxx --expires-at "2026-03-10T20:00:00Z"`
- `python -m core.bforge security oauth-get github`
- `python -m core.bforge security policy-set codemage --actions scan_workspace,get_secret`
- `python -m core.bforge security policy-check codemage scan_workspace`

## Runeforge Voice Commands

- Runeforge supports voice-first routing through `Runeforge OS Edition/audio_dictation.py`.
- Computer-control voice commands must begin with the Runeforge callout moniker.
  - Primary: `Runeforge`
  - Shorthand: `runforge`
- Agent-name monikers are supported only for task assignment/delegation.
  - Example: `codemage refactor auth retry logic and add tests`
  - This path dispatches a `work_item` to the target agent and never executes direct OS actions.
- Direct agent wake commands are enabled. Saying an agent name triggers `status_ping` and a wake response event.
- User-defined agent aliases are supported.
- Runeforge includes an internal LLM intent router after direct alias/wake matching and before fallback parser rules.
- LLM router is suggestion-only. Command processor, command-code, leases, and lock checks remain execution authority.
- Continuous voice daemon starts with unified launcher by default.

Voice control phrases:

- `Runeforge mute listening`
- `Runeforge unmute listening`
- `Runeforge stop listening`

Bus commands exposed by Runeforge:

- `voice_command` with args `{"text":"lock file \"C:/AgentSandbox/Downloads/tool.zip\"","command_code":"YOUR_CODE"}`
- `voice_listen` with optional args `{"command_code":"YOUR_CODE"}`

Example CLI invocations:

- `python -m core.bforge agent runeforge voice_command --args "{\"text\":\"Runeforge lock file \\\"C:/AgentSandbox/Downloads/tool.zip\\\"\",\"command_code\":\"123456\"}"`
- `python -m core.bforge agent runeforge voice_listen --args "{\"command_code\":\"123456\"}"`
- `python -m core.bforge agent runeforge voice_command --args "{\"text\":\"Runeforge codemage\"}"`
- `python -m core.bforge agent runeforge voice_command --args "{\"text\":\"Runeforge register voice alias emberforge to agent custom_agent\"}"`
- `python -m core.bforge agent runeforge voice_command --args "{\"text\":\"Runeforge emberforge talk to me\"}"`
- `python -m core.bforge agent runeforge voice_command --args "{\"text\":\"Runeforge open steam\"}"`
- `python -m core.bforge agent runeforge voice_command --args "{\"text\":\"Runeforge play Metallica Black Album\"}"`
- `python -m core.bforge agent runeforge voice_command --args "{\"text\":\"codemage harden login rate limits and report findings\"}"`

Runeforge LLM router config is stored in `bus/state/runeforge_profile.json` under `llm_router`:

- `enabled`
- `provider`
- `url`
- `model`
- `api_key_env`
- `timeout_seconds`
- `temperature`
- `max_tokens`

Launcher options:

- `python -m launcher.bossforge_launcher --no-voice-daemon`
- `python -m launcher.bossforge_launcher --voice-interval 0.75`

## Archivist File Index Database

- Index selected project files into a database via Archivist:
  - `python -m core.bforge agent archivist Archive_index_db --args "{\"project_path\":\"D:/Some/Repo\",\"db_path\":\"D:/Some/Repo/docs/archivist_index.sqlite3\",\"include_patterns\":[\"*.md\",\"*.txt\",\"*.py\"],\"db_type\":\"sqlite\"}"`
- Backward-compatible alias:
  - `python -m core.bforge agent archivist index_files_db --args "{\"project_path\":\"D:/Some/Repo\",\"db_path\":\"D:/Some/Repo/docs/archivist_index.sqlite3\",\"include_patterns\":[\"*.md\",\"*.txt\",\"*.py\"],\"db_type\":\"sqlite\"}"`
- Access support:
  - Set `db_type` to `access` and use `.accdb` path.
  - Requires `pyodbc` and Microsoft Access ODBC driver on Windows.

## CLI Plugin System

- Show plugin load status:
  - `python -m core.bforge plugins`
- Run sample plugin command:
  - `python -m core.bforge forge-echo "forge online"`
- Plugin guide:
  - `docs/plugins.md`

## Build Windows EXE

- Build one-file launcher executable:
  - `powershell -ExecutionPolicy Bypass -File .\build_launcher_exe.ps1`
- Output path:
  - `dist\\BossForgeLauncher.exe`

## Package Release Bundle

- Create versioned release package and desktop shortcut:
  - `powershell -ExecutionPolicy Bypass -File .\package_release.ps1 -Version 0.1.0`
- Release output folder:
  - `releases\\v0.1.0`
- Packaged executable name:
  - `BossForgeLauncher-v0.1.0.exe`

## Bus Root

- Default root: `%USERPROFILE%\\BossCrafts`
- Override by setting `BOSSFORGE_ROOT`

## Next Steps

- Add a full Control Hall web page UI layer.
- Add plugin-loading for CLI extensions.
- Add agent-side consumers for Archivist, CodeMage, Runeforge, and Devlot.
