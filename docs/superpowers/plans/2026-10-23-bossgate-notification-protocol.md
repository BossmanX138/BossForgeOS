# BossGate Notification Protocol Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the canonical BossGate notification, reply, and command-code approval-assertion protocols used by CBCAA and Grand Archivist.

**Architecture:** BossForgeOS remains the protocol home and reference implementation. Notification and reply envelopes reuse the existing AES-256-GCM payload helpers and HMAC envelope style; CBCAA approval assertions use Ed25519 so Archivist receives only a public verification key. Golden fixtures pin canonical serialization across the three repositories.

**Tech Stack:** Python 3, standard-library JSON/HMAC/hashlib, `cryptography` AESGCM and Ed25519, `unittest`, JSON Schema draft 7.

**Spec:** `D:\BossCrafts\Grand Archivist\docs\superpowers\specs\2026-10-23-archivist-repair-and-bossgate-notifications-design.md`

## Global Constraints

- Schema identifiers are exactly `bosscrafts.bossgate.notification.v1`, `bosscrafts.bossgate.reply.v1`, and `bosscrafts.bossgate.repair-approval.v1`.
- Full notification and reply details are AES-256-GCM encrypted; only the explicitly redacted preview is readable by CBCAA delivery adapters.
- Envelope identity is stable by `message_id`; retries never create a new logical message.
- Approval assertions use Ed25519, expire within 60 seconds, carry a unique nonce, and bind account, device, source gate, repair job, proposal version/digest, and project fingerprint.
- Raw command codes never appear in this protocol.
- Wrong keys, malformed payloads, expiry, binding mismatch, and replay fail closed.
- Existing agent-transfer protocol behavior remains compatible.

## Review Focus

- Mixed-case or non-UTC timestamps must be normalized or rejected consistently; Task 1 pins offset-aware UTC parsing.
- Oversized preview or sealed payload fields must be rejected before network or disk use; Task 1 pins size ceilings.
- A valid signature with the wrong proposal binding must fail; Task 2 pins every binding field.
- Consuming an approval nonce must happen only after full validation succeeds; Task 2 pins invalid-then-valid behavior.
- Golden vectors must survive key order and whitespace changes without signature drift; Task 2 pins canonical JSON across reordered dictionaries.

---

### Task 1: Canonical notification and reply envelopes

**Files:**
- Create: `core/bossgate/__init__.py`
- Create: `core/bossgate/notifications.py`
- Create: `schemas/bossgate_notification_v1.schema.json`
- Create: `schemas/bossgate_reply_v1.schema.json`
- Create: `tests/test_bossgate_notifications.py`
- Modify: `core/connectors/bossgate_connector.py:450-497`

**Interfaces:**
- Consumes: `encrypt_json_payload(payload: dict[str, Any], secret_key: str, key_id: str = "") -> str` and `decrypt_json_payload(encoded_payload: str, secret_key: str | dict[str, str]) -> dict[str, Any]` from `core.connectors.bossgate_connector`.
- Produces: `canonical_json_bytes(payload: Mapping[str, Any]) -> bytes`; `build_notification_envelope(...) -> dict[str, Any]`; `validate_notification_envelope(envelope, secret_keys, replay_tokens=None, at=None) -> tuple[bool, str]`; `decrypt_notification_detail(envelope, secret_keys) -> dict[str, Any]`; `build_reply_envelope(...) -> dict[str, Any]`; `validate_reply_envelope(...) -> tuple[bool, str]`; constants for schema names, severities, and user-facing event types.

- [ ] **Step 1: Write the failing envelope contract tests**

Add tests named `test_notification_round_trip_preserves_redacted_preview_and_sealed_detail`, `test_reply_round_trip_binds_parent_message_and_correlation`, `test_notification_rejects_missing_fields`, `test_notification_rejects_non_utc_or_invalid_timestamp`, and `test_notification_rejects_preview_over_2048_or_sealed_payload_over_1048576_bytes`.

