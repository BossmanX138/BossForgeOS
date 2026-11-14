"""Wire contracts: tampering, disclosure, invalid inputs and replay must fail closed."""
import hashlib
import base64
import hmac
import json
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import MappingProxyType
import unittest
from uuid import UUID

from core.bossgate.notifications import (
    canonical_json_bytes, build_notification_envelope, validate_notification_envelope,
    decrypt_notification_detail, build_reply_envelope, validate_reply_envelope,
)
from core.bossgate import decrypt_json_payload, encrypt_json_payload


class NotificationTests(unittest.TestCase):
    now = datetime(2026, 10, 23, 12, tzinfo=timezone.utc)
    secret = "test-only-notification-key"
    correlation = "e09ccbad-0569-44ec-b07a-a7a37806b78f"
    preview = {"title": "Decision", "project_name": "Example", "summary": "Review needed", "action": "Open Archivist"}

    def notification(self, **overrides):
        args = dict(event_type="repair.needs_decision", severity="warning", source_gate="archivist-gate",
                    recipient_account_id="account-1", preview=dict(self.preview), detail={"evidence": "private-stack-trace"},
                    secret_key=self.secret, key_id="key-1", correlation_id=self.correlation, at=self.now)
        args.update(overrides)
        return build_notification_envelope(**args)

    def reply(self, **overrides):
        args = dict(parent_message_id="3675c3ec-b28d-412f-87ae-b3b380118bed", correlation_id=self.correlation,
                    source_gate="cbcaa-gate", target_gate="archivist-gate", reply_type="request_status",
                    detail={"question": "private-question"}, secret_key=self.secret, key_id="key-1", at=self.now)
        args.update(overrides)
        return build_reply_envelope(**args)

    def resign(self, envelope):
        envelope["signature"] = hmac.new(self.secret.encode(), canonical_json_bytes(
            {k: v for k, v in envelope.items() if k != "signature"}), hashlib.sha256).hexdigest()
        return envelope

    def test_notification_round_trip_preserves_redacted_preview_and_sealed_detail(self):
        envelope = self.notification()
        self.assertEqual(envelope["schema"], "bosscrafts.bossgate.notification.v1")
        self.assertEqual(str(UUID(envelope["message_id"])), envelope["message_id"])
        self.assertEqual(str(UUID(envelope["correlation_id"])), self.correlation)
        self.assertEqual(envelope["created_at"], "2026-10-23T12:00:00Z")
        self.assertEqual(envelope["expires_at"], "2026-10-24T12:00:00Z")
        self.assertEqual(envelope["preview"], self.preview)
        self.assertNotIn("private-stack-trace", json.dumps(envelope))
        self.assertEqual(decrypt_notification_detail(envelope, MappingProxyType({"key-1": self.secret})),
                         {"evidence": "private-stack-trace"})
        self.assertEqual(validate_notification_envelope(envelope, self.secret, at=self.now), (True, "ok"))
        self.assertEqual(envelope["payload_hash"], hashlib.sha256(envelope["sealed_payload"].encode()).hexdigest())

    def test_reply_round_trip_binds_parent_message_and_correlation(self):
        reply = self.reply()
        self.assertEqual(reply["schema"], "bosscrafts.bossgate.reply.v1")
        self.assertEqual(reply["expires_at"], "2026-10-30T12:00:00Z")
        self.assertEqual(str(UUID(reply["message_id"])), reply["message_id"])
        self.assertEqual(decrypt_json_payload(reply["sealed_payload"], self.secret), {"question": "private-question"})
        self.assertNotIn("private-question", json.dumps(reply))
        self.assertEqual(validate_reply_envelope(reply, self.secret, at=self.now), (True, "ok"))
        for field in ("parent_message_id", "correlation_id", "source_gate", "target_gate", "reply_type"):
            changed = deepcopy(reply)
            changed[field] = "3675c3ec-b28d-412f-87ae-b3b380118bec" if field.endswith("_id") else "changed"
            self.assertFalse(validate_reply_envelope(changed, self.secret, at=self.now)[0], field)

    def test_notification_rejects_missing_fields(self):
        envelope = self.notification()
        for field in envelope:
            with self.subTest(field=field):
                changed = dict(envelope)
                del changed[field]
                self.assertFalse(validate_notification_envelope(changed, self.secret, at=self.now)[0])

    def test_notification_rejects_non_utc_or_invalid_timestamp(self):
        for field in ("created_at", "expires_at"):
            for value in ("bad", "2026-10-23T12:00:00", "2026-10-23T12:00:00+01:00", "2026-10-23t12:00:00z", "2026-02-30T12:00:00Z"):
                with self.subTest(field=field, value=value):
                    envelope = self.notification()
                    envelope[field] = value
                    self.assertFalse(validate_notification_envelope(self.resign(envelope), self.secret, at=self.now)[0])

    def test_notification_rejects_preview_over_2048_or_sealed_payload_over_1048576_bytes(self):
        envelope = self.notification()
        overhead = len(canonical_json_bytes(envelope["preview"]).decode()) - len(envelope["preview"]["summary"])
        envelope["preview"]["summary"] = "x" * (2048 - overhead)
        self.assertTrue(validate_notification_envelope(self.resign(envelope), self.secret, at=self.now)[0])
        envelope["preview"]["summary"] += "x"
        self.assertFalse(validate_notification_envelope(self.resign(envelope), self.secret, at=self.now)[0])
        envelope = self.notification()
        # A valid ciphertext must be rejected specifically for size, not decoding.
        envelope["sealed_payload"] = encrypt_json_payload({"large": "x" * 1048576}, self.secret, "key-1")
        envelope["payload_hash"] = hashlib.sha256(envelope["sealed_payload"].encode()).hexdigest()
        result = validate_notification_envelope(self.resign(envelope), self.secret, at=self.now)
        self.assertFalse(result[0])
        self.assertIn("1048576", result[1])
        with self.assertRaises(ValueError):
            self.notification(detail={"huge": "x" * 1048576})
        with self.assertRaises(ValueError):
            self.notification(preview={**self.preview, "summary": "x" * 2048})

    def test_canonical_json_is_sorted_compact_ascii_and_rejects_nan(self):
        self.assertEqual(canonical_json_bytes({"z": "é", "a": 1}), b'{"a":1,"z":"\\u00e9"}')
        with self.assertRaises(ValueError):
            canonical_json_bytes({"invalid": float("nan")})

    def test_tampering_wrong_keys_and_failed_validation_do_not_consume_replay(self):
        for build, validate in ((self.notification, validate_notification_envelope), (self.reply, validate_reply_envelope)):
            envelope = build()
            tokens = set()
            for field, value in (("signature", "0" * 64), ("payload_hash", "0" * 64), ("sealed_payload", "invalid")):
                changed = {**envelope, field: value}
                self.assertFalse(validate(changed, self.secret, tokens, self.now)[0])
                self.assertEqual(tokens, set())
            for keys in ("wrong-key", {"missing": self.secret}, {"default": self.secret}):
                self.assertFalse(validate(envelope, keys, tokens, self.now)[0])
                self.assertEqual(tokens, set())
            self.assertEqual(validate(envelope, {"key-1": self.secret}, tokens, self.now), (True, "ok"))
            self.assertEqual(len(tokens), 1)
            self.assertFalse(validate(envelope, self.secret, tokens, self.now)[0])

    def test_expiry_future_creation_and_invalid_interval_fail_closed(self):
        for build, validate in ((self.notification, validate_notification_envelope), (self.reply, validate_reply_envelope)):
            envelope = build(expires_in_seconds=60)
            self.assertFalse(validate(envelope, self.secret, at=self.now + timedelta(seconds=60))[0])
            self.assertFalse(validate(envelope, self.secret, at=self.now - timedelta(seconds=1))[0])
            envelope["expires_at"] = envelope["created_at"]
            self.assertFalse(validate(self.resign(envelope), self.secret, at=self.now)[0])

    def test_structure_types_and_unknown_fields_fail_closed(self):
        for build, validate in ((self.notification, validate_notification_envelope), (self.reply, validate_reply_envelope)):
            for field, value in (("message_id", "bad"), ("correlation_id", 1), ("nonce", ""),
                                 ("key_id", ""), ("source_gate", ""), ("signature", []), ("unknown", True)):
                self.assertFalse(validate({**build(), field: value}, self.secret, at=self.now)[0])
            self.assertFalse(validate([], self.secret, at=self.now)[0])
        for severity in ("info", "warning", "error", "critical"):
            self.assertTrue(validate_notification_envelope(self.notification(severity=severity), self.secret, at=self.now)[0])
        for overrides in ({"severity": "urgent"}, {"event_type": "internal.state"}, {"correlation_id": "bad"},
                          {"secret_key": ""}, {"at": self.now.replace(tzinfo=None)}, {"expires_in_seconds": 0},
                          {"preview": {**self.preview, "evidence": "leak"}}):
            with self.assertRaises(ValueError):
                self.notification(**overrides)

    def test_authenticated_but_invalid_ciphertext_is_rejected_before_replay(self):
        envelope = self.notification()
        envelope["sealed_payload"] = "not-base64"
        envelope["payload_hash"] = hashlib.sha256(b"not-base64").hexdigest()
        tokens = set()
        self.assertFalse(validate_notification_envelope(self.resign(envelope), self.secret, tokens, self.now)[0])
        self.assertEqual(tokens, set())
        with self.assertRaises(ValueError):
            decrypt_notification_detail({**self.notification(), "signature": "0" * 64}, self.secret)

    def test_schemas_validate_builders_and_reject_extra_properties(self):
        import jsonschema
        root = Path(__file__).resolve().parents[1] / "schemas"
        for build, filename in ((self.notification, "bossgate_notification_v1.schema.json"), (self.reply, "bossgate_reply_v1.schema.json")):
            schema = json.loads((root / filename).read_text())
            validator = jsonschema.Draft7Validator(schema, format_checker=jsonschema.FormatChecker())
            envelope = build()
            self.assertEqual(list(validator.iter_errors(envelope)), [])
            for field in envelope:
                changed = dict(envelope)
                del changed[field]
                self.assertTrue(list(validator.iter_errors(changed)), field)
            self.assertTrue(list(validator.iter_errors({**envelope, "extra": "forbidden"})))

    def test_both_envelopes_reject_authenticated_noncanonical_or_invalid_sealed_blobs(self):
        for build, validate in ((self.notification, validate_notification_envelope), (self.reply, validate_reply_envelope)):
            original = build()
            sealed = original["sealed_payload"]
            blob = json.loads(base64.b64decode(sealed))
            malformed = ["!" + sealed, sealed + "\n", sealed + "=", base64.b64encode(b"[]").decode()]
            for field, value in (("extra", True), ("version", 999), ("version", True), ("alg", "aes-256-gcm"),
                                 ("key_id", "other-key"), ("nonce_b64", "!" + blob["nonce_b64"]),
                                 ("nonce_b64", base64.b64encode(b"short").decode()),
                                 ("ciphertext_b64", "!" + blob["ciphertext_b64"]),
                                 ("ciphertext_b64", base64.b64encode(b"short").decode())):
                malformed.append(base64.b64encode(json.dumps({**blob, field: value}).encode()).decode())
            malformed.append(base64.b64encode((json.dumps(blob)[:-1] + ',"version":1}').encode()).decode())
            for index, value in enumerate(malformed):
                with self.subTest(kind=original["schema"], case=index):
                    envelope = {**original, "sealed_payload": value,
                                "payload_hash": hashlib.sha256(value.encode()).hexdigest()}
                    self.resign(envelope)
                    tokens = set()
                    self.assertFalse(validate(envelope, self.secret, tokens, self.now)[0])
                    self.assertEqual(tokens, set())
                    if build == self.notification:
                        with self.assertRaises(ValueError):
                            decrypt_notification_detail(envelope, self.secret)

    def test_both_envelopes_reject_authenticated_nonfinite_detail(self):
        for build, validate in ((self.notification, validate_notification_envelope), (self.reply, validate_reply_envelope)):
            for value in (float("nan"), float("inf"), -float("inf")):
                with self.subTest(kind=build.__name__, value=value):
                    envelope = build()
                    envelope["sealed_payload"] = encrypt_json_payload({"nested": [{"value": value}]}, self.secret, "key-1")
                    envelope["payload_hash"] = hashlib.sha256(envelope["sealed_payload"].encode()).hexdigest()
                    tokens = set()
                    self.assertFalse(validate(self.resign(envelope), self.secret, tokens, self.now)[0])
                    self.assertEqual(tokens, set())

    def test_both_builders_reject_explicit_command_code_fields_recursively(self):
        for build in (self.notification, self.reply):
            for detail in ({"command_code": "DUMMY-ONLY"}, {"nested": [{"commandCode": "DUMMY-ONLY"}]},
                           {"context": {"raw_command_code": "DUMMY-ONLY"}}, {"command-code": "DUMMY-ONLY"}):
                with self.subTest(kind=build.__name__, detail=detail):
                    with self.assertRaises(ValueError):
                        build(detail=detail)

    def test_both_builders_reject_noncanonical_key_ids(self):
        for build, validate in ((self.notification, validate_notification_envelope), (self.reply, validate_reply_envelope)):
            for key_id in (" key-1 ", "key-1 ", "\tkey-1", "\nkey-1\n"):
                with self.subTest(kind=build.__name__, key_id=key_id):
                    with self.assertRaises(ValueError):
                        build(key_id=key_id)
            envelope = build(key_id="key-1")
            self.assertEqual(envelope["key_id"], "key-1")
            self.assertEqual(validate(envelope, {"key-1": self.secret}, at=self.now), (True, "ok"))

    def test_both_envelopes_reject_authenticated_command_code_fields_recursively(self):
        for build, validate in ((self.notification, validate_notification_envelope), (self.reply, validate_reply_envelope)):
            for detail in ({"command_code": "DUMMY-ONLY"}, {"nested": [{"commandCode": "DUMMY-ONLY"}]},
                           {"context": {"raw_command_code": "DUMMY-ONLY"}}, {"command-code": "DUMMY-ONLY"}):
                with self.subTest(kind=build.__name__, detail=detail):
                    envelope = build()
                    envelope["sealed_payload"] = encrypt_json_payload(detail, self.secret, "key-1")
                    envelope["payload_hash"] = hashlib.sha256(envelope["sealed_payload"].encode()).hexdigest()
                    tokens = set()
                    self.assertFalse(validate(self.resign(envelope), self.secret, tokens, self.now)[0])
                    self.assertEqual(tokens, set())
                    if build == self.notification:
                        with self.assertRaises(ValueError):
                            decrypt_notification_detail(envelope, self.secret)

    def test_golden_envelopes_have_stable_hashes_signatures_and_decrypted_details(self):
        import jsonschema
        root = Path(__file__).resolve().parents[1]
        for name, validate in (("notification", validate_notification_envelope), ("reply", validate_reply_envelope)):
            with self.subTest(kind=name):
                fixture = json.loads((root / f"tests/fixtures/bossgate_{name}_v1.json").read_text())
                envelope = fixture["envelope"]
                # Deliberately independent of the production canonicalization helper.
                serialized = json.dumps(envelope, sort_keys=True, separators=(",", ":"),
                                        ensure_ascii=True, allow_nan=False).encode("utf-8")
                self.assertEqual(hashlib.sha256(serialized).hexdigest(), fixture["canonical_sha256"])
                unsigned = {k: v for k, v in envelope.items() if k != "signature"}
                expected_signature = hmac.new(fixture["secret_key"].encode(), json.dumps(
                    unsigned, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
                    allow_nan=False).encode(), hashlib.sha256).hexdigest()
                self.assertEqual(envelope["signature"], expected_signature)
                reordered = json.loads(json.dumps(dict(reversed(list(envelope.items()))), indent=4))
                keys = {envelope["key_id"]: fixture["secret_key"]}
                self.assertEqual(validate(reordered, keys, at=self.now), (True, "ok"))
                self.assertEqual(decrypt_json_payload(envelope["sealed_payload"], keys), fixture["detail"])
                schema = json.loads((root / f"schemas/bossgate_{name}_v1.schema.json").read_text())
                self.assertEqual(list(jsonschema.Draft7Validator(schema,
                    format_checker=jsonschema.FormatChecker()).iter_errors(envelope)), [])


if __name__ == "__main__":
    unittest.main()
