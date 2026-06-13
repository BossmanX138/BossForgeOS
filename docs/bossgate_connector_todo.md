# BossGate Connector Completion TODO

Last updated: 2026-06-01
Owner: `codemage` (background implementation owner)

## Completion Rules

1. Only mark an item `[x]` when code is merged locally and at least one relevant automated test passes.
2. Every completed item must include a short evidence note (commit hash or test command) directly under the item.
3. If scope changes, append new items; do not rewrite completed history.

## Phase 0: Spec and Backlog Hygiene

- [ ] (BG-001) Align protocol/connector docs (`bossgate_protocol.md` + `bossgate_connector.md`) with one canonical command and feature matrix.
- [ ] (BG-002) Add protocol version table (`v1-prototype`, `v1-pilot`) and compatibility notes.
- [ ] (BG-003) Add a command-to-test mapping section for all BossGate commands.

## Phase 1: Secure Transfer End-to-End

- [x] (BG-004) Upgrade `bossgate_transfer_agent` from intent logging to real transfer transport.
  evidence: [2026-06-01 09:12:39] .venv\\Scripts\\python.exe -m unittest tests.test_bossgate_agent tests.test_bossgate_connector -v (pass)
- [x] (BG-005) Implement chunked transfer with checksum verification.
  evidence: [2026-06-01 22:47:00] .venv\\Scripts\\python.exe -m unittest tests.test_codemage_agent tests.test_bossgate_agent tests.test_bossgate_connector -v (pass, 37 tests)
- [x] (BG-006) Implement resume support for interrupted transfers.
  evidence: [2026-06-01 22:53:00] .venv\\Scripts\\python.exe -m unittest tests.test_codemage_agent tests.test_bossgate_agent tests.test_bossgate_connector -v (pass, 41 tests)
- [x] (BG-007) Add replay protection checks for envelope/nonce reuse.
  evidence: [2026-06-01 22:57:00] .venv\\Scripts\\python.exe -m unittest tests.test_codemage_agent tests.test_bossgate_agent tests.test_bossgate_connector -v (pass, 43 tests)
- [x] (BG-008) Add negative tests for tamper, expiry, wrong key, replay, and partial chunk corruption.
  evidence: [2026-06-01 23:00:00] .venv\\Scripts\\python.exe -m unittest tests.test_codemage_agent tests.test_bossgate_agent tests.test_bossgate_connector -v (pass, 45 tests)

## Phase 2: Policy and Authorization

- [x] (BG-009) Require operator identity and scope id for discovery, scan, transfer, and install.
  evidence: [2026-06-01 23:35:42] .venv\\Scripts\\python.exe -m unittest tests.test_codemage_agent tests.test_bossgate_agent tests.test_bossgate_connector tests.test_model_gateway_agent tests.test_control_hall_model_routes -v (pass, 81 tests)
- [x] (BG-010) Enforce policy-driven metadata visibility profile defaults (`none` unless explicitly allowed).
  evidence: [2026-06-02 04:47:10] .venv\\Scripts\\python.exe -m unittest tests.test_codemage_agent tests.test_bossgate_agent tests.test_bossgate_connector tests.test_model_gateway_agent tests.test_agentforge_service tests.test_control_hall_model_routes -v (pass, 89 tests)
- [x] (BG-011) Enforce role/skill authorization on package, transfer, install, and remote control actions.
  evidence: [2026-06-02 05:37:37] .venv\\Scripts\\python.exe -m unittest tests.test_bossgate_authorization tests.test_codemage_agent tests.test_bossgate_agent tests.test_bossgate_connector tests.test_model_gateway_agent tests.test_agentforge_service tests.test_control_hall_model_routes -v (pass, 102 tests)
- [x] (BG-012) Add explicit deny reason codes to all blocked operations.
  evidence: [2026-06-12 23:37:41] python -m unittest tests.test_bossgate_agent tests.test_bossgate_connector tests.test_bossgate_authorization tests.test_model_gateway_agent -v (pass, 90 tests)

## Phase 3: Audit and Telemetry

- [x] (BG-013) Emit canonical correlated events for all lifecycle actions.
  evidence: [2026-06-12 23:44:27] python -m unittest tests.test_bossgate_agent.BossGateCommandAgentTests.test_lifecycle_actions_emit_canonical_events_with_correlation_ids -v (pass)
- [x] (BG-014) Add immutable/auditable transfer ledger format with correlation ids.
  evidence: [2026-06-12 23:44:27] python -m unittest tests.test_bossgate_agent.BossGateCommandAgentTests.test_transfer_ledger_records_auditable_correlation_metadata -v (pass)
- [x] (BG-015) Implement `bossgate_usage_report` command with local aggregation.
  evidence: [2026-06-12 23:47:57] python -m unittest tests.test_bossgate_agent tests.test_bossgate_connector tests.test_bossgate_authorization tests.test_model_gateway_agent -v (pass, 93 tests)
