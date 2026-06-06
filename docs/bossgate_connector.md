# BossGate Connector

## Purpose

BossGate is the secure transport and interoperability layer for BossCrafts agents.

Every BossCrafts agent is expected to carry a BossGate capability module that can:

1. Move agents between approved systems and networks.
2. Protect agent payloads through encrypted transport.
3. Expose only approved metadata when transporting or cataloging agents.
4. Support commercial distribution models (rent/sell) with licensing and usage tracking.
5. Enable remote diagnostics and operational telemetry.
6. Discover integration surfaces (endpoints, ports, protocol entry points) and generate connector stubs for approved targets.

## Target Platforms

BossGate-compatible targets include systems equipped with at least one of the following:

1. A.S.S. (Anvil Secured Shuttle)
2. BossForgeOS
3. bridgebase_alpha

Initiation authority rule:

1. Any BossGate endpoint may be a travel target (if validated).
2. Only super gates may initiate travel:
   - bridgebase_alpha
   - A.S.S.
   - BossForgeOS

## Security Model

BossGate operates under deny-by-default security.

1. Agent payloads are encrypted at rest and in transit.
2. Raw agent internals are not disclosed during transfer by default.
3. Optional metadata-only disclosure is allowed via policy:
   - Model Card
   - Agent ID Card
4. Transport, provisioning, and invocation actions must be authorized and auditable.
5. Discovery/scanning is only permitted on explicit user-approved scopes and approved targets.
6. Gate travel is move-only for live transfers: agent state is retired at source after confirmed transfer.
7. Each BossGate-enabled agent carries a secure 7-word gate address; this identity follows the agent across transfers.
8. Each BossGate-enabled agent is persisted with an encrypted gate companion file (`bus/state/agent_gates/<agent>.bossgate`) to protect profile identity and transport metadata from non-authorized inspection.
9. AgentForge disclosure posture controls authenticated profile views only. It never disables encrypted gate files or encrypted BossGate travel packages.

## Distribution and Commerce

BossGate is intended to support controlled distribution workflows:

1. Agent rental
2. Agent sale
3. Metered usage tracking
4. License enforcement and revocation
5. Remote support/debug channels for authorized operator roles

## Connector Synthesis Capability

BossGate can be used to identify integration points on approved software targets and assist agent-specific connector generation.

Supported discovery patterns:

1. OpenAPI/Swagger endpoint discovery
2. Port/service reconnaissance within authorized scope
3. Protocol capability probing for documented interfaces

Important boundary:

1. BossGate does not authorize bypassing security controls.
2. Discovery and connector generation are constrained to legal, authorized, policy-bound targets.

## Current Repository Status (April 2026)

Current implementation status is prototype-level.

1. Prototype location: [core/connectors/bossgate_connector.py](../core/connectors/bossgate_connector.py)
2. Implemented now:
   - LAN beacon broadcast/discovery
   - Basic REST endpoint scanning
   - AES-256-GCM encrypted package payloads (authenticated encryption)
   - Signed transfer envelope primitives (HMAC integrity + expiry)
   - Signed per-chunk SHA-256 manifest verification for transfer envelopes, with legacy envelope compatibility
   - Resume plans for interrupted transfers, bound to the envelope payload hash and chunk manifest
   - Replay protection for encrypted payload nonce reuse, persisted across BossGate worker restarts in `bus/state/bossgate_replay_tokens.json`
   - Negative protocol tests for tamper, expiry, wrong keys, replay, and partial chunk corruption
   - Required `operator_id` and `scope_id` authorization context for operator-triggered discovery, scan, transfer, and install operations
   - Hidden-by-default AgentForge profile views with reversible per-agent `hidden` / `non_hidden` posture
   - Trusted profile viewers: `bossforgeos` and `agentforge_standalone`; `bridgebase_alpha` is registered but disabled by default
   - Package metadata locked to `none` until a separate explicit package disclosure policy is implemented
   - Persisted human-role registry with seeded `viewer`, `operator`, `security_admin`, `commerce_manager`, and `support_engineer` roles
   - Custom human roles and multi-role assignments governed only by seeded `security_admin` users
   - Permission-driven Control Hall BossGate Access, Commerce, Support, and Security Administration mechanisms
   - Agent-origin package/install skill gate (`bossgate_coms_officer`) and transfer skill gate (`bossgate_travel_control`)
   - Keyring-backed key rotation (`active_key_id` + retained prior keys for decrypt)
   - Dedicated BossGate command agent (`core/agents/bossgate_agent.py`)
3. Not yet implemented end-to-end:
   - Encrypted transfer envelopes for full agent packages
   - Expanded package metadata disclosure policies beyond the enforced `none` default
   - Rental/sale license flow and billing integration
   - Agent runtime attestation + full audit stream

## Canonical Completion Tracker

BossGate completion checklist and live status is tracked in:

1. [docs/bossgate_connector_todo.md](./bossgate_connector_todo.md)

## Planned Command Surface (Draft)

Proposed bus-level command families:

1. `bossgate_discover_targets`
2. `bossgate_scan_target`
3. `bossgate_package_agent`
4. `bossgate_transfer_agent`
5. `bossgate_install_agent`
6. `bossgate_license_issue`
7. `bossgate_license_validate`
8. `bossgate_usage_report`
9. `bossgate_remote_debug_open`
10. `bossgate_remote_debug_close`

## Current Command Surface (Implemented Prototype)

These commands are now handled by the BossGate command agent (`target="bossgate"`):

