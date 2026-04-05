# BossGate Protocol Draft

## Scope

This document defines a draft protocol shape for BossGate secure transport and connector orchestration.

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

## Metadata Visibility Profile

Visibility is policy-driven.

Allowed metadata levels:

1. `none`
2. `id_card_only`
3. `model_card_only`
4. `id_and_model_card`

Default should be `id_and_model_card` only if explicitly enabled by policy. Otherwise default to `none`.

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