Assert exact schema names, UUID message/correlation IDs, UTC `Z` timestamps, severities in `info|warning|error|critical`, maximum 2,048-character serialized previews, maximum 1 MiB sealed payloads, and that only decryption reveals detailed evidence.

- [ ] **Step 2: Run the focused tests and verify they fail**

Run: `python -m unittest tests.test_bossgate_notifications -v`

Expected: FAIL because `core.bossgate.notifications` does not exist.

- [ ] **Step 3: Expose the existing AES-GCM helpers as the encryption dependency**

Keep the existing function signatures in `core/connectors/bossgate_connector.py`. Add them to `core/bossgate/__init__.py` only through explicit imports; do not duplicate the cryptography implementation.

- [ ] **Step 4: Implement the canonical envelope builders and validators**

In `core/bossgate/notifications.py`, implement:

```python
def canonical_json_bytes(payload: Mapping[str, Any]) -> bytes: ...
def build_notification_envelope(*, event_type: str, severity: str, source_gate: str,
    recipient_account_id: str, preview: dict[str, str], detail: dict[str, Any],
    secret_key: str, key_id: str, correlation_id: str, message_id: str | None = None,
    expires_in_seconds: int = 86400, at: datetime | None = None) -> dict[str, Any]: ...
def validate_notification_envelope(envelope: Mapping[str, Any],
    secret_keys: str | Mapping[str, str], replay_tokens: set[str] | None = None,
    at: datetime | None = None) -> tuple[bool, str]: ...
def decrypt_notification_detail(envelope: Mapping[str, Any],
    secret_keys: str | Mapping[str, str]) -> dict[str, Any]: ...
def build_reply_envelope(*, parent_message_id: str, correlation_id: str,
    source_gate: str, target_gate: str, reply_type: str, detail: dict[str, Any],
    secret_key: str, key_id: str, message_id: str | None = None,
    expires_in_seconds: int = 604800, at: datetime | None = None) -> dict[str, Any]: ...
def validate_reply_envelope(envelope: Mapping[str, Any],
    secret_keys: str | Mapping[str, str], replay_tokens: set[str] | None = None,
    at: datetime | None = None) -> tuple[bool, str]: ...
```

Sign canonical envelope content excluding `signature` with HMAC-SHA256, calculate `payload_hash` over `sealed_payload`, and consume replay tokens only after structure, hash, signature, and expiry all pass.

- [ ] **Step 5: Add JSON Schemas matching the validators**

Require all identity, routing, expiry, preview, sealed-payload, hash, nonce, key ID, and signature fields. Set `additionalProperties: false` at the envelope root and preview object.

- [ ] **Step 6: Run focused and connector regression tests**

Run: `python -W error::ResourceWarning -m unittest tests.test_bossgate_notifications tests.test_bossgate_connector tests.test_protocol_v1 -v`

Expected: PASS.

- [ ] **Step 7: Commit the protocol envelope unit**

```powershell
git add core/bossgate core/connectors/bossgate_connector.py schemas/bossgate_notification_v1.schema.json schemas/bossgate_reply_v1.schema.json tests/test_bossgate_notifications.py
git commit -m "Add BossGate notification and reply envelopes"
```

### Task 2: Command-code approval assertions and golden vectors

**Files:**
- Create: `core/bossgate/repair_approval.py`
- Create: `schemas/bossgate_repair_approval_v1.schema.json`
- Create: `tests/fixtures/bossgate_notification_v1.json`
- Create: `tests/fixtures/bossgate_reply_v1.json`
- Create: `tests/fixtures/bossgate_repair_approval_v1.json`
- Create: `tests/test_bossgate_repair_approval.py`
- Modify: `tests/test_bossgate_notifications.py`

**Interfaces:**
- Consumes: `canonical_json_bytes()` from Task 1.
- Produces: `build_repair_approval_assertion(...) -> dict[str, Any]`; `verify_repair_approval_assertion(assertion, public_keys, expected, consumed_nonces=None, at=None) -> tuple[bool, str]`; three key-order-independent golden fixtures copied unchanged into the CBCAA and Grand Archivist test suites.