1. `bossgate_discover_targets`
2. `bossgate_scan_target`
3. `bossgate_package_agent`
4. `bossgate_transfer_agent` (dry-run validation or live transfer POST; supports `resume_from_chunk`; live transfer enforces move semantics by retiring source traces)
5. `bossgate_install_agent`
6. `bossgate_rotate_key`
7. `bossgate_set_node_target_type`

## CLI Surface (Implemented)

The `bforge` CLI now includes a dedicated BossGate command group:

1. `bforge bossgate status [--limit N]`
2. `bforge bossgate tail [--limit N]`
3. `bforge bossgate discover [--timeout N] [--assistance-only] --operator-id <id> --scope-id <id> [--actor-type human|agent]`
4. `bforge bossgate scan <destination> --operator-id <id> --scope-id <id> [--actor-type human|agent]`
5. `bforge bossgate package <agent_name> --target-system-id <id> [--visibility-profile ...] [--policy-ref ...] [--secret-key ...] [--output-file ...] --operator-id <id> --scope-id <id> [--actor-type human|agent]`
6. `bforge bossgate transfer <package_file> <destination> [--dry-run|--no-dry-run] [--resume-from-chunk N] --operator-id <id> --scope-id <id> [--actor-type human|agent]`
7. `bforge bossgate install <package_file> [--secret-key ...] --operator-id <id> --scope-id <id> [--actor-type human|agent]`
8. `bforge bossgate rotate-key [--key-id ...] [--secret-key ...] --operator-id <id> --scope-id <id> [--actor-type human|agent]`
9. `bforge agent bossgate bossgate_set_node_target_type --args "{\"target_type\":\"bossforgeos\"}"`
10. `bforge bossgate map [--refresh] [--timeout N]`

## Beacon Map State (Implemented)

BossGate now maintains a live logical map from beacon discovery at:

1. `bus/state/bossgate_map.json`

Map contents include:

1. `gates` (all discovered gate nodes)
2. `travelable_gates` (subset allowed for transfer targets)
3. `agents` (current node/address view of discovered agents)

The BossGate service refreshes this map continuously during runtime and also supports on-demand refresh via the `bossgate_map_snapshot` command.

Passive map refresh is internal read-only telemetry and does not require operator authorization context. Operator-triggered discovery, scan, transfer, and install commands are denied unless both `operator_id` and `scope_id` are provided.

## Control Hall Integration (Implemented)

BossGate map state is now visible in Control Hall via:

1. `BossGate Map` panel (navigation tab)
2. `GET /api/model/travel/map?refresh=<bool>&timeout=<int>`
3. Visual topology graph per gate with travelable highlighting and mapped resident agents
4. Directional transfer edge overlay driven by `GET /api/model/travel/transfers?limit=<int>`

Endpoint behavior:

1. Delegates to model gateway adapter `bossgate_map_snapshot(refresh, timeout)`.
2. Returns BossGate map payload with `gates`, `travelable_gates`, and `agents`.
3. Supports read-only snapshot (`refresh=false`) and on-demand refresh (`refresh=true`).

## CodeMage Patch Proposal Workflow (Implemented)

CodeMage can now draft and verify narrowly scoped BossGate patches through the bus:

1. `bforge agent codemage generate_bossgate_patch_proposal --args "{\"todo_id\":\"BG-005\",\"details\":\"...\"}"`
2. `bforge agent codemage list_bossgate_patch_proposals`
3. `bforge agent codemage apply_bossgate_patch_proposal --args "{\"proposal_id\":\"...\",\"confirm\":true}"`

Safety rules:

1. Generated diffs may touch only BossGate source, tests, and BossGate documentation allowlist paths.
2. Draft proposals are persisted under `bus/state/codemage_patch_proposals/` for review.
3. Apply requires `confirm=true` and a successful `git apply --check`.
4. Focused BossGate tests run after apply; a failed focused suite reverses only the generated patch.
5. CodeMage persists its last consumed Rune Bus command filename in `bus/state/codemage_command_cursor.json`, preventing worker restarts from replaying historical assignments while preserving command JSON files as an audit trail.
6. Proposal requests may provide allowlisted `context_files`, `context_ranges`, `max_context_chars`, and `max_output_tokens` so local model work is split into compact reviewable slices. Each `context_ranges` item uses `file`, `start_line`, and `end_line`.
7. Draft creation runs `git apply --check` before persistence; malformed or stale model output is rejected before it can appear as a review-ready draft.
8. For an explicitly requested single-file context only, CodeMage pins generated diff headers to that allowlisted path and strips a terminal Markdown fence before Git preflight. Multi-file proposals remain strict.
9. Git-preflight failures are quarantined under `bus/state/codemage_patch_rejections/` with the patch and stderr for operator inspection; they are never listed as review-ready drafts.

## Key Management Notes (Prototype)

1. BossGate now stores a local keyring at `bus/state/bossgate_keys.json`.
2. New packages are encrypted with the active key id.
3. Key rotation promotes a new active key while retaining prior keys for package decrypt/install continuity.
4. This is local-file key management for prototype stage; secure external vault integration is still pending.

## Private Model Package Boundary

AgentForge now creates an independently owned encrypted private-model package
for every new LLM-enabled agent. The capsule model vault and runner bootstrap
reference that verified package. BossGate full-capsule travel must carry these
encrypted chunks unchanged as part of the agent and must not substitute a
destination-side shared model. Network transfer, destination mounting, and
source secure retirement remain Stage 6 work.

## Non-Goals

1. Unauthenticated remote execution.
2. Unauthorized network probing.
3. Exfiltration of encrypted agent internals.
4. Circumventing platform or tenant controls.