- [x] (BG-016) Add telemetry tests for event completeness per flow.
  evidence: [2026-06-12 23:52:09] python -m unittest tests.test_bossgate_agent tests.test_bossgate_connector tests.test_bossgate_authorization tests.test_model_gateway_agent -v (pass, 94 tests)

## Phase 4: Licensing and Commerce MVP

- [x] (BG-017) Implement `bossgate_license_issue`.
  evidence: [2026-06-12 23:55:35] python -m unittest tests.test_bossgate_agent tests.test_bossgate_connector tests.test_bossgate_authorization tests.test_model_gateway_agent -v (pass, 96 tests)
- [x] (BG-018) Implement `bossgate_license_validate`.
  evidence: [2026-06-12 23:55:35] python -m unittest tests.test_bossgate_agent tests.test_bossgate_connector tests.test_bossgate_authorization tests.test_model_gateway_agent -v (pass, 96 tests)
- [x] (BG-019) Enforce license checks during install and activation.
  evidence: [2026-06-13 00:06:02] python -m unittest tests.test_bossgate_agent tests.test_bossgate_connector tests.test_bossgate_authorization tests.test_model_gateway_agent -v (pass, 98 tests)
- [x] (BG-020) Implement revocation checks and denial paths.
  evidence: [2026-06-13 00:24:05] python -m unittest tests.test_bossgate_agent tests.test_bossgate_connector tests.test_bossgate_authorization tests.test_model_gateway_agent -v (pass, 100 tests)
- [x] (BG-021) Emit usage checkpoints for billing hooks.
  evidence: [2026-06-13 00:30:55] python -m unittest tests.test_bossgate_agent tests.test_bossgate_connector tests.test_bossgate_authorization tests.test_model_gateway_agent -v (pass, 101 tests)

## Phase 5: Runtime Control and Remote Debug

- [x] (BG-022) Implement `bossgate_remote_debug_open` with time-bound scoped session tokens.
  evidence: [2026-06-13 00:34:05] python -m unittest tests.test_bossgate_agent tests.test_bossgate_connector tests.test_bossgate_authorization tests.test_model_gateway_agent -v (pass, 102 tests)
- [x] (BG-023) Implement `bossgate_remote_debug_close` and emergency revoke/kill switch.
  evidence: [2026-06-13 01:39:26] python -W error::ResourceWarning -m unittest tests.test_bossgate_agent tests.test_bossgate_connector tests.test_bossgate_authorization tests.test_model_gateway_agent -q (pass, 104 tests)
- [x] (BG-024) Log full remote session transcripts with correlation ids.
  evidence: [2026-06-13 01:42:05] python -W error::ResourceWarning -m unittest tests.test_bossgate_agent tests.test_bossgate_connector tests.test_bossgate_authorization tests.test_model_gateway_agent -q (pass, 104 tests)
- [x] (BG-025) Add tests for token expiry and out-of-scope command rejection.
  evidence: [2026-06-13 01:45:20] python -W error::ResourceWarning -m unittest tests.test_bossgate_agent tests.test_bossgate_connector tests.test_bossgate_authorization tests.test_model_gateway_agent -q (pass, 106 tests)

## Phase 6: Connector Synthesis

- [x] (BG-026) Build interface map from discovery and scan outputs.
  evidence: [2026-06-13 01:49:20] python -W error::ResourceWarning -m unittest tests.test_bossgate_agent tests.test_bossgate_connector tests.test_bossgate_authorization tests.test_model_gateway_agent -q (pass, 108 tests)
- [x] (BG-027) Generate least-privilege connector skeletons for approved targets.
  evidence: [2026-06-13 02:13:41] python -W error::ResourceWarning -m unittest tests.test_bossgate_agent tests.test_bossgate_connector tests.test_bossgate_authorization tests.test_model_gateway_agent -q (pass, 110 tests)
- [x] (BG-028) Require explicit approval for write/destructive connector operations.
  evidence: [2026-06-13 02:16:37] python -W error::ResourceWarning -m unittest tests.test_bossgate_agent tests.test_bossgate_connector tests.test_bossgate_authorization tests.test_model_gateway_agent -q (pass, 112 tests)
- [x] (BG-029) Add one end-to-end generation test for an approved sample target.
  evidence: [2026-06-13 02:17:50] python -W error::ResourceWarning -m unittest tests.test_bossgate_agent tests.test_bossgate_connector tests.test_bossgate_authorization tests.test_model_gateway_agent -q (pass, 113 tests)

## Phase 7: Hardening and Release Readiness

- [ ] (BG-030) Add fuzz tests for malformed envelopes and payloads.
- [ ] (BG-031) Add migration tests for keyring and package format upgrades.
- [ ] (BG-032) Publish operator runbook and rollback steps.
- [ ] (BG-033) Prepare release notes and acceptance checklist.
