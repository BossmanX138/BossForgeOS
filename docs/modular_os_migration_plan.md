# BossForgeOS Modular OS Migration Plan

## Goal
Turn BossForgeOS into a control-plane OS over Windows where product modules can run standalone and also plug into the orchestrator.

## Core OS (stays in main BossForgeOS)
- `core/rune/*` (bus, protocol, trace, envelopes)
- `core/security/*` (auth/policy/vault/audit controls)
- `core/state/*` (shared state contracts and health)
- `core/orchestrator/*` (module registry, lifecycle, routing)
- `core/utils/bforge.py` (control-plane CLI)
- `launcher/bossforge_launcher.py` (service lifecycle + orchestration)

## Modules (standalone products)
- `modules/agentforge`
- `modules/soundforge`
- `modules/iconforge`
- `modules/runeforge_voice`

Each module includes `manifest.json` declaring:
- standalone entrypoint
- connector command
- health endpoint
- capability list

## Connectors
- `m365_connector` -> `connectors/m365`
- `m365_copilot_connector` -> `connectors/m365_copilot`
- Additional provider adapters grouped by external platform.

## Clients
- `ui/control_hall.py` split into:
  - `clients/control_hall_frontend` (UI)
  - `core-os api` routes (control-plane backend)
- `extension/` -> `clients/vscode_extension`

## Immediate Phase (shipped now)
- Added module manifest schema: `schemas/module_manifest_v1.json`
- Added orchestrator registry loader: `core/orchestrator/module_registry.py`
- Added scaffold manifests for 4 modules
- Added CLI discovery commands:
  - `bforge module list`
  - `bforge module show <module_id>`
  - `bforge module validate`

## Next Phases
1. Add module connector runtime stubs (`main.py`, `connector.py`) for each module.
2. Add orchestrator lifecycle commands (`bforge module start/stop/status`).
3. Extract feature code from core folders into module packages with compatibility wrappers.
4. Move connectors into `connectors/` and replace direct imports with adapter interfaces.
5. Split Control Hall monolith and attach module health/capability dashboards.
6. Add end-to-end tests for orchestrator + module federation.

