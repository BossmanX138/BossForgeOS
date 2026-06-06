# BossGate Protocol Draft

## Scope

This document defines a draft protocol shape for BossGate secure transport and connector orchestration.

Execution and completion tracking for protocol implementation is maintained in:

1. [docs/bossgate_connector_todo.md](./bossgate_connector_todo.md)

## Transport Layers

BossGate is modeled as a layered transport:

1. Discovery Layer
2. Capability Negotiation Layer
3. Secure Transfer Layer
4. Runtime Control Layer
5. Telemetry and Audit Layer

## Discovery Layer

Discovery may include:

1. LAN beaconing for compatible systems.
2. Target capability probes for approved hosts.
3. Optional endpoint catalog hydration from OpenAPI/Swagger.

All discovery actions must include:

1. Operator identity
2. Approved scope ID
3. Timestamp
4. Audit correlation ID

Operational note:

1. Control Hall exposes BossGate topology via `GET /api/model/travel/map` and the `BossGate Map` panel for live operator visibility.
2. Control Hall exposes recent transfer movement edges via `GET /api/model/travel/transfers` for operator travel-history tracing.

## Authorization Context

Operator-triggered sensitive commands must provide both:

1. `operator_id`
2. `scope_id`

This requirement is enforced for discovery, scan, package, transfer, install, and key-rotation operations. Missing or blank authorization context is denied before the requested operation begins.

Passive BossGate map refresh is internal read-only telemetry and remains exempt so the beacon map can continue tracking agent and travelable-gate locations.

### Human Roles And Agent Skills

Human-role assignments persist in `bus/state/bossgate_human_roles.json`. Users may hold multiple roles and receive the union of their permissions.

Seeded roles:

1. `viewer`
2. `operator`
3. `security_admin`
4. `commerce_manager`
5. `support_engineer`

Only users assigned the seeded `security_admin` role may create custom roles or assign roles to human users. Custom roles grant permission-driven GUI mechanisms but cannot delegate role-management authority.

Human permissions gate interactive operations:

1. Discovery and scan: `bossgate.discovery.run`
2. Package: `bossgate.package`
3. Transfer: `bossgate.transfer`
4. Install: `bossgate.install`
5. Key rotation: `bossgate.key.rotate`

Agent-originated actions use `actor_type=agent` and require skills:

1. Package and install: `bossgate_coms_officer`
2. Transfer: `bossgate_travel_control`
3. Future remote debug: `bossgate_remote_debug`

## Secure Transfer Envelope

BossGate transfer payload should be wrapped in an encrypted envelope.

Required envelope fields (draft):

1. `envelope_version`
2. `agent_id`
3. `agent_version`
4. `issuer`
5. `target_system_id`
6. `created_at`
7. `expires_at`
8. `cipher_suite`
9. `encrypted_payload`
10. `payload_hash`
11. `signature`
12. `policy_ref`
13. `chunk_manifest` for new envelopes; accepted as optional when validating legacy envelopes

### Chunk Manifest

New envelopes include signed per-chunk checksum metadata:

1. `algorithm` (`SHA-256`)
2. `chunk_size`
3. `chunk_count`
4. `payload_size`
5. `chunks` with `index`, `offset`, `size`, and `sha256`

Validation checks each chunk before signature validation so partial corruption reports the affected chunk index. Legacy envelopes without `chunk_manifest` remain valid when their existing payload hash and signature pass.

### Resume Plans

Interrupted transfers may resume from a verified chunk checkpoint. A resume plan is derived from the signed envelope manifest and includes:

1. `version`
2. `payload_hash`
3. `chunk_count`
4. `completed_chunk_indexes`
5. `pending_chunk_indexes`
6. `next_chunk_index`
7. `complete`

Resume plans must match the envelope payload hash and manifest chunk count. Out-of-range checkpoints are denied. Legacy packages without `chunk_manifest` may still transfer from checkpoint zero, but cannot request resumed chunk transport.

### Replay Protection

Install validation derives a replay token from the encrypted AES-GCM payload nonce after integrity, signature, and expiry checks pass. Consumed tokens are persisted locally and reused across BossGate worker restarts.

