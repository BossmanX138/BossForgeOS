# BossGate Notification Protocol v1

This is the operator and implementer contract for the notification, reply, and repair-approval wire formats implemented by `core.bossgate.notifications` and `core.bossgate.repair_approval`. The JSON Schemas under `schemas/` describe the wire shapes; the Python validators also enforce cryptographic, time, size, and replay rules. The golden vectors under `tests/fixtures/` pin representative canonical serialization. This contract describes implemented behavior only.

## Message types and routing

| Type | Schema identifier | Route and correlation fields | Purpose |
| --- | --- | --- | --- |
| Notification | `bosscrafts.bossgate.notification.v1` | `source_gate`, `recipient_account_id`, `message_id`, `correlation_id` | A user-facing event from the listed source gate to an account. |
| Reply | `bosscrafts.bossgate.reply.v1` | `source_gate`, `target_gate`, `parent_message_id`, `message_id`, `correlation_id` | A gate-to-gate response tied to a parent message and its logical correlation. |
| Repair approval assertion | `bosscrafts.bossgate.repair-approval.v1` | `account_id`, `device_id`, `source_gate`, `repair_job_id`, `proposal_version`, `proposal_digest`, `project_fingerprint`, `action` | A short-lived proof that a specific repair proposal was approved. |

Notification event types currently accepted are `repair.approval_requested`, `repair.implementation_started`, `repair.implementation_completed`, `repair.verification_failed`, `repair.needs_decision`, `repair.backup_failed`, and `delivery.recovered`. Severity is one of `info`, `warning`, `error`, or `critical`. A notification and a reply each have a UUID `message_id` and UUID `correlation_id`. Each reply also carries the UUID `parent_message_id`; consumers use it to identify the message being answered. Retries of a logical notification should retain its `message_id`. The protocol does not itself implement a delivery queue or retry scheduler. A gate can represent an acknowledgement or other response with a reply envelope routed by `source_gate` and `target_gate`; `parent_message_id` names the parent message, and `correlation_id` carries the caller-managed conversation correlation. `reply_type` is a required nonempty string whose value is caller-defined; peers must agree on its meaning. This is a wire-format option, not an implemented acknowledgement service. Validation checks the envelope fields and cryptographic/time rules, but does not establish that the parent exists, require the reply correlation ID to equal the parent conversation ID, or maintain matching conversation state; receivers must enforce those application-level relationships.

## Readable preview and sealed detail

A notification exposes only `preview` to systems that need to display a delivery summary. Its exact string fields are `title`, `project_name`, `summary`, and `action`; the canonical compact JSON representation is limited to 2,048 characters. The producer is responsible for redacting the preview. The codec checks its shape and size, but does not infer or perform redaction.

Full notification and reply detail is a JSON object encrypted as AES-256-GCM in `sealed_payload`. The Base64-encoded encrypted blob is limited to 1,048,576 bytes, carries version 1, algorithm `AES-256-GCM`, and must repeat the outer `key_id`. `payload_hash` is SHA-256 over the encoded sealed-payload string. The envelope signature is HMAC-SHA256 over canonical sorted, compact ASCII JSON for every envelope field other than `signature`. An adapter may inspect the notification preview without decrypting detail; it must not treat the preview as the full detail. `decrypt_notification_detail` authenticates and decrypts history, including expired records, and deliberately does not consume a delivery replay token. Delivery acceptance must use `validate_notification_envelope` for time and replay checks.

## Key IDs and rotation

Every notification and reply names its encryption/authentication key with `key_id`. A key mapping is resolved by that exact ID. There is no fallback to another key when the ID is absent or unknown. During rotation, a sender emits using its selected active ID; a receiver retains old ID-to-key entries for the period it must read still-valid or historical messages. Remove an old entry only when policy says those messages no longer need to be authenticated or decrypted. The notification/reply envelope uses symmetric key material for AES-GCM and HMAC; it is separate from the public-key approval assertion below. The code does not manage distribution, storage, or lifecycle of these keys.