- [ ] **Step 1: Write failing assertion tests**

Add `test_assertion_round_trip_binds_every_approval_field`, `test_assertion_expires_after_60_seconds`, `test_assertion_rejects_wrong_public_key`, `test_assertion_rejects_each_wrong_expected_binding`, `test_assertion_rejects_replayed_nonce`, `test_failed_validation_does_not_consume_nonce`, and `test_canonical_signature_survives_dictionary_reordering`.

Use a fixed Ed25519 test key, fixed UTC time, and exact expected binding keys: `account_id`, `device_id`, `source_gate`, `repair_job_id`, `proposal_version`, `proposal_digest`, `project_fingerprint`, and action `approve_repair`.

- [ ] **Step 2: Run the tests and verify they fail**

Run: `python -m unittest tests.test_bossgate_repair_approval -v`

Expected: FAIL because `core.bossgate.repair_approval` does not exist.

- [ ] **Step 3: Implement Ed25519 assertion creation and verification**

```python
def build_repair_approval_assertion(*, binding: Mapping[str, str],
    private_key_pem: str, key_id: str, nonce: str | None = None,
    ttl_seconds: int = 60, at: datetime | None = None) -> dict[str, Any]: ...
def verify_repair_approval_assertion(assertion: Mapping[str, Any],
    public_keys: Mapping[str, str], expected: Mapping[str, str],
    consumed_nonces: set[str] | None = None,
    at: datetime | None = None) -> tuple[bool, str]: ...
```

Clamp `ttl_seconds` to 1–60, encode signatures with Base64, select the public key by `key_id`, compare every expected binding value, and consume the nonce only after all checks pass.

- [ ] **Step 4: Add the approval schema and deterministic golden fixtures**

Generate fixtures from fixed keys/times/nonces. Each fixture includes `canonical_sha256`; tests recalculate it so CBCAA and Archivist can detect schema drift without importing BossForgeOS at runtime.

- [ ] **Step 5: Run all focused protocol tests**

Run: `python -W error::ResourceWarning -m unittest tests.test_bossgate_notifications tests.test_bossgate_repair_approval tests.test_bossgate_connector tests.test_protocol_v1 -v`

Expected: PASS.

- [ ] **Step 6: Commit the approval protocol unit**

```powershell
git add core/bossgate/repair_approval.py schemas/bossgate_repair_approval_v1.schema.json tests/fixtures tests/test_bossgate_notifications.py tests/test_bossgate_repair_approval.py
git commit -m "Add BossGate repair approval assertions"
```

### Task 3: Publish the notification protocol contract

**Files:**
- Modify: `docs/bossgate_protocol.md`
- Modify: `docs/bossgate_connector.md`
- Modify: `docs/bossgate_connector_todo.md`
- Create: `docs/bossgate_notification_protocol.md`

**Interfaces:**
- Consumes: Tasks 1–2 schemas, functions, and golden fixtures.
- Produces: the operator/developer contract CBCAA and capsule implementers follow.

- [ ] **Step 1: Document routing, redaction, replay, and approval boundaries**

Document the three schemas, redacted preview versus sealed detail, acknowledgement/reply correlation, Ed25519 key rotation by `key_id`, 60-second assertions, and the rule that raw command codes never enter BossGate messages.

- [ ] **Step 2: Record the milestone in the canonical tracker**

Add notification-protocol checklist entries to `docs/bossgate_connector_todo.md` with test commands as evidence placeholders; mark them complete only after the commands pass.

- [ ] **Step 3: Run the full BossForgeOS Python suite**

Run: `python -W error::ResourceWarning -W error::SyntaxWarning -m unittest discover -s tests -p "test_*.py" -q`

Expected: `OK` with a nonzero test count.

- [ ] **Step 4: Commit the protocol documentation**

```powershell
git add docs/bossgate_protocol.md docs/bossgate_connector.md docs/bossgate_connector_todo.md docs/bossgate_notification_protocol.md
git commit -m "Document BossGate notification protocol"
```
