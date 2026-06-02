# BossGate Human Role And GUI Authorization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Gate sensitive BossGate actions by human roles or agent skills and expose permission-driven Control Hall tools for assigned human responsibilities.

**Architecture:** Add a focused `core/security/bossgate_authorization.py` registry and evaluator. BossGate delegates sensitive-action checks to it. Control Hall exposes role-management and capability APIs, then uses effective permissions to reveal responsibility-specific workspaces.

**Tech Stack:** Python 3, JSON state, `unittest`, Flask routes, existing Rune Bus state directory, existing Control Hall HTML/JavaScript.

---

### Task 1: Build The Human Role Registry

**Files:**
- Create: `tests/test_bossgate_authorization.py`
- Create: `core/security/bossgate_authorization.py`

- [x] Add failing tests for bootstrap owner, seeded roles, multi-role permission union, security-admin-only role creation and assignment, invalid permissions, and GUI capability metadata.
- [x] Run `.\.venv\Scripts\python.exe -m unittest tests.test_bossgate_authorization -v` and confirm imports fail.
- [x] Implement the persisted registry, seeded role catalog, permission catalog, effective permissions, custom-role editing, assignments, and capability metadata.
- [x] Re-run `tests.test_bossgate_authorization` and confirm it passes.

### Task 2: Enforce BossGate Human Permissions And Agent Skills

**Files:**
- Modify: `tests/test_bossgate_agent.py`
- Modify: `core/agents/bossgate_agent.py`
- Modify: `core/utils/bforge.py`

- [x] Add failing tests for unknown-human denial, operator permission success, viewer package denial, security-admin key rotation, and missing agent-skill denial.
- [x] Run the focused BossGate tests and confirm the new checks fail.
- [x] Add shared authorization evaluation for discovery, scan, package, transfer, install, and key rotation.
- [x] Preserve compatibility by defaulting omitted `actor_type` to `human`.
- [x] Require CLI `--operator-id` and `--scope-id` for package and rotate-key, and add optional `--actor-type`.
- [x] Re-run `tests.test_bossgate_agent` and confirm it passes.

### Task 3: Propagate Authorization Through Compatibility Facades

**Files:**
- Modify: `tests/test_model_gateway_agent.py`
- Modify: `core/agents/model_gateway_agent.py`

- [x] Update wrapper tests to provide authorization context for package and propagate `actor_type`.
- [x] Run focused wrapper tests and confirm missing arguments fail.
- [x] Forward `operator_id`, `scope_id`, and `actor_type` through Model Gateway BossGate wrappers and command aliases.
- [x] Re-run `tests.test_model_gateway_agent` and confirm it passes.

### Task 4: Add Control Hall Capability And Role APIs

**Files:**
- Modify: `tests/test_control_hall_model_routes.py`
- Modify: `ui/control_hall.py`

- [x] Add route tests for current-user capabilities, custom-role creation, and multi-role user assignment.
- [x] Run route tests and confirm new routes return `404`.
- [x] Add role-management API routes backed by the shared authorization registry.
- [x] Add a current-user selector and permission-driven BossGate Access, Commerce, Support, and Security Administration workspaces.
- [x] Mark later license and remote-debug controls as pending without dispatching nonexistent commands.
- [x] Re-run `tests.test_control_hall_model_routes` and confirm it passes.

### Task 5: Document And Verify BG-011

**Files:**
- Modify: `docs/bossgate_connector.md`
- Modify: `docs/bossgate_protocol.md`
- Modify: `docs/AgentForge_readme.md`
- Modify: `docs/bossgate_connector_todo.md`

- [x] Document the persisted registry, seeded roles, custom roles, multi-role union, security-admin-only governance, agent skills, and permission-driven GUI.
- [x] Run `.\.venv\Scripts\python.exe -m unittest tests.test_bossgate_authorization tests.test_codemage_agent tests.test_bossgate_agent tests.test_bossgate_connector tests.test_model_gateway_agent tests.test_agentforge_service tests.test_control_hall_model_routes -v`.
- [x] Run `git diff --check`.
- [x] Mark `BG-011` complete with the fresh verification command and test count.