Approval assertions instead use Ed25519. The signer loads an Ed25519 private key and includes its `key_id`; a verifier selects the trusted public key from the map by that exact ID. This permits rotation by publishing a new ID/key pair while retaining old public keys for assertions that remain within their acceptance window. Never substitute a key on lookup failure.

## Validation and strict replay handling

In a repair approval assertion, `source_gate` identifies the originating Archivist gate (for example, `archivist-gate`), and `repair_job_id` identifies that gate's repair job. CBCAA is the assertion issuer: it verifies authorization and signs the complete proposal binding. Its issuer role does not replace the originating gate in `source_gate`.

Notification and reply validators reject missing or extra fields, malformed UUIDs, unsupported event/severity values, invalid UTC `Z` timestamps, future-created or expired messages, payload-hash mismatch, signature mismatch, malformed encrypted blobs, wrong keys, invalid decrypted detail, and oversized fields. Expiration is exclusive: `now >= expires_at` is expired. The builder defaults notification lifetime to 24 hours and reply lifetime to seven days; callers may choose a positive integer lifetime.

A receiver that requires replay protection must supply a caller-owned nonce set to `validate_notification_envelope` or `validate_reply_envelope`, persist that set across restarts, and serialize updates so concurrent acceptance cannot consume the same nonce twice. The token is derived from `source_gate` and the envelope `nonce`. The validator adds it only after structure, payload hash, key/signature, sealed payload, and time checks pass. A previously consumed token fails closed. If no set is supplied, validation authenticates and checks time but cannot provide durable one-use delivery semantics. Reading stored history with `decrypt_notification_detail` does not consume a delivery nonce.

Approval verification binds every field in the assertion to the caller-supplied complete expected binding, validates the Ed25519 signature and the `key_id`, rejects future or expired proofs, and accepts only `action: approve_repair`. The assertion lifetime must be greater than zero and no more than 60 seconds; the builder clamps its requested TTL into that interval. For a one-use proof, the verifier must receive a caller-owned `consumed_nonces` set backed by durable state and guard concurrent verification/consumption with a lock or transaction. It consumes the nonce only after all signature, binding, and time checks pass. Omitting that set is verification without replay persistence, not one-use acceptance.

## Approval authority and raw command-code boundary

The assertion proves approval of one exact proposal binding; it does not perform command-code verification or replace the issuer's authorization process. The issuer performs the required authorization (including command-code verification where the surrounding workflow requires it) before creating the assertion. The assertion schema contains no command-code field, and unknown fields are rejected. Raw command codes must never be serialized into a BossGate notification, reply, sealed detail, preview, approval assertion, audit message, or log. Notification/reply builders and validators recursively reject detail object keys that identify command-code material (including punctuation/case variants); this guard is defense in depth, not a substitute for callers keeping the value out of all fields and logs. Never put a code in a value, preview string, identifier, or diagnostic text.

## Reference implementation and evidence

- Envelope builders and validators: `core/bossgate/notifications.py` (`build_notification_envelope`, `validate_notification_envelope`, `decrypt_notification_detail`, `build_reply_envelope`, `validate_reply_envelope`).
- Approval builder and verifier: `core/bossgate/repair_approval.py` (`build_repair_approval_assertion`, `verify_repair_approval_assertion`).
- Schemas: `schemas/bossgate_notification_v1.schema.json`, `schemas/bossgate_reply_v1.schema.json`, and `schemas/bossgate_repair_approval_v1.schema.json`.
- Golden vectors and behavior coverage: `tests/fixtures/bossgate_notification_v1.json`, `tests/fixtures/bossgate_reply_v1.json`, `tests/fixtures/bossgate_repair_approval_v1.json`, `tests/test_bossgate_notifications.py`, and `tests/test_bossgate_repair_approval.py`.
- Adjacent protocol overview: [BossGate Protocol](./bossgate_protocol.md); connector overview: [BossGate Connector](./bossgate_connector.md).