1. First valid install consumes the replay token.
2. Reuse of the same encrypted payload nonce is denied, even if a new envelope changes other metadata.
3. Failed key candidates and failed payload decryption do not consume tokens.
4. Legacy payload shapes fall back to an encrypted-payload token so duplicate install attempts remain detectable.

### Negative Validation Coverage

Automated BossGate protocol tests cover:

1. Whole-payload tampering
2. Envelope expiry
3. AES payload decryption with the wrong key
4. Envelope signature validation with the wrong key
5. Replayed encrypted payload nonce
6. Partial chunk checksum corruption

## Move Semantics Rule

BossGate transfer is defined as **move**, not copy, for live transport operations:

1. After transfer acknowledgement, source-side agent profile traces must be retired.
2. Transfer artifacts containing agent payload should be securely removed locally after successful handoff.
3. Audit records of transfer metadata are retained, but not full decrypted payload copies.

## Initiation Authority Rule

1. Any validated gate may be a travel target.
2. Travel initiation is restricted to super-gate nodes only:
   - `bridgebase_alpha`
   - `ass` (Anvil Secured Shuttle)
   - `bossforgeos`
3. Non-super gates (`bossgate_connector` class nodes) must reject initiation requests.

## Agent Gate Identity Rule

1. Every BossGate-enabled agent must carry a secure 7-word gate identifier.
2. That identifier is included in package identity metadata and follows the agent across travel and return.

## Metadata Visibility Profile

Visibility is policy-driven.

Allowed metadata levels:

1. `none`
2. `id_card_only`
3. `model_card_only`
4. `id_and_model_card`

Default should be `id_and_model_card` only if explicitly enabled by policy. Otherwise default to `none`.

### AgentForge View Disclosure Posture

Agent-level disclosure posture controls profile views only:

1. New agents default to `hidden`.
2. `hidden` agents return a sealed summary even to trusted tools.
3. `non_hidden` agents may render approved profile details only to authenticated `bossforgeos` and `agentforge_standalone` viewers.
4. `bridgebase_alpha` is a configurable viewer channel but remains disabled by default.
5. AgentForge may switch an existing agent between `hidden` and `non_hidden`.
6. A posture update affects future views of that agent only.
7. Gate companion files and travel packages remain encrypted for both postures.
8. Package metadata remains `none` until a separate package disclosure policy explicitly permits broader metadata.

## Agent ID Card (Draft)

Suggested fields:

1. `agent_id`
2. `agent_name`
3. `publisher`
4. `build_fingerprint`
5. `capabilities_summary`
6. `license_tier`
7. `support_contact`

## Model Card Snapshot (Draft)

Suggested fields:

1. `model_family`
2. `runtime_requirements`
3. `safety_constraints`
4. `known_limits`
5. `compliance_flags`

## Runtime Control and Remote Debug

Remote debug/control channels must enforce:

1. Mutual authentication
2. Time-bound session tokens
3. Role-based command scopes
4. Full session transcript logging
5. Emergency revoke/kill switch

## Usage Tracking and Commerce

Usage telemetry should support rental/sale operations.

Suggested events:

1. `agent_installed`
2. `agent_activated`
3. `agent_invoked`
4. `agent_usage_checkpoint`
5. `agent_license_validated`
6. `agent_license_revoked`
7. `agent_transfer_completed`

## Connector Generation Pipeline

Connector synthesis should follow this flow:

1. Discover target capabilities in approved scope.
2. Build interface map from documented endpoints/ports/protocol features.
3. Generate connector skeleton with least-privilege defaults.
4. Require explicit approval before enabling write/destructive operations.
5. Register connector with audit identity and policy binding.

## Compliance Constraints

BossGate operations must remain:

1. Authorized
2. Auditable
3. Policy-bound
4. Revocable

Unauthorized scanning, access, or data extraction is out-of-scope by design.

## Private Model Payload Contract

The agent capsule model vault references a verified per-agent private-model
package containing encrypted chunk files, an encrypted manifest, and a sparse
attestation. Package ownership must match the runner and capsule agent ID.
BossGate transport may resume and verify these ciphertext artifacts, but may
not rename the agent, rebind the package to a sibling identity, or replace the
package with shared destination weights.
