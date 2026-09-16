# BossGate Agent View Disclosure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Add reversible, hidden-by-default agent profile views without weakening mandatory BossGate encryption.

**Architecture:** Model Gateway persists an agent-level `disclosure_posture` and refreshes the encrypted gate companion after posture changes. AgentForge exposes trusted-channel profile views and posture updates. BossGate packaging remains encrypted and package metadata remains deny-by-default.

**Tech Stack:** Python 3, `unittest`, Flask routes, existing AgentForge service/adapter, Model Gateway profile persistence, BossGate AES-GCM packaging.

---

### Task 1: Persist Disclosure Posture Without Disabling Encryption

**Files:**
- Modify: `tests/test_model_gateway_agent.py`
- Modify: `core/agents/model_gateway_agent.py`

- [x] Add tests proving new agents default to `hidden`, `encrypt_profile=false` maps to `non_hidden` while preserving `bossgate_enabled`, and posture changes refresh an encrypted gate file.
- [x] Run `.\.venv\Scripts\python.exe -m unittest tests.test_model_gateway_agent.ModelGatewayAgentTests.test_create_agent_defaults_to_hidden_disclosure tests.test_model_gateway_agent.ModelGatewayAgentTests.test_create_agent_non_hidden_compatibility_preserves_bossgate_encryption tests.test_model_gateway_agent.ModelGatewayAgentTests.test_set_agent_disclosure_posture_is_reversible -v` and confirm the new assertions fail.
- [x] Normalize `disclosure_posture` to `hidden|non_hidden`, stop coupling `encrypt_profile=false` to `bossgate_enabled=false`, and add `set_agent_disclosure_posture(name, posture)`.
- [x] Refresh the encrypted gate companion before saving a successful posture update.
- [x] Re-run the focused Model Gateway tests and confirm they pass.

### Task 2: Add Trusted AgentForge Profile Views

**Files:**
- Create: `tests/test_agentforge_service.py`
- Modify: `modules/agentforge/service.py`
- Modify: `modules/agentforge/api_adapter.py`

- [x] Add tests for sealed hidden-agent views, approved non-hidden views from authenticated `bossforgeos` and `agentforge_standalone`, sealed unauthenticated views, sealed disabled `bridgebase_alpha` views, and reversible AgentForge posture updates.
- [x] Run `.\.venv\Scripts\python.exe -m unittest tests.test_agentforge_service -v` and confirm the service operations are missing.
- [x] Add enabled trusted viewer channels `bossforgeos` and `agentforge_standalone`, with `bridgebase_alpha` registered but disabled.
- [x] Add `view_agent_profile(name, viewer_id, viewer_channel)` and `set_agent_disclosure_posture(name, posture)` service functions plus adapter forwarding.
- [x] Ensure sealed summaries include only agent name, posture, sealed state, and secure address.
- [x] Re-run `tests.test_agentforge_service` and confirm it passes.

### Task 3: Wire Control Hall Routes And Labels

**Files:**
- Modify: `tests/test_control_hall_model_routes.py`
- Modify: `ui/control_hall.py`

- [x] Add route tests for profile view forwarding and posture update forwarding.
- [x] Run the new route tests and confirm the routes return `404`.
- [x] Add `GET /api/agentforge/agents/<name>/view` and `POST /api/agentforge/agents/<name>/disclosure`.
- [x] Replace misleading `Encrypt profile` UI wording with `Hide proprietary profile details` while preserving the compatibility payload field.
- [x] Re-run `tests.test_control_hall_model_routes` and confirm it passes.

### Task 4: Lock BossGate Package Metadata To None

**Files:**
- Modify: `tests/test_bossgate_agent.py`
- Modify: `core/agents/bossgate_agent.py`

- [x] Add a test proving an explicitly requested visible package profile is reduced to `none`, while the encrypted envelope remains populated for a non-hidden agent.
- [x] Run the new BossGate test and confirm it fails because metadata remains visible.
- [x] Force BossGate package metadata visibility to `none` until a separate explicit package policy is implemented.
- [x] Re-run `tests.test_bossgate_agent` and confirm it passes.

### Task 5: Document And Verify BG-010

**Files:**
- Modify: `docs/bossgate_connector.md`
- Modify: `docs/bossgate_protocol.md`
- Modify: `docs/AgentForge_readme.md`
- Modify: `docs/bossgate_connector_todo.md`

- [x] Document hidden-by-default views, mandatory encryption, trusted viewer channels, reversible AgentForge posture updates, and package metadata remaining `none`.
- [x] Run `.\.venv\Scripts\python.exe -m unittest tests.test_codemage_agent tests.test_bossgate_agent tests.test_bossgate_connector tests.test_model_gateway_agent tests.test_agentforge_service tests.test_control_hall_model_routes -v`.
- [x] Run `git diff --check`.
- [x] Mark `BG-010` complete with the fresh verification command and test count.

