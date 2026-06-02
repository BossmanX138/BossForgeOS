# BossGate Deny Reason Codes Design

Date: 2026-06-02
Tracker item: BG-012

## Goal

Add explicit machine-readable deny reason codes to every BossGate blocked-operation response without breaking existing callers that rely on human-readable `message`, `reason`, or tuple validator results.

## Compatibility Contract

BossGate dictionary failures keep their current response shape and gain:

```json
{
  "ok": false,
  "reason_code": "permission_required",
  "message": "authorization denied: permission is required: bossgate.package"
}
```

Connector scans that currently use `reason` retain that field:

```json
{
  "ok": false,
  "reason_code": "destination_not_approved",
  "reason": "Destination rejected: transfer is only allowed to approved BossGate targets."
}
```

Tuple validators keep their existing `(ok, reason)` signatures. A shared `reason_code_for_message(reason)` mapper converts validator text into a canonical code when the result crosses a dictionary-response boundary.

## Architecture

`core/connectors/bossgate_connector.py` owns the canonical reason-code catalog and mapper because it is the lowest shared BossGate protocol layer.

`core/security/bossgate_authorization.py` imports catalog constants or the response helper for role-management failures.

`core/agents/bossgate_agent.py` uses the same helper for command failures and maps tuple-validator text before returning install failures.

No exception hierarchy is added. Existing tuple validators, CLI behavior, UI messages, and adapter contracts remain compatible.

## Canonical Codes

### Authorization And Governance

| Code | Meaning |
| --- | --- |
| `auth_context_required` | `operator_id` or `scope_id` is missing. |
| `unknown_agent` | An agent actor has no known profile. |
| `agent_skill_required` | An agent actor lacks the required BossGate skill. |
| `unknown_actor_type` | The caller actor type is unsupported. |
| `unknown_operator` | A human operator has no assigned roles. |
| `permission_required` | A human operator lacks the required permission. |
| `security_admin_required` | A role-management action was attempted without seeded `security_admin`. |
| `invalid_role_name` | A custom role name is malformed. |
| `seeded_role_immutable` | A seeded role edit was attempted. |
| `unknown_permissions` | A custom role references permissions outside the catalog. |
| `user_id_required` | A role assignment omitted its user id. |
| `unknown_roles` | A role assignment references unknown roles. |

### Command Input And Policy

| Code | Meaning |
| --- | --- |
| `target_type_required` | Node target type is missing. |
| `destination_required` | Scan destination or connector base URL is missing. |
| `invalid_transfer_validation_result` | Scan integration returned an invalid result. |
| `agent_name_required` | Package operation omitted the agent name. |
| `agent_not_found` | Package operation references an unknown agent. |
| `agent_bossgate_disabled` | Package operation references an agent with BossGate disabled. |
| `target_system_id_required` | Package operation omitted the destination system id. |
| `travel_initiator_not_allowed` | A non-super gate attempted to initiate travel. |
| `destination_not_approved` | Scan classification or transfer target policy rejected the destination. |
| `scanning_skill_required` | Low-level REST scan was invoked for an agent lacking `bossgate_scanning`. |
| `unknown_command` | BossGate command dispatch received an unsupported command. |

### Package, Resume, And Transport

| Code | Meaning |
| --- | --- |
| `package_file_not_found` | A package path does not exist. |
| `invalid_package_file` | Package JSON cannot be loaded. |
| `package_envelope_required` | A package does not contain an envelope. |
| `resume_manifest_required` | Resume was requested for a package without a chunk manifest. |
| `resume_checkpoint_out_of_range` | Resume checkpoint exceeds the package chunk count. |
| `transport_http_error` | Remote BossGate transport returned an HTTP error. |
| `transport_error` | Remote BossGate transport failed outside an HTTP response. |
| `transfer_failed` | A transfer failed after validation; the nested transport result retains its more specific code. |
| `payload_decryption_failed` | Encrypted payload decryption failed. |

### Protocol Validation

| Code | Meaning |
| --- | --- |
| `envelope_fields_required` | Envelope required fields are missing. |
| `cipher_suite_unsupported` | Envelope cipher suite is unsupported. |
| `payload_hash_mismatch` | Envelope encrypted payload hash does not match. |
| `chunk_manifest_invalid` | Chunk manifest structure is invalid. |
| `chunk_checksum_algorithm_unsupported` | Chunk checksum algorithm is unsupported. |
| `chunk_payload_size_mismatch` | Chunk payload size does not match. |
| `chunk_count_mismatch` | Chunk count does not match. |
| `chunk_metadata_invalid` | Chunk metadata is malformed. |
| `chunk_metadata_mismatch` | Chunk index, offset, or size does not match. |
| `chunk_checksum_mismatch` | Chunk checksum does not match. |
| `signature_mismatch` | Envelope signature validation failed. |
| `expires_at_invalid` | Envelope expiry timestamp cannot be parsed. |
| `envelope_expired` | Envelope has expired. |
| `replay_detected` | Encrypted payload nonce was already consumed. |
| `resume_plan_version_unsupported` | Resume plan version is unsupported. |
| `resume_payload_hash_mismatch` | Resume payload hash does not match. |
| `resume_checkpoint_invalid` | Resume checkpoint cannot be parsed or validated. |
| `resume_plan_mismatch` | A resume-plan field does not match the expected plan. |
| `envelope_validation_failed` | Fallback for an unmapped envelope validator failure. |

## Mapping Rules

`reason_code_for_message(reason)` applies deterministic prefix or substring matching from specific to general.

Examples:

| Human-readable reason | Canonical code |
| --- | --- |
| `replay detected: encrypted payload nonce was already consumed` | `replay_detected` |
| `chunk checksum mismatch at index 1` | `chunk_checksum_mismatch` |
| `resume pending_chunk_indexes mismatch` | `resume_plan_mismatch` |
| `missing fields: signature` | `envelope_fields_required` |

Unknown validator messages map to a caller-supplied fallback such as `envelope_validation_failed`.

## Data Flow

1. A low-level validator produces its existing readable reason.
2. If a dictionary failure is returned directly, the producer adds its canonical `reason_code`.
3. If a tuple-validator failure reaches `BossGateCommandAgent.install_agent`, the agent maps the readable reason and returns both `reason_code` and `message`.
4. If transport fails inside `_send_transfer_package`, it returns a transport-specific code. `transfer_agent` returns `transfer_failed` at its own boundary and preserves the nested transport code as `cause_reason_code`.

## Testing

Add regression tests before production edits:

1. Connector scan denials include `scanning_skill_required`, `destination_required`, and `destination_not_approved`.
2. Mapper returns specific protocol codes for tamper, expiry, replay, chunk, and resume failures.
3. Authorization registry denials include stable governance codes.
4. Command-agent authorization denials include stable codes.
5. Transfer policy, transport, and install-envelope failures expose stable codes.
6. Existing readable messages and tuple-validator signatures remain intact.

## Documentation

Update:

- `docs/bossgate_protocol.md` with the additive wire contract and code taxonomy.
- `docs/bossgate_connector.md` with implementation status and compatibility behavior.
- `docs/bossgate_connector_todo.md` only after fresh regression verification proves BG-012 complete.

